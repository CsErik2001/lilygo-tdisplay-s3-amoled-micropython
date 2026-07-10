import time

import amoled

BLACK = amoled.rgb(0, 0, 0)
WHITE = amoled.rgb(255, 255, 255)
GRAY = amoled.rgb(128, 128, 128)
CLR_BG = amoled.rgb(64, 64, 64)
BAR_BG = amoled.rgb(32, 32, 64)

COLORS = [
    amoled.rgb(255, 0, 0),
    amoled.rgb(0, 255, 0),
    amoled.rgb(0, 0, 255),
    amoled.rgb(255, 255, 0),
    amoled.rgb(255, 0, 255),
    amoled.rgb(0, 255, 255),
    WHITE,
]

W = amoled.WIDTH
H = amoled.HEIGHT

TIME_X = 6
TIME_Y = 6

BAR_Y = 200
BAR_H = 40
SWATCH_W = 55
SWATCH_H = 30
GAP = 7
SWATCH_OY = BAR_Y + (BAR_H - SWATCH_H) // 2

N_COLORS = len(COLORS)
TOTAL_ITEMS = N_COLORS + 1  # +1 clear button
TOTAL_W = TOTAL_ITEMS * SWATCH_W + (TOTAL_ITEMS - 1) * GAP
OFFSET_X = (W - TOTAL_W) // 2


def item_rect(i):
    x = OFFSET_X + i * (SWATCH_W + GAP)
    return x, SWATCH_OY, x + SWATCH_W - 1, SWATCH_OY + SWATCH_H - 1


def draw_color_swatch(display, idx, highlight):
    x0, y0, x1, y1 = item_rect(idx)
    display.fill_rect(x0, y0, x1, y1, COLORS[idx])
    if highlight:
        display.rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1, WHITE)
    else:
        display.rect(x0, y0, x1, y1, GRAY)


def draw_clear_btn(display, highlight):
    x0, y0, x1, y1 = item_rect(N_COLORS)
    display.fill_rect(x0, y0, x1, y1, COLORS[0] if highlight else CLR_BG)
    display.rect(x0, y0, x1, y1, GRAY)
    tx = x0 + (SWATCH_W - 3 * 5) // 2
    ty = y0 + (SWATCH_H - 7) // 2
    display.text("CLR", tx, ty, WHITE, 1)


def draw_bar(display, color_idx):
    display.fill_rect(0, BAR_Y, W - 1, H - 1, BAR_BG)
    display.line(0, BAR_Y - 1, W - 1, BAR_Y - 1, CLR_BG)
    for i in range(N_COLORS):
        draw_color_swatch(display, i, i == color_idx)
    draw_clear_btn(display, False)


def format_datetime(rtc):
    if rtc is None:
        return "--.-- --:--:--"

    try:
        year, month, day, weekday, hour, minute, second, subsecond = rtc.datetime()
    except OSError as exc:
        print("rtc read failed", exc)
        return "--.-- --:--:--"

    return "{:02d}.{:02d} {:02d}:{:02d}:{:02d}".format(
        month, day, hour, minute, second
    )


def draw_datetime(display, rtc):
    display.text(format_datetime(rtc), TIME_X, TIME_Y, WHITE, 1, BLACK)


def clear_drawing(display, rtc):
    display.fill_rect(0, 0, W - 1, BAR_Y - 2, BLACK)
    draw_datetime(display, rtc)
    display.line(0, BAR_Y - 1, W - 1, BAR_Y - 1, CLR_BG)
    print("cleared")


def main():
    display = amoled.Display()
    display.brightness(220)
    display.clear(BLACK)

    try:
        rtc = amoled.RTC()
    except OSError as exc:
        rtc = None
        print("rtc unavailable", exc)

    draw_datetime(display, rtc)

    touch = amoled.Touch()
    print("ready")

    color_idx = 0
    draw_bar(display, color_idx)

    screen_on = True
    last_home = time.ticks_ms()
    last_tap = time.ticks_ms()
    last_clock = time.ticks_ms()

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

        now = time.ticks_ms()
        if time.ticks_diff(now, last_clock) >= 1000:
            draw_datetime(display, rtc)
            last_clock = now

        point = touch.read()
        if point and time.ticks_diff(time.ticks_ms(), last_tap) > 50:
            x, y, event = point
            last_tap = time.ticks_ms()
            if y >= BAR_Y:
                for i in range(N_COLORS):
                    x0, y0, x1, y1 = item_rect(i)
                    if x0 <= x <= x1 and y0 <= y <= y1:
                        if i != color_idx:
                            draw_color_swatch(display, color_idx, False)
                            color_idx = i
                            draw_color_swatch(display, color_idx, True)
                            print("color", color_idx)
                        break
                else:
                    cx0, cy0, cx1, cy1 = item_rect(N_COLORS)
                    if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                        clear_drawing(display, rtc)
            else:
                bs = 4
                display.fill_rect(x - bs, y - bs, x + bs, y + bs, COLORS[color_idx])
        time.sleep_ms(10)


main()
