# drip_tuya — прошивка TuyaOpen для ESP32 (заготовка)

Копия примера `apps/tuya_cloud/switch_demo` из [TuyaOpen](https://github.com/tuya/TuyaOpen)
с PID продукта `0uo7msdnt2yn1lgp` (Drip Irrigation 8ch). Логики полива здесь нет:
DP, пришедшие из облака, отправляются обратно как есть.

Зачем она нужна: консоль Tuya не отдаёт лицензию TuyaOpen, пока у продукта нет
версии прошивки. Эту сборку загружаем как версию 1.0.0. Рабочая прошивка
пишется на MicroPython (`mpy/`).

Сборка (WSL Ubuntu, TuyaOpen в `~/TuyaOpen`):

```bash
cp -r firmware/drip_tuya ~/TuyaOpen/apps/drip_tuya
cd ~/TuyaOpen && . ./export.sh && cd apps/drip_tuya && tos.py build
```

Результат лежит в `dist/drip_tuya_1.0.0/`: `*_QIO_*.bin` для заводской прошивки (с адреса 0x0),
`*_UA_*.bin` для приложения и `*_UG_*.bin` для обновления OTA.
UUID и AuthKey пишутся в `src/tuya_config_secrets.h`, который не попадает в git.
