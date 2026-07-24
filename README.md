# LilyGo T-Display-S3 AMOLED Plus - MicroPython firmware

Custom MicroPython 1.28.0 firmware for the LilyGo T-Display-S3 AMOLED Plus
Touch board. It includes native RM67162 display, CST816T touch, PCF85063 RTC,
and BQ25896 battery-charger drivers in the built-in `amoled` module, plus the
frozen `amoled_ui` widget toolkit.

## Contents

- `firmware/firmware.bin` - pre-built, flashable firmware
- `amoled_ui.py` - frozen touch UI toolkit source
- `examples/draw/main.py` - drawing palette, RTC clock, and side-button demo
- `examples/widgets/main.py` - input, keyboard, button, switch, checkbox, and slider demo
- `examples/sandbox.py` - widget playground including `ProgressBar`
- `examples/wifi/` - Wi-Fi selection and password-entry flow
- `builder/` - Docker firmware builder, board definition, and native drivers
- `tools/image_to_bin.py` - PNG/JPG to AMG0 RGB565 converter

## Hardware and software

- Board: LilyGo T-Display-S3 AMOLED Plus Touch
- MCU: ESP32-S3R8, 16 MB flash, 8 MB Octal PSRAM
- Display: RM67162 AMOLED, SPI, 536 x 240
- Touch: CST816T, I2C address `0x15`
- External RTC: PCF85063-compatible, I2C address `0x51`
- Battery charger/PMU: TI BQ25896, I2C address `0x6b`
- MicroPython: `v1.28.0`
- ESP-IDF: `v5.5.1`

## Quick start (macOS)

Install `esptool` and `mpremote`, connect the board, then flash the pre-built
firmware:

```bash
esptool --chip esp32s3 -p /dev/cu.usbmodem101 -b 460800 --before default-reset \
  --after hard-reset write-flash -z --flash-mode dio --flash-freq 80m \
  0x0 firmware/firmware.bin
```

Upload and start the drawing demo:

```bash
mpremote connect /dev/cu.usbmodem101 cp examples/draw/main.py :main.py
mpremote connect /dev/cu.usbmodem101 reset
```

Other examples:

```bash
# Widget demo
mpremote connect /dev/cu.usbmodem101 cp examples/widgets/main.py :main.py

# Full widget playground, including ProgressBar
mpremote connect /dev/cu.usbmodem101 cp examples/sandbox.py :main.py

# Wi-Fi demo: connect_wifi.py remains a filesystem module
mpremote connect /dev/cu.usbmodem101 cp examples/wifi/connect_wifi.py :connect_wifi.py
mpremote connect /dev/cu.usbmodem101 cp examples/wifi/main.py :main.py

mpremote connect /dev/cu.usbmodem101 reset
```

`amoled_ui` is frozen into the firmware and does not need to be copied to the
device filesystem. A filesystem copy takes precedence over the frozen module.
Remove stale development copies after flashing a newer firmware:

```bash
mpremote connect /dev/cu.usbmodem101 rm :amoled_ui.py
```

Find a different serial port with:

```bash
ls /dev/cu.usbmodem* /dev/tty.usbmodem*
```

If an old firmware left an incompatible filesystem, erase and flash again:

```bash
esptool --chip esp32s3 -p /dev/cu.usbmodem101 erase-flash
```

## Native `amoled` API

The built-in module exposes the display, touch controller, external RTC,
BQ25896 PMU, RGB565 conversion, and shared I2C scanning:

```python
import amoled

amoled.WIDTH       # physical landscape width: 536
amoled.HEIGHT      # physical landscape height: 240
amoled.rgb(0, 180, 255)
amoled.scan_i2c()  # for example: [0x15, 0x51, 0x6b]

display = amoled.Display()
# For screenshots, allocate an optional PSRAM-backed shadow framebuffer instead:
# display = amoled.Display(framebuffer=True)
touch = amoled.Touch()
rtc = amoled.RTC()
pmu = amoled.PMU()
```

