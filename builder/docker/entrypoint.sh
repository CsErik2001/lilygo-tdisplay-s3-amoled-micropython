#!/bin/bash
set -e
source "$IDF_PATH/export.sh"

if [ "$1" = "build" ]; then
    cd "$MICROPY_DIR/ports/esp32"
    make BOARD=LILYGO_TDISPLAY_S3_AMOLED_PLUS -j"$(nproc)"
    mkdir -p /build-out
    cp build-LILYGO_TDISPLAY_S3_AMOLED_PLUS/firmware.bin /build-out/
    echo "Firmware artifacts copied to /build-out"
else
    exec "$@"
fi
