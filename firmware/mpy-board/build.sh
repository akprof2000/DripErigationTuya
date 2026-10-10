#!/bin/bash
# Сборка прошивки контроллера (MicroPython + замороженный mpy/lib) в WSL Ubuntu.
# Вызывается из tools/build_fw.py; можно и руками:  wsl -d Ubuntu bash firmware/mpy-board/build.sh
#
# Нужны: клон MicroPython (v1.26.x) в $MPY_DIR с собранным mpy-cross и подмодулями
# esp32, ESP-IDF v5.4 (берётся из TuyaOpen, см. переменные ниже).
set -e
MPY_DIR=${MPY_DIR:-$HOME/micropython}
IDF_DIR=${IDF_DIR:-$HOME/TuyaOpen/platform/ESP32/esp-idf}
export IDF_TOOLS_PATH=${IDF_TOOLS_PATH:-$HOME/TuyaOpen/platform/ESP32/.espressif}
export IDF_PYTHON_ENV_PATH=${IDF_PYTHON_ENV_PATH:-$IDF_TOOLS_PATH/python_env/idf5.4_py3.12_env}
export PATH=$HOME/TuyaOpen/.tools/python/3.12.13/cpython-3.12-linux-x86_64-gnu/bin:$PATH

BOARD_DIR=$(cd "$(dirname "$0")/DRIP" && pwd)
. "$IDF_DIR/export.sh" >/dev/null 2>&1 || { echo "ESP-IDF: export.sh не сработал"; exit 1; }

cd "$MPY_DIR/ports/esp32"
make -j"$(nproc)" BOARD=DRIP BOARD_DIR="$BOARD_DIR" > /tmp/drip-build.log 2>&1 \
  || { echo "сборка не удалась, см. /tmp/drip-build.log"; grep -n "error" /tmp/drip-build.log | head -20; exit 1; }
echo "BUILD_DIR=$MPY_DIR/ports/esp32/build-DRIP"
ls -la build-DRIP/firmware.bin build-DRIP/micropython.bin