`Display()`, `Touch()`, `RTC()`, and `PMU()` initialize their hardware and
raise `OSError` if initialization fails. The display uses SPI; touch, RTC, and
PMU share a mutex-protected I2C0 bus at 400 kHz. Enabling the display
framebuffer requires approximately 251 KiB of PSRAM and raises `MemoryError`
if that allocation fails.

### Display

All rectangle endpoints are inclusive: `(x0, y0, x1, y1)`. Colors are RGB565
integers, normally created with `amoled.rgb()`.

```python
d = amoled.Display()

d.clear(color)
d.pixel(x, y, color)
d.line(x0, y0, x1, y1, color)
d.rect(x0, y0, x1, y1, color)
d.fill_rect(x0, y0, x1, y1, color)

d.text("HELLO", x, y, color)
d.text("HELLO", x, y, color, scale)
d.text("HELLO", x, y, color, scale, background)

d.blit(buffer, x0, y0, x1, y1)
d.draw_image("image.bin", x, y)
d.draw_image("raw.bin", x, y, width, height)

d.brightness(220)  # expected range: 0..255
d.sleep()
d.wake()
d.rotation(0)      # accepted values: 0, 1, 2
d.width()
d.height()

d.framebuffer()       # current screenshot-buffer state
d.framebuffer(True)   # allocate in PSRAM and clear the display to black
d.framebuffer(False)  # release the allocation
d.capture()           # raw little-endian RGB565 bytes
d.screenshot("screen.bmp")

amoled.Display.WIDTH   # physical constant: 536
amoled.Display.HEIGHT  # physical constant: 240
```

Rotation and logical dimensions:

| Rotation | Orientation | `width()` x `height()` |
| --- | --- | --- |
| `0` | default landscape | `536 x 240` |
| `1` | portrait | `240 x 536` |
| `2` | inverted landscape | `536 x 240` |

Rotation `3` is intentionally rejected; the driver supports only the three
orientations listed above. `Touch.read()` coordinates are transformed to match
the active display rotation.

Drawing bounds behavior:

- `fill_rect()` reorders reversed corners, clips partially visible rectangles,
  and ignores fully off-screen rectangles.
- `pixel()`, `line()`, `rect()`, and `text()` skip off-screen pixels safely.
- `blit()` and `draw_image()` require the complete target rectangle/image to
  fit on screen and raise `ValueError` otherwise.
- A `blit()` buffer must contain exactly
  `(x1 - x0 + 1) * (y1 - y0 + 1)` little-endian RGB565 words, or twice that
  number of bytes; a different size raises `ValueError`.

`brightness()` writes an 8-bit hardware register directly; it does not clamp
or validate its argument. Pass values in the documented `0..255` range.

The built-in text renderer uses a 5 x 7 font with a 6 x 8 cell per character.
`scale` enlarges both dimensions. Lowercase ASCII is rendered as uppercase;
unsupported characters are rendered as `?`. Newline (`\n`) advances to the
next 8-pixel text row, and the optional background paints each character cell.

`draw_image(path, x, y)` reads the dimensions from an AMG0 header.
`draw_image(path, x, y, width, height)` treats the file as raw little-endian
RGB565 data. Images are streamed one row at a time rather than loaded fully
into RAM.

### Screenshots

The RM67162 connection is write-only, so screenshots use an optional shadow
framebuffer rather than reading pixels back from the panel. Enable it when
constructing the display:

```python
import amoled

display = amoled.Display(framebuffer=True)

# Draw normally using clear(), text(), shapes, blit(), draw_image(), or the
# amoled_ui widget toolkit.
display.screenshot("screen.bmp")
```

`screenshot(path)` streams a standard 24-bit BMP to the MicroPython
filesystem. It uses only small row buffers during conversion and does not
allocate a second complete frame. Copy the result to a computer, for example:

```bash
mpremote connect /dev/cu.usbmodem101 cp :screen.bmp screen.bmp
```

