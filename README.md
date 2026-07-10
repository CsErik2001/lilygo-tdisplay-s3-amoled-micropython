# LilyGo T-Display-S3 AMOLED Plus — MicroPython firmware

Custom MicroPython firmware for the LilyGo T-Display-S3 AMOLED Plus Touch board,
with RM67162 display and CST816T touch drivers as a built-in `amoled` module.

## Contents

- `firmware/firmware.bin` — pre-built flashable MicroPython firmware
- `examples/draw/main.py` — touch drawing palette demo
- `amoled_ui.py` — lightweight touch UI widgets
- `examples/widgets/main.py` — title, text input, keyboard, and button demo
- `examples/wifi/` — Wi-Fi selection and password-entry demo
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
mpremote connect /dev/cu.usbmodem101 cp examples/draw/main.py :main.py
mpremote connect /dev/cu.usbmodem101 reset
```

To try the widget demo instead:

```bash
mpremote connect /dev/cu.usbmodem101 cp examples/widgets/main.py :main.py
mpremote connect /dev/cu.usbmodem101 reset
```

`amoled_ui` is frozen into the firmware, so it does not need to be copied to
the device filesystem.

After upgrading from an older setup, remove any filesystem copy because it
takes precedence over the frozen module:

```bash
mpremote connect /dev/cu.usbmodem101 rm :amoled_ui.py
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

`examples/draw/main.py` boots into a touch drawing app:

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
d.rotation(0..2)
d.width()
d.height()
```

### Colors (RGB565)

```python
BLACK = amoled.rgb(0, 0, 0)
WHITE = amoled.rgb(255, 255, 255)
RED   = amoled.rgb(255, 0, 0)
GREEN = amoled.rgb(0, 255, 0)
BLUE  = amoled.rgb(0, 0, 255)

d.clear(amoled.rgb(10, 10, 10))
```

`amoled.rgb(r, g, b)` accepts standard `0..255` RGB values and returns the
RGB565 integer used by the display methods. Values outside this range raise
`ValueError`.

### Touch

```python
t = amoled.Touch()
t.read()      # None or display-rotation-adjusted (x, y, event)
t.touched()   # IRQ state
t.raw()       # raw CST816 register bytes
t.home()      # orange side touch button
```

The orange circle on the right edge of the display is not a GPIO button — it is
a capacitive "home" area on the CST816T. Use `touch.home()` to detect it.

### External RTC

```python
rtc = amoled.RTC()
rtc.datetime()                         # (year, month, day, weekday, hour, minute, second, 0)
rtc.datetime((2026, 7, 9, 3, 12, 50, 0, 0))
rtc.is_valid()                         # False if the RTC oscillator/voltage flag is set
```

The external RTC is a PCF85063-compatible chip at I2C address `0x51`. Its
datetime registers start at `0x04`, not the PCF8563 `0x02` offset.

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

## UI widgets

`amoled_ui.py` provides reusable controls while keeping all pixel drawing in
the native `amoled` module. Widgets redraw only after their state changes.

```python
import amoled
import amoled_ui as ui

display = amoled.Display()
touch = amoled.Touch()
screen = ui.Screen(display, touch)

screen.add(ui.Title("Settings", x=10, y=8))

name = screen.add(
    ui.TextInput(
        x=10,
        y=36,
        width=220,
        placeholder="Name",
    )
)

screen.add(
    ui.Button(
        "Save",
        x=244,
        y=36,
        width=90,
        height=28,
        on_click=lambda: print(name.value),
    )
)

screen.add(
    ui.Switch("WiFi", x=350, y=36, value=True)
)

screen.add(
    ui.Checkbox("Remember", x=350, y=70, checked=True)
)

screen.add(
    ui.Slider(
        x=350,
        y=108,
        width=160,
        min_value=0,
        max_value=255,
        value=128,
        step=5,
        on_change=display.brightness,
    )
)

screen.set_keyboard(
    ui.Keyboard(x=0, y=72, width=330, height=168)
)
screen.run()
```

Available controls:

- `Label` and `Title` for opaque, updateable text
- `Button` with pressed, disabled, and callback states
- `Checkbox` for labelled boolean choices
- `Switch` for compact on/off settings
- `Slider` with value limits, step rounding, and drag callbacks
- `TextInput` with placeholder, cursor, maximum length, and callbacks
- `Keyboard` with larger ABC keys and a separate `123` number mode
- `Theme` for shared colors, spacing, and control styling
- `Screen` for focus, touch dispatch, and dirty rendering

Tap `123` to replace the letter layout with large number keys, then tap `ABC`
to return to letters. Both layouts keep backspace and done available.

The keyboard opens automatically when a `TextInput` receives focus. The input
and the nearest action button keep their original x positions and move to the
temporary action bar at `y=8`; other widgets are hidden while the keyboard uses
the rest of the display. Tapping `DONE` or outside restores every widget's
original position, size, and visibility. Use `action_bar_y` on `Screen` to
change the action bar position.

The UI stays in Python so it can be uploaded independently from the firmware.
Rendering remains native because each widget uses the existing C display API.

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
builder/modules/amoled/pcf85063.c     # external RTC driver
builder/modules/amoled/amoled_i2c.c   # shared I2C bus helper
builder/modules/amoled/amoledmodule.c # MicroPython binding
builder/modules/amoled/board_pins.h   # pin mapping
```
