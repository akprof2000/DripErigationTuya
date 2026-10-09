"""main.py — эмулятор контроллера капельного полива для облака Tuya.

Запуск:
  python main.py --offline          # без облака: DP печатаются в консоль
  python main.py                    # с облаком: нужен tuya.json (PID, UUID, AuthKey)

Время эмулятора идёт быстрее реального (--speed, по умолчанию ×6:
одна «минута» прошивки — 10 секунд), чтобы на панели всё менялось заметно.
Консольные команды — `help`.
"""
import argparse
import json
import logging
import shlex
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mpy" / "lib"))
from device import Device  # noqa: E402
from spec import Spec  # noqa: E402
from world import World, ADC_WET, ADC_DRY  # noqa: E402

HERE = Path(__file__).resolve().parent
log = logging.getLogger("emu")

HELP = """\
Мир (что «видят» датчики):
  dry N|all [доля]     засушить грядку (доля влажности почвы, по умолч. 0.1)
  wet N|all [доля]     залить грядку (по умолч. 0.9)
  put N soil|water|air куда воткнут датчик N (для мастеров калибровки и поиска)
  rain on|off          дождь
  night on|off|auto    ночь (auto — по часам эмулятора: ночь 21:00–06:00)
  clog 0..1            пропускная способность фильтра (1 = чистый, 0.3 = засор)
  fault rtc|sd|valves on|off   аппаратная неисправность (аварийный режим)
Облако (как будто прислала панель):
  set КОД ЗНАЧЕНИЕ     например: set mode_3 on | set border_1 45 | set run_on_night true
                       set wizard {"op":"calib","ch":2,"step":"start"}
Прочее:
  status               состояние каналов
  dps                  все DP в формате Tuya
  speed N              ускорение времени (секунд эмулятора на 1 с)
  time ЧЧ:ММ           перевести часы эмулятора
  quit
"""