`capture()` returns the same frame as raw, row-major, little-endian RGB565
bytes. The returned dimensions are `width()` by `height()` in the current
logical rotation. Because the returned `bytes` object is a complete copy, it
temporarily requires another approximately 251 KiB for a landscape frame.

The shadow framebuffer tracks `clear()`, `pixel()`, `line()`, `rect()`,
`fill_rect()`, `text()`, `blit()`, and `draw_image()`. It is stored in physical
panel coordinates, so both BMP and raw captures follow the active logical
rotation. Calling `framebuffer(True)` for the first time clears the panel to
black because its existing RAM cannot be read back; this establishes an exact
initial match between the panel and shadow buffer. Calling
`framebuffer(False)` releases the PSRAM allocation. `capture()` and
`screenshot()` raise `ValueError` while the framebuffer is disabled.

A complete runnable example is available in `examples/screenshot.py`.

### Colors (RGB565)

```python
BLACK = amoled.rgb(0, 0, 0)
WHITE = amoled.rgb(255, 255, 255)
RED = amoled.rgb(255, 0, 0)
GREEN = amoled.rgb(0, 255, 0)
BLUE = amoled.rgb(0, 0, 255)

d.clear(amoled.rgb(10, 10, 10))
```

`amoled.rgb(r, g, b)` accepts standard `0..255` components and returns an
RGB565 integer. Values outside this range raise `ValueError`.

`amoled.scan_i2c()` returns up to 16 detected 7-bit addresses from the shared
bus. Common results are touch `0x15`, RTC `0x51`, and PMU `0x6b`.

### Touch

```python
t = amoled.Touch()

point = t.read()  # None or rotation-adjusted (x, y, event)
t.touched()       # True while the active-low CST816 IRQ is asserted
t.raw()           # seven bytes from CST816 registers 0x00..0x06
t.home()          # separate orange side touch target
```

Touch event values follow the CST816 register map:

```python
EVENT_DOWN = 0
EVENT_UP = 1
EVENT_CONTACT = 2
```

The same constants are available as `amoled_ui.EVENT_DOWN`,
`amoled_ui.EVENT_UP`, and `amoled_ui.EVENT_CONTACT`.

The controller reports one finger. Polling can return `None` between contact
samples, and some touch sequences do not provide a final `EVENT_UP`. `Screen`
therefore keeps the active widget until its `release_ms` timeout expires.

The orange circle beside the panel is a capacitive CST816 home area, not a GPIO
button. It is outside the normal display coordinate range, so use
`touch.home()` rather than `touch.read()` for it.

### External RTC

```python
rtc = amoled.RTC()

rtc.datetime()
# (year, month, day, weekday, hour, minute, second, 0)

rtc.datetime((2026, 7, 9, 3, 12, 50, 0, 0))
rtc.is_valid()
```

Setter ranges are year `2000..2099`, month `1..12`, day `1..31`, weekday
`0..6`, hour `0..23`, minute `0..59`, and second `0..59`. The eighth tuple
item is accepted for MicroPython RTC compatibility but is not stored. Invalid
ranges raise `ValueError`; I2C failures raise `OSError`.

`is_valid()` is false when the PCF85063 oscillator-stop/voltage-low flag is
set or the RTC cannot be read. The datetime registers begin at `0x04`, unlike
the PCF8563 `0x02` layout.

### Battery charger and PMU

`amoled.PMU` controls the TI BQ25896 on the board's shared I2C bus. Creating
the object verifies the chip identity but does not change charging or input
settings.

