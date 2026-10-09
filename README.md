# DripErigationTuya

Перевод контроллера капельного полива ([DripIrrigation](https://github.com/akprof2000/DripIrrigation))
с Telegram-бота на Tuya: управление через приложение Smart Life, своя панель
устройства, ESP32 подключается к облаку Tuya напрямую.

Порядок работы: сначала панель и отладка на эмуляторе, потом перенос в прошивку.

```
spec/dp.json        единый список data points: от него работают эмулятор, панель и прошивка
docs/dp.md          таблица DP и протокол мастеров (генерируется tools/gen_dp_doc.py)
emulator/           эмулятор устройства на Python: логика прошивки и модель грядок
panel/              панель Smart MiniApp (будет)
```

## Эмулятор

Повторяет логику прошивки: решение по клапану (`decideValve`), блокировки по
ночи и дождю, режим парника, пусковое окно и насос давления, пролив дренажа,
заливку бака, авто-калибровку границ, мастера калибровки и поиска датчика,
аварийный режим. Контроль засора фильтра упрощён. Уведомления бота стали
событиями в DP `event`.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r emulator/requirements.txt
cd emulator
../.venv/Scripts/python main.py --offline     # без облака
../.venv/Scripts/python main.py               # с облаком: нужен tuya.json
```

Для облака скопируйте `emulator/tuya.example.json` в `emulator/tuya.json` и
впишите PID продукта и лицензию (UUID, AuthKey). Этот файл в git не попадает.
При первом запуске эмулятор печатает QR-код: отсканируйте его в Smart Life,
и устройство появится в приложении.

В консоли эмулятора можно управлять «миром» (`dry 3`, `rain on`, `put 4 water`,
`clog 0.3`, `fault sd on`) и слать DP так, как их прислала бы панель
(`set mode_2 off`). Полный список — команда `help`.

Тесты: `cd emulator && python -m unittest discover -s tests`.
