"""WiFi connection flow — shows a full-screen setup dialog and returns when connected.

Usage::

    import amoled
    import connect_wifi as wifi

    display = amoled.Display()
    touch = amoled.Touch()
    ssid, ip = wifi.run(display, touch)
    print(f"connected to {ssid} at {ip}")
"""

import time
import network

import amoled
import amoled_ui as ui

W = amoled.WIDTH
H = amoled.HEIGHT
LIST_TOP = 68
ITEM_H = 24
MAX_VISIBLE = 7

UPPER = (
    (("Q","Q",1),("W","W",1),("E","E",1),("R","R",1),("T","T",1),
     ("Y","Y",1),("U","U",1),("I","I",1),("O","O",1),("P","P",1)),
    (("A","A",1),("S","S",1),("D","D",1),("F","F",1),("G","G",1),
     ("H","H",1),("J","J",1),("K","K",1),("L","L",1)),
    (("SHFT",ui.Keyboard.ACTION_SHIFT,2),("Z","Z",1),("X","X",1),
     ("C","C",1),("V","V",1),("B","B",1),("N","N",1),("M","M",1)),
    (("123",ui.Keyboard.ACTION_NUMBERS,2),("BKSP","\b",2),("SPACE"," ",4),("DONE","\n",2)),
)

LOWER = (
    (("Q","q",1),("W","w",1),("E","e",1),("R","r",1),("T","t",1),
     ("Y","y",1),("U","u",1),("I","i",1),("O","o",1),("P","p",1)),
    (("A","a",1),("S","s",1),("D","d",1),("F","f",1),("G","g",1),
     ("H","h",1),("J","j",1),("K","k",1),("L","l",1)),
    (("SHFT",ui.Keyboard.ACTION_SHIFT,2),("Z","z",1),("X","x",1),
     ("C","c",1),("V","v",1),("B","b",1),("N","n",1),("M","m",1)),
    (("123",ui.Keyboard.ACTION_NUMBERS,2),("BKSP","\b",2),("SPACE"," ",4),("DONE","\n",2)),
)


class _ShiftKeyboard(ui.Keyboard):
    def __init__(self, x, y, width, height, **kw):
        self._shifted = False
        kw["rows"] = LOWER
        super().__init__(x, y, width, height, **kw)

    def _toggle_shift(self):
        self._shifted = not self._shifted
        self.set_letter_rows(UPPER if self._shifted else LOWER)

    def _key_colors(self, theme, index, value):
        if value == ui.Keyboard.ACTION_SHIFT:
            if self.target is None:
                return theme.control_disabled, theme.muted
            if index == self._pressed_key:
                return theme.control_pressed, theme.foreground
            if self._shifted:
                return theme.accent, theme.foreground
            return theme.control, theme.muted
        return super()._key_colors(theme, index, value)

    def _activate_value(self, value):
        if value == ui.Keyboard.ACTION_SHIFT:
            self._toggle_shift()
        else:
            super()._activate_value(value)


def _scan():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    raw = wlan.scan()
    seen = {}
    for ap in raw:
        ssid = ap[0].decode("utf-8", "ignore") or ""
        if ssid and ssid not in seen:
            seen[ssid] = True
    return sorted(seen, key=str.lower)


def _connect(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.config(pm=0)
    except Exception:
        pass
    time.sleep_ms(500)
    if wlan.isconnected():
        wlan.disconnect()
        time.sleep_ms(500)
    wlan.connect(ssid, password)
    for _ in range(250):
        if wlan.isconnected():
            return wlan.ifconfig()[0]
        time.sleep_ms(100)
    return None


def _clear(screen):
    for w in screen.widgets:
        w.screen = None
    screen.widgets = []
    screen.focused = None
    screen.keyboard = None
    screen._active = None
    screen._full_redraw = True


def run(display, touch, theme=None):
    """Show the WiFi setup UI and return ``(ssid, ip)`` on connection."""
    if theme is None:
        theme = ui.Theme(accent=amoled.rgb(0, 200, 255))
    screen = ui.Screen(display, touch, theme=theme)

    home_last = [0]
    screen_on = [True]
    done = [False]
    result = [None]
    _clear(screen)

    while True:
        # ---------- scan ----------
        _clear(screen)
        screen.add(ui.Title("WiFi Setup", x=12, y=40))
        screen.add(ui.Label("Scanning...", x=12, y=70, width=W - 24))
        screen.draw()
        networks = _scan()
        if not networks:
            time.sleep_ms(2000)
            continue

        selected = [None]
        password_input = [None]

        def back():
            done[0] = True
            result[0] = "back"

        def do_connect():
            if selected[0] is None:
                return
            pwd = password_input[0].value if password_input[0] else ""
            _clear(screen)
            screen.add(ui.Title("Connecting...", x=12, y=40))
            screen.add(ui.Label("Please wait", x=12, y=70, width=W - 24, color=theme.muted))
            screen.draw()
            ip = _connect(selected[0], pwd)
            if ip:
                done[0] = True
                result[0] = (selected[0], ip)
            else:
                _clear(screen)
                screen.add(ui.Title("Failed", x=12, y=40, color=amoled.rgb(255, 0, 0)))
                screen.add(ui.Label(f"Could not connect to {selected[0]}", x=12, y=70, width=W - 24))
                screen.add(ui.Button("Back", x=12, y=130, width=80, height=28, on_click=back))
                selected[0] = None
                password_input[0] = None

        def on_select(ssid):
            selected[0] = ssid
            _clear(screen)
            inp_w = W - 24 - 120 - 8
            password_input[0] = ui.TextInput(x=12, y=8, width=inp_w, height=28, placeholder=ssid)
            screen.add(password_input[0])
            screen.add(ui.Button("Connect", x=12 + inp_w + 8, y=8, width=120, height=28, on_click=do_connect))
            kb = _ShiftKeyboard(x=0, y=40, width=W, height=H - 40)
            screen.set_keyboard(kb)
            screen.set_focus(password_input[0])

        # ---------- list ----------
        _clear(screen)
        t = screen.theme
        screen.add(ui.Title("WiFi Setup", x=12, y=8))
        screen.add(ui.Label(f"{len(networks)} networks", x=12, y=36, width=W - 24, scale=1, color=t.muted))
        for i, ssid in enumerate(networks[:MAX_VISIBLE]):
            screen.add(ui.Button(
                ssid, x=16, y=LIST_TOP + i * ITEM_H,
                width=W - 32, height=ITEM_H - 2,
                border=t.background, scale=1,
                on_click=lambda s=ssid: on_select(s),
            ))

        # ---------- event loop ----------
        while not done[0]:
            now = time.ticks_ms()
            if touch.home() and time.ticks_diff(now, home_last[0]) > 500:
                home_last[0] = now
                screen_on[0] = not screen_on[0]
                if screen_on[0]:
                    display.wake()
                    display.brightness(220)
                else:
                    display.sleep()
                time.sleep_ms(120)
                continue
            if not screen_on[0]:
                time.sleep_ms(30)
                continue

            screen.update()
            time.sleep_ms(10)

        if done[0]:
            if result[0] == "back":
                continue  # show scan again
            ssid, ip = result[0]
            display.clear(amoled.rgb(0, 0, 0))
            display.text("Connected!", 12, 12, amoled.rgb(0, 255, 0), 2)
            display.text(f"IP: {ip}", 12, 34, amoled.rgb(255, 255, 255), 1)
            time.sleep_ms(1500)
            return ssid, ip