```python
import amoled

pmu = amoled.PMU()

pmu.charging()                 # current charge-enable state
pmu.charging(False)            # disable charging
pmu.charging(True)             # enable charging

pmu.charge_current()           # configured fast-charge current, mA
pmu.charge_current(1000)       # sets and returns 960 mA
pmu.charge_voltage()           # configured regulation voltage, mV
pmu.charge_voltage(4200)       # sets and returns 4192 mV
pmu.input_current_limit(500)   # mA
pmu.input_voltage_limit(4500)  # mV, absolute VINDPM threshold

pmu.battery_voltage()          # measured VBAT, mV
pmu.bus_voltage()              # measured USB/VBUS, mV; 0 if absent
pmu.system_voltage()           # measured VSYS, mV
pmu.measured_charge_current()  # measured charging current, mA

pmu.charge_status()            # not_charging/precharge/fast_charging/done
pmu.power_status()             # source, power-good, thermal and DPM flags
pmu.faults()                   # watchdog, boost, charge, battery and NTC faults
```

`power_status()` returns `raw`, `source`, `source_code`, `charge_status`,
`charging`, `power_good`, `vbus_present`, `thermal_regulation`,
`input_voltage_limited`, `input_current_limited`, and `vsys_minimum`. Source
names are `no_input`, `usb_host_sdp`, `adapter`, `otg`, or `unknown`.

`faults()` returns `raw`, `active`, `watchdog`, `boost`, `charge`,
`charge_code`, `battery`, `ntc`, and `ntc_code`. Charge faults are `normal`,
`input`, `thermal_shutdown`, or `safety_timer`; NTC states are `normal`,
`warm`, `cool`, `cold`, `hot`, or `unknown`.

Configuration setters validate the board-safe range, round down to the nearest
hardware step, write the register, and return the actual value:

| Setting | Accepted range | Step |
| --- | ---: | ---: |
| Fast-charge current | `0`, or `64..1024 mA` | `64 mA` |
| Battery regulation voltage | `3840..4208 mV` | `16 mV` |
| USB input-current limit | `100..1500 mA` | `50 mA` |
| USB input-voltage limit | `3900..5500 mV` | `100 mV` |

Values outside these ranges raise `ValueError`; I2C and ADC timeouts raise
`OSError`. The BQ25896 supports higher register values, but this firmware uses
conservative limits for the T-Display-S3 AMOLED Plus. The selected charge
current must also be safe for the connected battery; the board cannot discover
the battery's rated charge current.

Read battery and USB voltage and inspect charging state:

```python
print("battery:", pmu.battery_voltage(), "mV")
print("USB:", pmu.bus_voltage(), "mV")
print("charging:", pmu.charge_status())
print(pmu.power_status())
```

Temporarily stop charging and restore the previous state:

```python
was_enabled = pmu.charging()
pmu.charging(False)
# Perform the operation that requires charging to be disabled.
pmu.charging(was_enabled)
```

Set a conservative current limit:

```python
actual_ma = pmu.charge_current(512)
print("charge-current limit:", actual_ma, "mA")
```

An application-controlled battery-preservation mode can lower both the charge
voltage and current, then restore the firmware's maximum board-safe values when
full capacity is needed:

```python
# Preservation mode
pmu.charge_voltage(4096)
pmu.charge_current(512)

# Restore maximum board-safe settings
pmu.charge_voltage(4208)
pmu.charge_current(1024)
```

The first voltage/current measurement can take about one second because the
driver starts a one-shot ADC conversion. Measurements made immediately after
it reuse that sample. `faults()` reads the BQ25896 fault register, whose latched
flags may change after a read. The absolute input-voltage limit register is
reset by the BQ25896 when a new input source is connected, so reapply a custom
limit after reconnecting USB.

The BQ25896 is not a fuel gauge and does not directly report battery charge
percentage. Percentage requires voltage-based estimation or a separate fuel-
gauge IC.

### Side-button sleep/wake

`Screen` does not consume the side home area. Handle it in the application:

```python
import time
import amoled

d = amoled.Display()
t = amoled.Touch()
screen_on = True
last_home = time.ticks_ms()

while True:
    now = time.ticks_ms()
    if t.home() and time.ticks_diff(now, last_home) > 500:
        last_home = now
        screen_on = not screen_on
        if screen_on:
            d.wake()
            d.brightness(220)
        else:
            d.sleep()
    time.sleep_ms(20)
```

