"""ota.py — обновление прошивки через облако Tuya (как в TuyaOpen, без OTA-разделов).

«Прошивка» для MicroPython — пакет .mpk: все файлы /app (логика, клиент
облака, драйверы) и dp.json. Его загружают в консоль Tuya как версию
прошивки продукта; дальше всё делает облако:
  1. пользователь нажимает «Обновить» в Smart Life (или включено
     автообновление, тогда облако присылает задание само) → по MQTT приходит
     протокол 15 (PRO_UPGD_REQ) с firmwareType;
  2. устройство запрашивает tuya.device.upgrade.get → httpsUrl, size, md5,
     version; отвечает статусом 2 «обновляюсь» (tuya.device.upgrade.status.update);
  3. качает файл кусками на SD/флеш, шлёт прогресс (протокол 16), проверяет
     md5 и размер, распаковывает в /app_new, пишет /ota/apply.json;
  4. статус 3 «готово» и перезагрузка; main.py меняет /app_new → /app, а
     старую версию держит в /app_prev для отката, если новая не стартует;
  5. после подключения новая версия сообщает облаку свои версии
     (tuya.device.versions.update) — в приложении пропадает «доступно обновление».
При старте также спрашиваем tuya.device.upgrade.silent.get: так подхватывается
автообновление, назначенное, пока устройство было выключено.

Формат .mpk (tools/build_fw.py):
  строка "MPK1", строка JSON {"version":…, "files":[{"path","size","sha256"}…]},
  затем содержимое файлов подряд в порядке списка.
"""
import hashlib
import json
import os

from compat import b64encode  # noqa: F401  (на случай отладки) — основной код ниже

MAGIC = b"MPK1\n"
OTA_DIR = "/ota"
PKG = OTA_DIR + "/fw.mpk"
APPLY = OTA_DIR + "/apply.json"
NEW_DIR = "/app_new"
CHUNK = 2048

# статусы tuya.device.upgrade.status.update (tuya_ota.h)
ST_UPGRADING, ST_DONE, ST_FAILED = 2, 3, 4
ST_DOWNLOAD_START, ST_DOWNLOAD_DONE, ST_DOWNLOAD_ERROR = 10, 11, 40


def _hexdigest(h):
    import binascii
    return binascii.hexlify(h.digest()).decode()


def _mkdirs(path):
    """Создать все каталоги пути (os.makedirs в MicroPython нет)."""
    makedirs = getattr(os, "makedirs", None)
    if makedirs:                       # CPython (тесты на ПК)
        makedirs(path, exist_ok=True)
        return
    parts = path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            os.mkdir(cur)
        except OSError:
            pass


def _rmtree(path):
    try:
        for name, kind, *_ in os.ilistdir(path):
            full = path + "/" + name
            if kind & 0x4000:
                _rmtree(full)
            else:
                os.remove(full)
        os.rmdir(path)
    except (OSError, AttributeError):
        # CPython (тесты): ilistdir нет
        import shutil
        shutil.rmtree(path, ignore_errors=True)


def read_header(f):
    """Файл .mpk (открыт в 'rb', позиция 0) → dict заголовка; f остаётся на начале данных."""
    if f.read(len(MAGIC)) != MAGIC:
        raise ValueError("не .mpk")
    line = f.readline()
    return json.loads(line)


def unpack(pkg_path, dest):
    """Распаковать пакет в каталог dest с проверкой sha256 каждого файла. → version."""
    _rmtree(dest)
    _mkdirs(dest)
    with open(pkg_path, "rb") as f:
        hdr = read_header(f)
        for item in hdr["files"]:
            path = dest + "/" + item["path"]
            if "/" in item["path"]:
                _mkdirs(path.rsplit("/", 1)[0])
            h = hashlib.sha256()
            left = item["size"]
            with open(path, "wb") as out:
                while left > 0:
                    chunk = f.read(min(CHUNK, left))
                    if not chunk:
                        raise ValueError("пакет оборван: " + item["path"])
                    out.write(chunk)
                    h.update(chunk)
                    left -= len(chunk)
            if _hexdigest(h) != item["sha256"]:
                raise ValueError("sha256 не сошёлся: " + item["path"])
    return hdr["version"]


def md5_of_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return _hexdigest(h)


