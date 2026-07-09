import time

import amoled

BLACK = 0x0000
WHITE = 0xFFFF
COLORS = [0xF800, 0x07E0, 0x001F, 0xFFE0, 0xF81F, 0x07FF, 0xFFFF]
SWATCH = 20


def palette(display):
    for i, c in enumerate(COLORS):
        x = 12 + i * SWATCH
        display.fill_rect(x, 74, x + 14, 88, c)
        display.rect(x, 74, x + 14, 88, WHITE)


def main():
    display = amoled.Display()
    display.brightness(220)
    display.clear(BLACK)
    display.text("LilyGo AMOLED", 12, 12, 0xFFFF, 2)
    display.text("touch & draw", 12, 34, 0xFFE0, 1)
    display.text("side button = display on/off", 12, 52, 0x07FF, 1)
    palette(display)

    touch = amoled.Touch()
    print("ready")

    screen_on = True
    last_home = time.ticks_ms()
    color_idx = 0

    while True:
        if touch.home() and time.ticks_diff(time.ticks_ms(), last_home) > 500:
            screen_on = not screen_on
            last_home = time.ticks_ms()
            if screen_on:
                display.wake()
                display.brightness(220)
                print("display on")
            else:
                display.sleep()
                print("display off")
            time.sleep_ms(120)
            continue

        if not screen_on:
            time.sleep_ms(30)
            continue

        point = touch.read()
        if point:
            x, y, event = point
            if y < 94:
                ci = (x - 12) // SWATCH
                if 0 <= ci < len(COLORS):
                    color_idx = ci
                    print("color", color_idx)
            else:
                bs = 4
                display.fill_rect(x - bs, y - bs, x + bs, y + bs, COLORS[color_idx])
        time.sleep_ms(10)


main()