The debounce prevents repeated toggles while the capacitive target remains
pressed.

## Frozen `amoled_ui` toolkit

`amoled_ui.py` provides reusable controls while all pixel rendering remains in
the native `amoled` driver. Widgets mark themselves dirty when their state
changes, and `Screen` redraws only dirty regions unless `refresh()` requests a
full redraw.

### Complete example

```python
import amoled
import amoled_ui as ui

display = amoled.Display()
display.brightness(220)
touch = amoled.Touch()

theme = ui.Theme(accent=amoled.rgb(0, 200, 255))
screen = ui.Screen(display, touch, theme=theme)

screen.add(ui.Title("Settings", x=10, y=8))

name = screen.add(
    ui.TextInput(x=10, y=36, width=220, placeholder="Name", max_length=24)
)

screen.add(
    ui.Button(
        "Save", x=244, y=36, width=90, height=28,
        on_click=lambda: print(name.value),
    )
)

screen.add(ui.Switch("WiFi", x=350, y=36, value=True))
screen.add(ui.Checkbox("Remember", x=350, y=70, checked=True))

progress = screen.add(
    ui.ProgressBar(
        x=350, y=144, width=160,
        min_value=0, max_value=255, value=128,
    )
)

def set_brightness(value):
    display.brightness(value)
    progress.set_value(value)

screen.add(
    ui.Slider(
        x=350, y=108, width=160,
        min_value=0, max_value=255, value=128, step=5,
        on_change=set_brightness,
    )
)

screen.set_keyboard(ui.Keyboard(x=0, y=72, width=330, height=168))
screen.run()
```

### Available UI classes

- `Theme` - shared colors and spacing
- `Widget` - base class for custom rectangular controls
- `Label` - opaque, updateable, aligned text
- `Title` - `Label` with default text scale `2`
- `Button` - pressed/disabled feedback and click callback
- `Checkbox` - labelled boolean control
- `Switch` - compact labelled on/off control
- `Slider` - clamped, stepped numeric drag control
- `ProgressBar` - read-only fill indicator with centered percentage
- `TextInput` - single-line value, placeholder, cursor, and callbacks
- `Keyboard` - letter/number touch keyboard with customizable rows
- `Screen` - widget ownership, focus, touch dispatch, popover, and dirty drawing

### Theme and common widget API

Create a theme by overriding any known property:

```python
theme = ui.Theme(
    background=amoled.rgb(0, 0, 0),
    foreground=amoled.rgb(255, 255, 255),
    accent=amoled.rgb(0, 180, 255),
)
```

Theme properties are `background`, `foreground`, `muted`, `accent`, `border`,
`control`, `control_pressed`, `control_disabled`, `input_background`,
`padding`, and `gap`. Unknown property names raise `ValueError`.

All widgets expose `x`, `y`, `width`, `height`, `x1`, `y1`, `visible`,
`enabled`, `dirty`, and their owning `screen`, plus these methods:

```python
widget.set_bounds(x, y, width, height)
widget.set_visible(True_or_False)
widget.set_enabled(True_or_False)
widget.invalidate()
widget.contains(x, y)
widget.overlaps(other_widget)
```

`Widget` can be subclassed by implementing `draw(display, theme)` and, for an
interactive control, `pointer_down(x, y)`, `pointer_move(x, y)`, and
`pointer_up(x, y)`. The class flags `focusable`, `preserve_focus`, and
`accepts_text` tell `Screen` how a custom widget participates in focus and
keyboard dispatch.

### Label and Title

```python
ui.Label(
    text, x, y, width=None, height=None,
    color=None, background=None, scale=1,
    align="left", visible=True,
)

ui.Title(text, x, y, width=None, **label_options)

label.set_text("Updated")
```

Alignment can be `left`, `center`, or `right`. An omitted width follows the
text width and changes when `set_text()` changes the content. A fixed width
clips text to the available number of glyphs.

