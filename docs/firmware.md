# Прошивка на MicroPython (ESP32 DevKitC)

Логика полива одна и та же в эмуляторе и на плате — `mpy/lib/device.py`.
На плате к ней добавляются драйверы и сервисы:

| Файл | Что делает |
|---|---|
| `mpy/boot.py`, `mpy/main.py` | стабильный загрузчик: применяет OTA-пакет, откатывает неудачную версию, запускает `app` |
| `mpy/lib/app.py` | главный цикл: раз в секунду тик логики, отчёты, Wi-Fi, облако, OTA, кнопка, светодиод |
| `mpy/lib/hw.py` | железо: мультиплексор датчиков + АЦП, PCF8574 (клапаны), реле насоса/дренажа/заливки, датчики дождя и света, расходомер на прерывании |
| `mpy/lib/clock.py` | DS3231 + NTP |
| `mpy/lib/wifi.py` | подключение к сети, портал настройки (точка доступа + страница) |
| `mpy/lib/tuya.py`, `mqtt.py`, `compat.py` | облако Tuya (протокол TuyaOpen 2.3, AES-GCM) |
| `mpy/lib/outbox.py` | очередь отчётов на время без связи |
| `mpy/lib/reporter.py` | фильтр отчётов: не больше ~3500 в сутки |
| `mpy/lib/ota.py` | обновление через облако Tuya |

Пины — как в `pins.h` старой прошивки: мультиплексор 12/13/14 → АЦП 33, дождь 15
(замкнут = дождь), свет 4 (HIGH = ночь), заливка 17, дренаж 25, насос 26,
расходомер 27, кнопка 16, светодиод 2, I2C 21/22 (PCF8574 0x20, DS3231 0x68),
SD на VSPI с CS 5.

## Первая заливка

1. Прошить MicroPython (образ `ESP32_GENERIC` с micropython.org, v1.24+):
   ```bash
   esptool.py --chip esp32 --port COM5 erase_flash
   esptool.py --chip esp32 --port COM5 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-*.bin
   ```
2. Положить файлы (нужен `pip install mpremote`):
   ```bash
   mpremote connect COM5 cp mpy/boot.py mpy/main.py :
   mpremote connect COM5 mkdir :app
   mpremote connect COM5 cp mpy/lib/*.py :app/
   mpremote connect COM5 cp spec/dp.json :app/dp.json
   mpremote connect COM5 cp emulator/tuya.json :tuya.json     # pid, uuid, authkey (лицензия TuyaOpen)
   ```
3. Включить плату. Без сохранённой сети (или с зажатой кнопкой) поднимется точка
   доступа `DripIrrigation-XXXX` (пароль `irrigation`), страница `http://192.168.4.1`
   — ввести SSID и пароль. Плата перезагрузится и подключится.
4. Привязать в Smart Life: «+» → сканер → QR из `python tools/bind_qr.py`
   (ссылка печатается и в консоль платы: `mpremote connect COM5 repl`).

Лицензия в `/tuya.json`, состояние привязки в `/tuya_state.json`, настройки
полива в `/sd/state.json` (без карты — `/state.json`), очередь отчётов —
`pending.jsonl` там же.

## Обновление (OTA)

1. Поднять `FW_VERSION` в `mpy/lib/device.py`, собрать пакет:
   `python tools/build_fw.py` → `firmware/dist/drip_mpy_<версия>.mpk` (печатает md5).
2. В консоли Tuya у прошивки продукта добавить версию: файл `.mpk` в поле
   **Firmware Updates** (UG), включить версию.
3. Пользователь в Smart Life нажимает «Обновить» (или включено автообновление
   устройства) → облако присылает задание, плата качает пакет, проверяет md5 и
   sha256 файлов, распаковывает в `/app_new` и перезагружается. `main.py`
   меняет каталоги местами; если новая версия три раза подряд не доходит до
   «минута онлайн», откатывается на предыдущую.

Вручную без облака: `mpremote cp mpy/lib/*.py :app/` и перезагрузка.

## Светодиод

- горит — на связи с облаком;
- мигает раз в секунду — Wi-Fi есть, облака нет (привязка или переподключение);
- частое мигание — нет Wi-Fi;
- в портале настройки — мигает, пока открыта страница.

Кнопка: удерживать 5 с — портал настройки Wi-Fi.
