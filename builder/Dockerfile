# Reproducible build environment for MicroPython (ESP32-S3 port) with the
# custom RM67162 + CST816 "amoled" usermod baked in.
#
# Build:
#   docker build -f builder/Dockerfile -t tdisplay-s3-amoled-mpy .
#
# Extract firmware.bin (and micropython.bin/bootloader/partitions if you
# want to flash by hand instead of via `idf.py -p PORT flash`):
#   docker create --name amoled-extract tdisplay-s3-amoled-mpy
#   docker cp amoled-extract:/build-out ./build-out
#   docker rm amoled-extract
#
# Flash directly from a container with USB passthrough (Linux host):
#   docker run --rm -it --device=/dev/ttyACM0 tdisplay-s3-amoled-mpy \
#       idf.py -p /dev/ttyACM0 flash

# Pin an ESP-IDF version known to work with recent MicroPython ESP32 ports.
# Check micropython/ports/esp32/README.md in the tag you use below for the
# exact recommended IDF version and bump this if it differs.
ARG IDF_VERSION=v5.5.1
FROM espressif/idf:${IDF_VERSION}

ARG MICROPYTHON_REF=v1.28.0
ENV MICROPY_DIR=/opt/micropython

# The official IDF v5.5.1 image omits this empty directory, but its CMake
# configuration still lists it as a public include path for ESP32-S3 builds.
RUN mkdir -p ${IDF_PATH}/components/esp_hw_support/mspi_timing_tuning/port/esp32s3/include

RUN git clone --depth 1 --branch ${MICROPYTHON_REF} \
        https://github.com/micropython/micropython.git ${MICROPY_DIR}

# mpy-cross is needed to build the frozen bytecode / manifest.
RUN cd ${MICROPY_DIR}/mpy-cross && make -j"$(nproc)"

RUN cd ${MICROPY_DIR}/ports/esp32 && \
    /bin/bash -c "source \$IDF_PATH/export.sh && make submodules"

# Drop in our board definition and usermod source tree.
COPY builder/boards/LILYGO_TDISPLAY_S3_AMOLED_PLUS \
     ${MICROPY_DIR}/ports/esp32/boards/LILYGO_TDISPLAY_S3_AMOLED_PLUS
COPY builder/modules/amoled ${MICROPY_DIR}/ports/esp32/modules/amoled

# Freeze the repository's UI module through the board manifest.
COPY amoled_ui.py \
     ${MICROPY_DIR}/ports/esp32/boards/LILYGO_TDISPLAY_S3_AMOLED_PLUS/modules/amoled_ui.py

WORKDIR ${MICROPY_DIR}/ports/esp32

COPY builder/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["build"]