### Button

```python
ui.Button(
    text, x, y, width, height,
    on_click=None,
    color=None, background=None, pressed_background=None, border=None,
    scale=1, visible=True, enabled=True,
)

button.set_text("Save")
```

`on_click()` is called without arguments only when press and release both
finish inside the button.

### Checkbox and Switch

```python
ui.Checkbox(
    text, x, y, width=None, height=28, checked=False,
    on_change=None, color=None, background=None,
    visible=True, enabled=True,
)

ui.Switch(
    text, x, y, width=None, height=28, value=False,
    on_change=None, color=None, background=None,
    visible=True, enabled=True,
)
```

Both controls expose `value`, `set_value(value, notify=True)`, `toggle()`, and
`set_text(text)`. `Checkbox` also exposes the read-only `checked` property and
`set_checked(checked, notify=True)`. `on_change(value)` receives a boolean.

### Slider and ProgressBar

```python
ui.Slider(
    x, y, width, height=28,
    min_value=0, max_value=100, value=0, step=1,
    on_change=None,
    background=None, track_color=None, fill_color=None, thumb_color=None,
    visible=True, enabled=True,
)

slider.set_value(value, notify=True)
```

The slider clamps values to its range and rounds them to `step` increments.
`on_change(value)` runs only when the normalized value changes.

```python
ui.ProgressBar(
    x, y, width, height=16, value=0.0,
    min_value=0, max_value=100,
    color=None, background=None, visible=True,
)

progress.set_value(85)
```

`ProgressBar` is read-only and has no touch interaction. Values are clamped to
the configured range. The fill uses `theme.accent`, the unfilled area uses
`theme.control`, and the centered label shows the normalized percentage.

### TextInput

```python
ui.TextInput(
    x, y, width, height=28,
    value="", placeholder="",
    on_change=None, on_submit=None, max_length=None,
    color=None, background=None, border=None,
    scale=1, visible=True, enabled=True, password=False,
)

input.set_value(value, notify=True)
input.insert(text)
input.backspace()
input.clear()
input.submit()
```

`on_change(value)` receives the new string. `on_submit(value)` runs when
`submit()` or the keyboard's `DONE` key is used. Long values display their
rightmost characters so newly entered text remains visible. Set
`password=True` to display the value as `*` characters.

### Keyboard

```python
ui.Keyboard(
    x, y, width, height,
    target=None, rows=None, shifted_rows=None, number_rows=None,
    mode=ui.Keyboard.MODE_LETTERS,
    gap=2, visible=True,
)

keyboard.set_target(text_input_or_none)
keyboard.set_mode(ui.Keyboard.MODE_NUMBERS)
keyboard.set_letter_rows(custom_rows, shifted_rows=custom_shifted_rows)
keyboard.set_bounds(x, y, width, height)
```

The default letter layout starts lowercase and has `123`, `BKSP`, `SPACE`,
`LOW`/`CAPS`, and `DONE` keys. Shift switches the labels and inserted values,
and remains highlighted until pressed again. Number mode includes digits and
common symbols, with an `ABC` key to return to letters.
Keyboard constants include:

```python
ui.Keyboard.MODE_LETTERS
ui.Keyboard.MODE_NUMBERS
ui.Keyboard.LETTER_ROWS
ui.Keyboard.SHIFTED_ROWS
ui.Keyboard.NUMBER_ROWS
ui.Keyboard.ACTION_NUMBERS
ui.Keyboard.ACTION_LETTERS
ui.Keyboard.ACTION_SHIFT
ui.Keyboard.ACTION_DONE
```

Custom row entries are `(label, value, weight)` tuples. Weight controls the
relative key width. Pass `rows` and `shifted_rows` to provide custom
lowercase and uppercase layouts.

### Screen, focus, and keyboard popover

