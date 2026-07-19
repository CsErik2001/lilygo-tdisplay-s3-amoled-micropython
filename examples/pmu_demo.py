"""Interactive PMU / battery dashboard — BQ25896 charger control."""

import time
import amoled
import amoled_ui as ui

W = amoled.WIDTH
GRN = amoled.rgb(0, 220, 100)
RED = amoled.rgb(255, 60, 60)


def pct(mv):
    return max(0, min(100, int((mv - 3300) * 100 // (4200 - 3300))))


def main():
    display = amoled.Display()
    display.brightness(220)
    touch = amoled.Touch()
    theme = ui.Theme(accent=GRN)
    screen = ui.Screen(display, touch, theme=theme)

    screen.add(ui.Title("Battery & Power", x=10, y=8))
    pmu = amoled.PMU()

    bat_pct_label = screen.add(ui.Label("—", x=W - 60, y=36, width=50, align="right"))
    screen.add(ui.Label("Battery", x=10, y=40))
    pb = screen.add(ui.ProgressBar(x=10, y=62, width=W - 20, value=0))

    bus_label = screen.add(ui.Label("USB: —", x=10, y=84, width=W - 20))
    sys_label = screen.add(ui.Label("System: — mV", x=10, y=104, width=W - 20))

    stat_label = screen.add(ui.Label("Charge: —", x=10, y=130, width=W - 20, color=theme.muted))

    def toggle_charging(v):
        print("toggle_charging", v)
        pmu.charging(v)
        stat_label.set_text(f"Charge: {'ON' if pmu.charging() else 'OFF'}")

    charging_enabled = pmu.charging()
    sw = screen.add(ui.Switch("Charging", x=10, y=152, value=charging_enabled,
                              on_change=toggle_charging))

    def set_current(v):
        actual = pmu.charge_current(v)
        cur_label.set_text(f"{actual} mA")

    cur_label = screen.add(ui.Label(f"{pmu.charge_current()} mA", x=W - 60, y=184, width=50, align="right"))
    screen.add(ui.Label("Charge current", x=10, y=184))
    screen.add(ui.Slider(x=10, y=206, width=W - 20, min_value=0, max_value=1024, step=64,
                         value=pmu.charge_current(), on_change=set_current))

    home_last = 0
    screen_on = True
    last_read = 0

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

        # touch + redraw first (responsive UI)
        screen.update()

        # PMU readings every 500ms (I2C reads, can be slow)
        if time.ticks_diff(now, last_read) > 500:
            last_read = now
            try:
                bat_mv = pmu.battery_voltage()
                bus_mv = pmu.bus_voltage()
                sys_mv = pmu.system_voltage()
                cs = pmu.charge_status()
                ma = pmu.measured_charge_current()

                p = pct(bat_mv)
                pb.set_value(p)
                bat_pct_label.set_text(f"{p}%")

                bus_label.set_text(f"USB: {bus_mv} mV  ({'plugged' if bus_mv > 100 else 'unplugged'})")
                sys_label.set_text(f"System: {sys_mv} mV  |  Charge: {ma} mA")
                stat_label.set_text(f"Status: {cs}")
            except Exception as e:
                stat_label.set_text(f"Error: {e}")

        time.sleep_ms(10)


main()