class Ota:
    def __init__(self, tuya, version, log=print, on_before_reboot=None):
        self.tuya = tuya
        self.version = version
        self.log = log
        self.on_before_reboot = on_before_reboot
        self._channel = None        # задание на обновление ждёт выполнения
        self._busy = False

    # ---------------- события облака
    def on_protocol(self, proto, data):
        if proto == 15:              # PRO_UPGD_REQ
            self._channel = (data or {}).get("firmwareType", 0)
            self.log("ota: облако просит обновиться (канал %s)" % self._channel)

    def on_connected(self):
        """После подключения: доложить версию, завершить прошлое обновление, спросить тихое."""
        try:
            applied = None
            try:
                with open(APPLY) as f:
                    applied = json.load(f)
            except (OSError, ValueError):
                pass
            if applied:
                self.tuya.atop_dev("tuya.device.upgrade.status.update", "4.1",
                                   {"type": applied.get("type", 0), "upgradeStatus": ST_DONE})
                os.remove(APPLY)
                self.log("ota: обновление до %s завершено" % applied.get("version"))
            self.tuya.atop_dev("tuya.device.versions.update", "4.1", {
                "versions": json.dumps([{"otaChannel": 0, "protocolVer": "2.3",
                                         "baselineVer": "40.07", "softVer": self.version}])})
            res = self.tuya.atop_dev("tuya.device.upgrade.silent.get", "4.4", {"type": 0})
            if res and res.get("httpsUrl"):
                self.log("ota: есть тихое обновление до %s" % res.get("version"))
                self._run(res)
        except Exception as e:
            self.log("ota: on_connected: %s" % e)

    def tick(self):
        if self._channel is None or self._busy or not self.tuya.online:
            return
        ch, self._channel = self._channel, None
        try:
            info = self.tuya.atop_dev("tuya.device.upgrade.get", "4.4", {"type": ch})
        except Exception as e:
            self.log("ota: upgrade.get: %s" % e)
            return
        if not info or not info.get("httpsUrl"):
            self.log("ota: обновления нет")
            return
        self._run(info)

    # ---------------- само обновление
    def _status(self, ch, st):
        try:
            self.tuya.atop_dev("tuya.device.upgrade.status.update", "4.1", {"type": ch, "upgradeStatus": st})
        except Exception as e:
            self.log("ota: status %s: %s" % (st, e))

    def _progress(self, ch, pct):
        self.tuya.publish(16, {"progress": str(pct), "firmwareType": ch})

    def _run(self, info):
        self._busy = True
        ch = int(info.get("type", 0))
        try:
            self.log("ota: %s → %s, %s байт" % (self.version, info.get("version"), info.get("size")))
            self._status(ch, ST_UPGRADING)
            self._status(ch, ST_DOWNLOAD_START)
            self._download(info["httpsUrl"], int(info["size"]), ch)
            if info.get("md5") and md5_of_file(PKG) != info["md5"].lower():
                raise ValueError("md5 пакета не сошёлся")
            self._status(ch, ST_DOWNLOAD_DONE)
            version = unpack(PKG, NEW_DIR)
            _mkdirs(OTA_DIR)
            with open(APPLY, "w") as f:
                json.dump({"version": version, "type": ch}, f)
            self._progress(ch, 100)
            self.log("ota: пакет %s распакован, перезагрузка" % version)
            if self.on_before_reboot:
                self.on_before_reboot()
            import machine
            machine.reset()
        except Exception as e:
            self.log("ota: ошибка: %s" % e)
            self._status(ch, ST_DOWNLOAD_ERROR)
            self._status(ch, ST_FAILED)
            _rmtree(NEW_DIR)
        finally:
            self._busy = False

    def _download(self, url, size, ch):
        import requests
        _mkdirs(OTA_DIR)
        r = requests.get(url, stream=True)
        if r.status_code != 200:
            raise OSError("HTTP %s" % r.status_code)
        got, last_pct = 0, -1
        try:
            with open(PKG, "wb") as f:
                while got < size:
                    chunk = r.raw.read(min(CHUNK, size - got))
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    pct = got * 100 // size
                    if pct - last_pct >= 10:
                        last_pct = pct
                        self._progress(ch, min(pct, 99))
        finally:
            r.close()
        if got != size:
            raise OSError("скачано %d из %d байт" % (got, size))
