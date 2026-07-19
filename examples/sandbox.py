"""Widget playground — test all the things."""

import time
import amoled
import amoled_ui as ui

W = amoled.WIDTH


def main():
    display = amoled.Display()
    display.brightness(220)
    touch = amoled.Touch()
    screen = ui.Screen(display, touch, action_bar_y=2)

    screen.add(ui.Title("Widget Playground", x=10, y=8))
    screen.add(ui.Label("Slider, Checkbox, Switch, Keyboard", x=10, y=34, color=screen.theme.muted))

    bright_label = screen.add(ui.Label("220", x=W - 40, y=56, width=30, align="right"))
    screen.add(ui.Label("Brightness", x=10, y=60))
    screen.add(ui.Slider(x=10, y=78, width=W - 20, min_value=0, max_value=255, value=220,
                         on_change=lambda v: (display.brightness(v), bright_label.set_text(str(v)))))

    cb_label = screen.add(ui.Label("unchecked", x=W - 120, y=106, width=110, align="right"))
    screen.add(ui.Checkbox("Enable", x=10, y=106,
                           on_change=lambda v: cb_label.set_text("on" if v else "off")))

    sw_label = screen.add(ui.Label("off", x=W - 120, y=134, width=110, align="right"))
    screen.add(ui.Switch("Light mode", x=10, y=134,
                         on_change=lambda v: (
        setattr(screen.theme, 'background', amoled.rgb(255,255,255) if v else amoled.rgb(0,0,0)),
        setattr(screen, 'background', screen.theme.background),
        setattr(screen.theme, 'foreground', amoled.rgb(0,0,0) if v else amoled.rgb(255,255,255)),
        setattr(screen.theme, 'muted', amoled.rgb(160,160,160) if v else amoled.rgb(128,128,128)),
        setattr(screen.theme, 'control', amoled.rgb(220,220,220) if v else amoled.rgb(32,32,40)),
        setattr(screen.theme, 'border', amoled.rgb(180,180,180) if v else amoled.rgb(96,96,96)),
        setattr(screen.theme, 'input_background', amoled.rgb(240,240,240) if v else amoled.rgb(16,16,20)),
        screen.refresh(),
        sw_label.set_text("on" if v else "off"),
    )))

    screen.add(ui.ProgressBar(x=10, y=162, width=W - 20, value=64))
    inp = screen.add(ui.TextInput(x=10, y=174, width=W - 20, height=24, placeholder="Tap to type", max_length=20, scale=2))
    kb = ui.Keyboard(x=0, y=194, width=W, height=amoled.HEIGHT - 194)
    screen.set_keyboard(kb)

    home_last = 0
    screen_on = True

    while True:
        now = time.ticks_ms()
        if touch.home() and time.ticks_diff(now, home_last) > 500:
            home_last = now
            screen_on = not screen_on
            if screen_on:
                display.wake()
                display.brightness(220)
            else:
                display.sleep()
            time.sleep_ms(120)
            continue
        if not screen_on:
            time.sleep_ms(30)
            continue
        screen.update()
        time.sleep_ms(10)


main()
