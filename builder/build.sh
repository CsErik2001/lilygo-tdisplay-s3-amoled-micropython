#!/bin/bash
# Build the firmware in Docker and copy the artifacts out to ./build-out
set -e

IMG=tdisplay-s3-amoled-mpy

docker build -t "$IMG" .

docker rm -f amoled-build 2>/dev/null || true

# This actually RUNS the container - i.e. executes entrypoint.sh's "make"
# step - which is what was missing before (docker create alone never
# starts the container, so the build step never ran).
docker run --name amoled-build "$IMG" build

rm -rf ./build-out
docker cp amoled-build:/build-out ./build-out
docker rm amoled-build

echo ""
echo "Firmware in ./build-out/firmware.bin"
echo ""
echo "Flash:"
echo "  esptool --chip esp32s3 -p /dev/cu.usbmodem101 -b 460800 --before default-reset --after hard-reset \\"
echo "    write-flash -z --flash-mode dio --flash-freq 80m 0x0 build-out/firmware.bin"
