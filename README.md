# DripErigationTuya

Контроллер капельного полива на ESP32, работающий через облако **Tuya**:
управление и графики в приложении **Smart Life**, своя панель устройства,
push-уведомления, обновление прошивки по воздуху.

Это продолжение проекта **[DripIrrigation](https://github.com/akprof2000/DripIrrigation)**
(версия с Telegram-ботом). Логика полива перенесена оттуда модуль в модуль, а
**железо — без изменений**: схема, плата-носитель, перечень компонентов и сборка
берутся из исходного репозитория:

| Что | Где в DripIrrigation |
|---|---|
| Плата-носитель (KiCad) | [`hardware/`](https://github.com/akprof2000/DripIrrigation/tree/master/hardware) — `DripCarrier.kicad_pcb`, генератор `gen_pcb.py`, Gerber для заказа |
| Описание платы и блок-схемы | [`docs/hardware-carrier-board.md`](https://github.com/akprof2000/DripIrrigation/blob/master/docs/hardware-carrier-board.md) |
| Перечень компонентов (BOM) | [`docs/bom.md`](https://github.com/akprof2000/DripIrrigation/blob/master/docs/bom.md) |
| Сборка | [`docs/assembly.md`](https://github.com/akprof2000/DripIrrigation/blob/master/docs/assembly.md) |
| Соединения (netlist) | [`hardware/netlist.md`](https://github.com/akprof2000/DripIrrigation/blob/master/hardware/netlist.md) |
| Распиновка | [`pins.h`](https://github.com/akprof2000/DripIrrigation/blob/master/pins.h) — в этой прошивке те же пины |

## Возможности

- **8 грядок**: датчики влажности через мультиплексор, клапаны на PCF8574,
  режимы «Авто / Всегда вкл / Выкл / Парник», порог и гистерезис, блокировки
  ночью и в дождь, калибровка датчиков (мастер и вручную).
- **Вода**: насос давления, дренаж, заливка бака, расходомер, расход по дням,
  контроль засора фильтра по падению потока.
- **Работа без интернета**: полив идёт по локальной логике, отчёты копятся в
  очереди (SD или флеш) и уходят в облако с исходным временем.
- **Состояние периферии** в приложении: «контроллер работает, не подключено: …»
  (часы DS3231, SD, плата клапанов, датчики).
- **Настройка Wi-Fi** без пароля к точке доступа: портал со списком сетей и QR-кодом
  привязки к Tuya; портал сам поднимается, если сеть пропала на 3 минуты.
- **OTA** через облако Tuya с откатом, если новая прошивка не вышла на связь.
- **Push-уведомления**: засор фильтра, авария платы клапанов, контроллер
  не в сети больше 30 минут (русский, английский, китайский).
- **Панель Smart Life** на русском, английском и китайском: грядки, вода, события,
  настройки; графики влажности по часам / неделям / месяцам с календарём,
  график открытия клапана, расход воды по дням.

## Состав репозитория

```
firmware/esp32/     прошивка на C++ (PlatformIO, Arduino-ядро ESP32) — основная
panel/              панель устройства (Tuya Smart MiniApp на Ray, React + TypeScript)
spec/dp.json        единый список data points: от него генерируются прошивка, панель, документация
docs/firmware.md    прошивка: модули, сборка, заливка, OTA, индикация
docs/dp.md          таблица DP и протокол мастеров
emulator/           эмулятор устройства на Python (для отладки панели без платы)
mpy/lib/            логика полива на Python — ядро эмулятора и его тестов
tools/              сборка/заливка (deploy.py), генераторы таблиц DP, иконок, отчёта о тестах
CHANGELOG.md        история версий
```

## Быстрый старт

Нужны: ESP32 DevKitC (38 pin, лучше с внешней антенной), плата-носитель из
[DripIrrigation](https://github.com/akprof2000/DripIrrigation/tree/master/hardware),
Python 3.11+ и лицензия TuyaOpen (UUID + AuthKey) для продукта в консоли Tuya.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r emulator/requirements.txt platformio

# лицензия: скопировать emulator/tuya.example.json → emulator/tuya.json и вписать pid/uuid/authkey
python tools/deploy.py --build                         # сборка, firmware/dist/drip_<версия>.bin
python tools/deploy.py --port COM8 --upload            # прошить
python tools/deploy.py --port COM8 --fs --creds        # записать лицензию на плату
python tools/deploy.py --port COM8 --monitor           # консоль
```

После прошивки плата поднимает открытую точку доступа `DripIrrigation-XXXX`:
подключитесь, выберите свою сеть 2,4 ГГц, затем в Smart Life «Добавить устройство»
→ сканировать QR со страницы портала. Подробнее — [docs/firmware.md](docs/firmware.md).

Готовый образ для OTA и прошивки лежит в [релизах](https://github.com/akprof2000/DripErigationTuya/releases).

### Панель

```bash
cd panel
npm install
npx -p typescript@5.9.3 tsc -p tsconfig.check.json    # проверка типов
```

Загрузка — через Tuya MiniApp IDE (проект `panel/`, MiniApp `tyn8jv4cjlpyk2u5u1`).

### Эмулятор

```bash
cd emulator
../.venv/Scripts/python main.py --offline     # без облака
../.venv/Scripts/python main.py               # с облаком, нужен tuya.json
```

Тесты: `cd emulator && python -m unittest discover -s tests`.

## Секреты

В git не попадают: `emulator/tuya.json` (лицензия), `emulator/tuya_storage.json`
(данные привязки), `firmware/esp32/data/` (образ файловой системы с лицензией и Wi-Fi).

## Лицензия

[WTFPL](LICENSE).