```python
ui.Screen(
    display, touch,
    theme=None, background=None,
    poll_ms=10, release_ms=60, action_bar_y=8,
)

screen.add(widget)       # returns the same widget
screen.remove(widget)
screen.set_keyboard(keyboard)  # returns the same keyboard
screen.set_focus(widget_or_none)
screen.refresh()         # request a full clear/redraw
screen.draw()            # draw pending dirty widgets
screen.update()          # process once; True when touch.read() returned a point
screen.run()             # blocking event loop
```

The keyboard starts hidden after `set_keyboard()`. Focusing a `TextInput`
saves every widget's bounds and visibility, keeps the input and nearest action
`Button` in a temporary action bar, and expands the keyboard into the remaining
display height. `DONE`, `set_focus(None)`, or tapping outside restores the
original layout exactly. Change `action_bar_y` to move the temporary bar.
Only focusable widgets, currently `TextInput`, can be passed to `set_focus()`;
other widget types raise `ValueError`.

`release_ms` handles controllers that stop reporting points without a final
`EVENT_UP`. `poll_ms` controls the sleep interval used by `run()`.

The source remains ordinary Python for development, but the builder freezes it
into firmware. To test an edited version without rebuilding, copy it to the
filesystem; remember that it shadows the frozen version until removed.

## Displaying images from `.bin` files

AMG0 is a small, streamable RGB565 format:

```text
byte 0..3:  AMG0 magic
byte 4..5:  width, uint16 little-endian
byte 6..7:  height, uint16 little-endian
byte 8..:   RGB565 pixels, uint16 little-endian, row-major
```

Convert an image with Pillow or the built-in macOS `sips` tool:

```bash
python3 tools/image_to_bin.py image.png image.bin
python3 tools/image_to_bin.py image.png landscape.bin --orientation landscape
python3 tools/image_to_bin.py image.png portrait.bin --orientation portrait

python3 tools/image_to_bin.py image.png image.bin --resize 320x120
python3 tools/image_to_bin.py image.png image.bin --canvas 536x240 --fit contain
python3 tools/image_to_bin.py image.png image.bin --orientation landscape --fit cover
python3 tools/image_to_bin.py image.png image.bin --orientation landscape --fit stretch
python3 tools/image_to_bin.py image.png image.bin --rotate 90 --bg 101018
```

`--fit` accepts `contain`, `cover`, or `stretch`. `--orientation landscape` is
`536x240`; `portrait` is `240x536`. `--bg` accepts `RRGGBB` or `#RRGGBB`.

Upload and draw:

```bash
mpremote connect /dev/cu.usbmodem101 cp image.bin :image.bin
```

```python
d = amoled.Display()
d.draw_image("image.bin", 0, 0)
```

## Building the firmware

Docker is required. From the repository root:

```bash
./builder/build.sh
```

The build pins MicroPython `v1.28.0` and ESP-IDF `v5.5.1`, compiles the native
`amoled` module, freezes `amoled_ui.py`, and writes:

```text
builder/build-out/firmware.bin
```

Flash the newly built image with:

```bash
esptool --chip esp32s3 -p /dev/cu.usbmodem101 -b 460800 --before default-reset \
  --after hard-reset write-flash -z --flash-mode dio --flash-freq 80m \
  0x0 builder/build-out/firmware.bin
```

## Driver and board sources

```text
builder/modules/amoled/rm67162.c      display driver
builder/modules/amoled/cst816.c       touch and side-home driver
builder/modules/amoled/pcf85063.c     external RTC driver
builder/modules/amoled/amoled_i2c.c   shared I2C bus and board power helper
builder/modules/amoled/amoledmodule.c MicroPython native binding
builder/modules/amoled/board_pins.h   driver pin mapping

builder/boards/LILYGO_TDISPLAY_S3_AMOLED_PLUS/manifest.py
builder/boards/LILYGO_TDISPLAY_S3_AMOLED_PLUS/mpconfigboard.cmake
builder/boards/LILYGO_TDISPLAY_S3_AMOLED_PLUS/mpconfigboard.h
```
