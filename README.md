# LilyGo T-Display-S3 AMOLED Plus — MicroPython firmware

Custom MicroPython firmware for the LilyGo T-Display-S3 AMOLED Plus Touch board,
with RM67162 display and CST816T touch drivers as a built-in `amoled` module.

## Contents

- `firmware/firmware.bin` — pre-built flashable MicroPython firmware
- `main.py` — demo: touch drawing palette + side button display on/off
- `builder/` — Docker-based firmware builder and C driver sources
- `tools/image_to_bin.py` — PNG/JPG → AMG0 RGB565 converter for fast `draw_image()`

## Hardware

- Board: LilyGo T-Display-S3 AMOLED Plus Touch
- MCU: ESP32-S3R8, 16MB flash, 8MB Octal PSRAM
- Display: RM67162 AMOLED, SPI, 536 × 240
- Touch: CST816T, I2C (address 0x15)

## Quick start (macOS)

```bash
# Flash the firmware
esptool --chip esp32s3 -p /dev/cu.usbmodem101 -b 460800 --before default-reset \
  --after hard-reset write-flash -z --flash-mode dio --flash-freq 80m \
  0x0 firmware/firmware.bin

# Upload the demo and reset
mpremote connect /dev/cu.usbmodem101 cp main.py :main.py
mpremote connect /dev/cu.usbmodem101 reset
```

If the port differs:
```bash
ls /dev/cu.usbmodem* /dev/tty.usbmodem*
```

If the MicroPython filesystem is corrupted after an old firmware, erase first:
```bash
esptool --chip esp32s3 -p /dev/cu.usbmodem101 erase-flash
# then re-flash firmware and upload main.py
```

## Demo

`main.py` boots into a touch drawing app:

- Touch the color palette at the top to switch colors
- Touch below the palette to draw 9×9 blocks
- Press the orange circle on the right edge to toggle display on/off

## MicroPython API

```python
import amoled

amoled.WIDTH      # 536
amoled.HEIGHT     # 240
amoled.scan_i2c() # e.g. [0x15, 0x51, 0x6b]
```

### Display

```python
d = amoled.Display()
d.clear(color)                         # fill entire screen
d.pixel(x, y, color)                   # single pixel
d.line(x0, y0, x1, y1, color)          # line
d.rect(x0, y0, x1, y1, color)          # empty rectangle (absolute coords)
d.fill_rect(x0, y0, x1, y1, color)     # filled rectangle, clipped to display
d.text("HELLO", x, y, color)           # 5×7 font, transparent background
d.text("HELLO", x, y, color, scale)    # scaled
d.text("HELLO", x, y, color, scale, bg)# with background color, RGB565
d.blit(buffer, x0, y0, x1, y1)         # RGB565 buffer blit
d.draw_image("image.bin", x, y)        # AMG0-header RGB565 image
d.draw_image("raw.bin", x, y, w, h)    # raw RGB565, no header
d.brightness(0..255)
d.sleep()
d.wake()
d.rotation(0..3)
d.width()
d.height()
```

### Colors (RGB565)

```python
BLACK = 0x0000
WHITE = 0xFFFF
RED   = 0xF800
GREEN = 0x07E0
BLUE  = 0x001F
```

RGB565 formula: `((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)`

### Touch

```python
t = amoled.Touch()
t.read()      # None or (x, y, event)
t.touched()   # IRQ state
t.raw()       # raw CST816 register bytes
t.home()      # orange side touch button
```

The orange circle on the right edge of the display is not a GPIO button — it is
a capacitive "home" area on the CST816T. Use `touch.home()` to detect it.

### Display on/off with the side button

```python
import amoled
import time

d = amoled.Display()
t = amoled.Touch()

screen_on = True
last_home = time.ticks_ms()

while True:
    if t.home() and time.ticks_diff(time.ticks_ms(), last_home) > 500:
        screen_on = not screen_on
        last_home = time.ticks_ms()
        if screen_on:
            d.wake()
            d.brightness(220)
        else:
            d.sleep()
    time.sleep_ms(20)
```

The 500 ms debounce prevents rapid on/off cycling from a single long touch.

## Displaying images from `.bin` files

AMG0 format — the fastest way to show images:

```
byte 0..3:  AMG0 magic
byte 4..5:  width  uint16 LE
byte 6..7:  height uint16 LE
byte 8..:   RGB565 pixels uint16 LE, row-major
```

Convert with the included tool:

```bash
python3 tools/image_to_bin.py image.png image_landscape.bin --orientation landscape
python3 tools/image_to_bin.py image.png image_portrait.bin --orientation portrait
```

Optional fitting modes:

```bash
python3 tools/image_to_bin.py image.png image.bin --orientation landscape --fit contain
python3 tools/image_to_bin.py image.png image.bin --orientation landscape --fit cover
python3 tools/image_to_bin.py image.png image.bin --orientation landscape --fit stretch
```

Upload to the board:

```bash
mpremote connect /dev/cu.usbmodem101 cp image.bin :image.bin
```

Draw from MicroPython:

```python
d = amoled.Display()
d.draw_image("image.bin", 0, 0)
```

## Building the firmware

Requires Docker.

```bash
cd builder
./build.sh
```

Output: `builder/build-out/firmware.bin`

## C driver sources

```
builder/modules/amoled/rm67162.c      # display driver
builder/modules/amoled/cst816.c       # touch driver
builder/modules/amoled/amoledmodule.c # MicroPython binding
builder/modules/amoled/board_pins.h   # pin mapping
```
