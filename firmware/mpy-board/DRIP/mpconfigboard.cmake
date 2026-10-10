# Плата контроллера капельного полива: ESP32-WROOM-32D (4 МБ флеш, без PSRAM).
# Сборка: make -C ports/esp32 BOARD=DRIP BOARD_DIR=<этот каталог>
set(IDF_TARGET esp32)

set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.free_ram
    ${MICROPY_BOARD_DIR}/sdkconfig.board
)

set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest.py)
