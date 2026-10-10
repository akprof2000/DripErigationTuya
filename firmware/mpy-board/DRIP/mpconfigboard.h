// Контроллер капельного полива (ESP32 DevKitC, 4 МБ, без PSRAM).
#define MICROPY_HW_BOARD_NAME "Drip Irrigation ESP32"
#define MICROPY_HW_MCU_NAME "ESP32"

// Bluetooth не нужен: экономим ОЗУ и флеш (образ должен влезть в OTA-раздел 1.5 МБ).
#define MICROPY_PY_BLUETOOTH (0)
