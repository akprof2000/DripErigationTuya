"""ota.py — обновление прошивки через облако Tuya на два OTA-раздела ESP32.

Прошивка — образ MicroPython с замороженным кодом контроллера
(`micropython.bin` из tools/build_fw.py). Его загружают в консоль Tuya как
версию прошивки продукта; дальше всё делает облако:
  1. пользователь нажимает «Обновить» в Smart Life (или включено
     автообновление, тогда облако присылает задание само) → по MQTT приходит
     протокол 15 (PRO_UPGD_REQ) с firmwareType;
  2. устройство запрашивает tuya.device.upgrade.get → httpsUrl, size, md5,
     version; отвечает статусом 2 «обновляюсь» (tuya.device.upgrade.status.update);
  3. образ пишется блоками по 4 КБ прямо в свободный OTA-раздел, прогресс —
     протокол 16, md5 считается на лету; пишется /ota/apply.json;
  4. раздел назначается загрузочным, перезагрузка. Загрузчик ESP-IDF ждёт
     подтверждения (confirm() — app.py даёт его, побыв минуту онлайн); если
     новая прошивка упала или перезагрузилась раньше — автоматический откат
     на прежний раздел;
  5. после подключения новая версия сообщает облаку статус 3 «готово» и свои
     версии (tuya.device.versions.update) — в приложении пропадает
     «доступно обновление».
При старте также спрашиваем tuya.device.upgrade.silent.get: так подхватывается
автообновление, назначенное, пока устройство было выключено.
"""
import binascii
import hashlib
import json
import os

from compat import http_open

OTA_DIR = "/ota"
APPLY = OTA_DIR + "/apply.json"
BLOCK = 4096                     # блок OTA-раздела

# статусы tuya.device.upgrade.status.update (tuya_ota.h)
ST_UPGRADING, ST_DONE, ST_FAILED = 2, 3, 4
ST_DOWNLOAD_START, ST_DOWNLOAD_DONE, ST_DOWNLOAD_ERROR = 10, 11, 40


def _mkdirs(path):
    """Создать все каталоги пути (os.makedirs в MicroPython нет)."""
    makedirs = getattr(os, "makedirs", None)
    if makedirs:                       # CPython (тесты на ПК)
        makedirs(path, exist_ok=True)
        return
    cur = ""
    for p in path.strip("/").split("/"):
        cur += "/" + p
        try:
            os.mkdir(cur)
        except OSError:
            pass


def confirm(log=print):
    """Подтвердить загрузчику, что текущая прошивка рабочая (отменить откат)."""
    try:
        from esp32 import Partition
        Partition.mark_app_valid_cancel_rollback()
    except ImportError:                # симуляция
        pass
    except Exception as e:             # не в состоянии «ждёт подтверждения» — это норма
        log("ota: confirm: %s" % e)


def target_partition():
    """Свободный OTA-раздел (куда писать образ)."""
    from esp32 import Partition
    return Partition(Partition.RUNNING).get_next_update()


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
            else:
                self.log("ota: версия %s доложена, обновлений нет" % self.version)
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
            size = int(info["size"])
            self.log("ota: %s → %s, %s байт" % (self.version, info.get("version"), size))
            part = target_partition()
            if size > part.info()[3]:
                raise ValueError("образ %d байт не влезает в раздел %s" % (size, part.info()[4]))
            self._status(ch, ST_UPGRADING)
            self._status(ch, ST_DOWNLOAD_START)
            md5 = self._download(info["httpsUrl"], size, part, ch)
            if info.get("md5") and md5 != info["md5"].lower():
                raise ValueError("md5 образа не сошёлся")
            self._status(ch, ST_DOWNLOAD_DONE)
            _mkdirs(OTA_DIR)
            with open(APPLY, "w") as f:
                json.dump({"version": info.get("version"), "type": ch}, f)
            self._progress(ch, 100)
            self.log("ota: образ записан в %s, перезагрузка" % part.info()[4])
            if self.on_before_reboot:
                self.on_before_reboot()
            part.set_boot()
            import machine
            machine.reset()
        except Exception as e:
            self.log("ota: ошибка: %s" % e)
            self._status(ch, ST_DOWNLOAD_ERROR)
            self._status(ch, ST_FAILED)
        finally:
            self._busy = False

    def _download(self, url, size, part, ch):
        """Скачать образ в раздел блоками по 4 КБ. → md5 (hex)."""
        status, _, conn, _ = http_open("GET", url, timeout=30)
        if status != 200:
            conn.close()
            raise OSError("HTTP %s" % status)
        h = hashlib.md5()
        buf = bytearray(BLOCK)
        mv = memoryview(buf)
        got, block, last_pct = 0, 0, -1
        try:
            while got < size:
                n = 0
                while n < BLOCK and got + n < size:        # набрать полный блок
                    chunk = conn.read_some(min(BLOCK - n, size - got - n))
                    if not chunk:
                        raise OSError("скачано %d из %d байт" % (got + n, size))
                    mv[n:n + len(chunk)] = chunk
                    n += len(chunk)
                h.update(mv[:n])
                if n < BLOCK:
                    for i in range(n, BLOCK):
                        buf[i] = 0xFF
                part.writeblocks(block, buf)
                block += 1
                got += n
                pct = got * 100 // size
                if pct - last_pct >= 10:
                    last_pct = pct
                    self._progress(ch, min(pct, 99))
        finally:
            conn.close()
        return binascii.hexlify(h.digest()).decode()
