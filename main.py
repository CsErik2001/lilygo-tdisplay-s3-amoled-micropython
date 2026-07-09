import time

import amoled

BLACK = 0x0000
WHITE = 0xFFFF
GRAY = 0x8410
CLR_BG = 0x4228

COLORS = [0xF800, 0x07E0, 0x001F, 0xFFE0, 0xF81F, 0x07FF, WHITE]

W = amoled.WIDTH
H = amoled.HEIGHT

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
    display.fill_rect(x0, y0, x1, y1, 0xF800 if highlight else CLR_BG)
    display.rect(x0, y0, x1, y1, GRAY)
    tx = x0 + (SWATCH_W - 3 * 5) // 2
    ty = y0 + (SWATCH_H - 7) // 2
    display.text("CLR", tx, ty, WHITE, 1)


def draw_bar(display, color_idx):
    display.fill_rect(0, BAR_Y, W - 1, H - 1, 0x2108)
    display.line(0, BAR_Y - 1, W - 1, BAR_Y - 1, 0x4208)
    for i in range(N_COLORS):
        draw_color_swatch(display, i, i == color_idx)
    draw_clear_btn(display, False)


def clear_drawing(display):
    display.fill_rect(0, 0, W - 1, BAR_Y - 2, BLACK)
    display.text("LilyGo AMOLED", 6, 6, 0xFFFF, 1)
    display.line(0, BAR_Y - 1, W - 1, BAR_Y - 1, 0x4208)
    print("cleared")


def main():
    display = amoled.Display()
    display.brightness(220)
    display.clear(BLACK)
    display.text("LilyGo AMOLED", 6, 6, 0xFFFF, 1)

    touch = amoled.Touch()
    print("ready")

    color_idx = 0
    draw_bar(display, color_idx)

    screen_on = True
    last_home = time.ticks_ms()
    last_tap = time.ticks_ms()

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
                        clear_drawing(display)
            else:
                bs = 4
                display.fill_rect(x - bs, y - bs, x + bs, y + bs, COLORS[color_idx])
        time.sleep_ms(10)


main()