class Emulator:
    def __init__(self, args):
        self.spec = Spec()
        self.world = World(self.spec.channels)
        state = HERE / args.state
        fresh = not state.exists()
        self.dev = Device(self.world, state_path=str(state), spec=self.spec)
        if fresh:
            # 🔧 новый «прибор» сразу откалиброван под модель мира, чтобы панель
            #    показывала правдоподобные проценты, а не 0 % на всех каналах
            for i, c in enumerate(self.dev.cfg.channels):
                c.min_val, c.max_val = ADC_WET, ADC_DRY
                c.name = f"🌱 Грядка {i + 1}"
                self.dev.set_low_high(i, ADC_WET, ADC_DRY)
            self.dev.save()
        self.speed = args.speed
        self.now = 0.0
        lt = time.localtime()
        self.unix = time.time() - lt.tm_sec    # «часы» эмулятора, стартуют с реального времени
        self.lock = threading.RLock()
        self.client = None
        self.offline = args.offline
        self.verbose = args.verbose
        self.running = True

    # ------------------------------------------------------------ облако
    def connect(self, creds_path):
        # тот же клиент, что работает на ESP32 под MicroPython (mpy/lib/tuya.py)
        from tuya import Tuya
        from tuyalinksdk.console_qrcode import qrcode_generate

        creds = json.loads(Path(creds_path).read_text(encoding="utf-8"))
        c = Tuya(creds["pid"], creds["uuid"], creds["authkey"], version=creds.get("version", "1.0.0"),
                 storage=str(HERE / "tuya_storage.json"), log=lambda m: log.info(m))
        c.on_qrcode = lambda url: (print("\nОтсканируйте QR в Smart Life («+» → сканер):", url),
                                   qrcode_generate(url))
        c.on_connected = self._on_connected
        c.on_dps = self._on_dps
        c.on_reset = lambda: log.warning("облако: устройство удалено из приложения")
        self.client = c
        threading.Thread(target=self.cloud_loop, daemon=True).start()

    def cloud_loop(self):
        # без self.lock: подключение может идти секундами, а консоль и модель
        # должны работать; колбэки клиента сами берут lock
        while self.running:
            self.client.loop()
            time.sleep(0.05)

    def _on_connected(self):
        log.info("облако: подключено")
        with self.lock:
            for p in self.dev.report(full=True):
                self.push(p)

    def _on_dps(self, dps):
        log.info("← облако: %s", dps)
        with self.lock:
            for dp_id, value in dps.items():
                self.apply(dp_id, value)

    def apply(self, dp_id, value):
        try:
            code, v = self.spec.decode(dp_id, value)
            self.dev.apply_dp(code, v, self.now, self.unix)
        except (ValueError, KeyError) as e:
            log.error("DP %s=%r отклонён: %s", dp_id, value, e)
        # подтверждение записи: облако ждёт отчёт с новым значением
        for p in self.dev.report():
            self.push(p)

    def push(self, packet):
        if self.offline or self.client is None:
            if self.verbose or "event" in packet:
                shown = {k: (v.hex() if isinstance(v, bytes) else v) for k, v in packet.items()}
                print("→", shown if "event" not in packet else self.event_text(packet["event"]))
            return
        dps = {self.spec.by_code[code].id: v for code, v in packet.items()}
        if self.client.push(dps):
            log.debug("→ облако: %s", dps)

    def event_text(self, raw):
        """Человекочитаемое событие для консоли (так же будет рисовать панель)."""
        e = json.loads(raw)
        ch = e.get("ch")
        name = f"№ {ch} ({self.dev.cfg.channels[ch - 1].name})" if ch else ""
        return {
            "valve": lambda: f"клапан {name}: {e['s']}" + (f", влажность {e['h']} %" if "h" in e else "")
                             + (" (погода)" if e.get("w") else ""),
            "clog": lambda: f"засор фильтра: {e['r']} л/мин при норме {e['e']}",
            "hw_fault": lambda: "аварийный режим: " + ", ".join(e["f"]),
        }.get(e["t"], lambda: e["t"])()

    # ------------------------------------------------------------ цикл
    def run_loop(self):
        while self.running:
            time.sleep(1)
            with self.lock:
                self.now += self.speed
                self.unix += self.speed
                self.dev.tick(self.now, self.unix, self.speed)
                for p in self.dev.report():
                    self.push(p)

    # ------------------------------------------------------------ консоль
    def status(self):
        d = self.dev
        t = time.strftime("%H:%M", time.localtime(self.unix))
        print(f"[{t}] дождь={d.rain_now} ночь={d.night_now} насос={d.pump} дренаж={d.drain_active} "
              f"поток={d.flow_rate:.3f} л/мин сессия={d.flow_session:.2f} всего={d.cfg.flow_total:.2f} "
              f"засор={d.clogged} аварии={sorted(d.hw_faults) or '-'}")
        for i, c in enumerate(d.cfg.channels):
            print(f"  {i + 1}: {d.percent(i):3d}% (почва {self.world.soil[i]:.2f}, датчик в {self.world.place[i]:5}) "
                  f"порог {c.border}% режим {c.mode:10} клапан {d.old_mode[i]:12} {c.name}")
        print("  мастер:", json.dumps(d.wizard, ensure_ascii=False))

    def command(self, line):
        try:
            argv = shlex.split(line, posix=True)
        except ValueError:
            argv = line.split()
        if not argv:
            return
        cmd, a = argv[0], argv[1:]
        w = self.world

        def chans(x):
            return range(w.channels) if x == "all" else [int(x) - 1]

        if cmd == "help":
            print(HELP)
        elif cmd == "quit":
            self.running = False
        elif cmd == "status":
            self.status()
        elif cmd == "dps":
            for k, v in self.dev.dp_snapshot().items():
                print(f"  {self.spec.by_code[k].id:3d} {k:20} {v.hex() if isinstance(v, bytes) else v!r}")
        elif cmd in ("dry", "wet"):
            level = float(a[1]) if len(a) > 1 else (0.1 if cmd == "dry" else 0.9)
            for i in chans(a[0]):
                w.soil[i] = level
        elif cmd == "put":
            assert a[1] in ("soil", "water", "air")
            for i in chans(a[0]):
                w.place[i] = a[1]
        elif cmd == "rain":
            w.rain = a[0] == "on"
        elif cmd == "night":
            w.auto_daynight = a[0] == "auto"
            if not w.auto_daynight:
                w.night = a[0] == "on"
        elif cmd == "clog":
            w.clog = float(a[0])
        elif cmd == "fault":
            (self.dev.hw_faults.add if a[1] == "on" else self.dev.hw_faults.discard)(a[0])
        elif cmd == "speed":
            self.speed = float(a[0])
        elif cmd == "time":
            hh, mm = map(int, a[0].split(":"))
            lt = time.localtime(self.unix)
            self.unix += ((hh * 60 + mm) - (lt.tm_hour * 60 + lt.tm_min)) * 60
        elif cmd == "set":
            # значение берём из исходной строки: shlex съел бы кавычки в JSON мастера
            _, code, raw = line.strip().split(maxsplit=2)
            dp = self.spec.by_code[code]
            if dp.type == "bool":
                val = raw.lower() in ("1", "true", "on", "да")
            elif dp.type == "value":
                val = int(round(float(raw) * 10 ** dp.scale))
            else:
                val = raw
            self.apply(dp.id, val)
        else:
            print("неизвестная команда, см. help")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="не подключаться к облаку")
    ap.add_argument("--creds", default=str(HERE / "tuya.json"), help="файл с pid/uuid/authkey")
    ap.add_argument("--state", default="state.json", help="файл настроек (аналог Config на SD)")
    ap.add_argument("--speed", type=float, default=6.0, help="секунд эмулятора на 1 реальную секунду")
    ap.add_argument("-v", "--verbose", action="store_true", help="печатать все отчёты DP и отладку SDK")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    emu = Emulator(args)
    if not args.offline:
        if not Path(args.creds).exists():
            sys.exit(f"Нет {args.creds}. Скопируйте tuya.example.json → tuya.json и впишите PID/UUID/AuthKey, "
                     f"или запустите с --offline.")
        emu.connect(args.creds)
    threading.Thread(target=emu.run_loop, daemon=True).start()

    print("Эмулятор запущен. help — список команд.")
    while emu.running:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        with emu.lock:
            try:
                emu.command(line)
            except (ValueError, IndexError, KeyError, AssertionError) as e:
                print("ошибка:", e or "неверные аргументы")
    emu.running = False
    with emu.lock:
        emu.dev.save()


if __name__ == "__main__":
    main()
