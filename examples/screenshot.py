import amoled


display = amoled.Display(framebuffer=True)
display.brightness(220)

background = amoled.rgb(12, 16, 28)
accent = amoled.rgb(0, 200, 255)
white = amoled.rgb(255, 255, 255)

display.clear(background)
display.text("SCREENSHOT", 16, 16, white, 2, background)
display.fill_rect(16, 52, 220, 100, accent)
display.text("RGB565 -> BMP", 28, 70, background, 1, accent)

# Saves a standard 24-bit BMP to the MicroPython filesystem.
display.screenshot("screenshot.bmp")

# Raw little-endian RGB565 data is also available when a host-side encoder or
# network transfer is more useful. Its dimensions are display.width() and
# display.height() in the active rotation.
raw_rgb565 = display.capture()
print(
    "saved screenshot.bmp:",
    display.width(),
    "x",
    display.height(),
    "-",
    len(raw_rgb565),
    "RGB565 bytes",
)
