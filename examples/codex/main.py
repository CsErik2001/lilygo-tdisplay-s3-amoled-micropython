"""Codex usage monitor for LilyGo T-Display-S3 AMOLED Plus (536x240).

Apple-style UI on a retained RGB565 canvas: SF Compact large title,
grouped inset list with hairline separators, chevron rows, blue text
actions and animated Activity-style rings instead of bars. The living
mascot mirrors Codex: it types while Codex works, spins while loading,
cheers on fresh data and suffers through the limit row by row.

Requires firmware with ``amoled.fill_arc``, ``amoled.blit_rgb565``,
``amoled.blend_a4`` and ``amoled.blend_rgb565_a4`` plus frozen
``amoled_assets`` / ``amoled_canvas``. Assets come from
``assets.manifest.json`` (``tools/amoled_assets.py build``)::

    mpremote connect /dev/cu.usbmodem101 cp examples/codex/codex_usage.py :codex_usage.py
    mpremote connect /dev/cu.usbmodem101 cp examples/codex/connect_wifi.py :connect_wifi.py
    for f in examples/codex/assets_tgi/*; do \\
      mpremote connect /dev/cu.usbmodem101 cp "$f" :"$f##*/"; done
    mpremote connect /dev/cu.usbmodem101 cp examples/codex/main.py :main.py
    mpremote connect /dev/cu.usbmodem101 reset
"""

import time

import amoled
import amoled_ui as ui

import amoled_assets as assets
import amoled_canvas as cv

import codex_usage
import connect_wifi

POLL_INTERVAL_MS = 60000
BOOT_WIFI_TIMEOUT_MS = 12000
WORK_DELTA_PCT = 0.05
WORK_HOLD_MS = 45000

# iOS dark grouped-list palette, opaque RGB565.
SEPARATOR = amoled.rgb(56, 56, 58)
TRACK = amoled.rgb(44, 44, 46)
RING_5H = amoled.rgb(250, 17, 79)
RING_WEEK = amoled.rgb(48, 219, 91)

# Mood -> (step_ms, [(frame, dx, dy)], once). Each mood plays its full
# sprite-sheet row. once "auto" plays once, then work-or-idle.
POSES = {
    "work": (130, [("work0", 0, 0), ("work1", 0, -2), ("work2", 0, 0),
                   ("work3", 0, -1), ("work4", 0, -2), ("work5", 0, 0),
                   ("work1", 0, 1)], None),
    "idle": (300, [("idle", 0, 0), ("idle2", 0, 0), ("idle3", 0, 0),
                   ("sleep", 0, 1), ("idle4", 0, 0), ("idle5", 0, 0),
                   ("idle6", 0, 0), ("idle", 0, 0)], None),
    "cheer": (120, [("happy", 0, 0), ("jump0", 0, -2), ("jump1", 0, -5),
                    ("jump2", 0, -3), ("jump3", 0, -5), ("jump4", 0, -1)],
              "auto"),
    "spin": (100, [("spin%d" % i, 0, 0) for i in range(8)], None),
    "stress": (220, [("stress0", 0, 0), ("stress1", 0, 0), ("dead", 0, 0),
                     ("stress3", 0, 0), ("stress4", 0, 0),
                     ("stress5", 0, 0), ("stress6", 0, 0),
                     ("stress7", 0, 0)], None),
    "think": (450, [("think0", 0, 0), ("think", 0, 1), ("think2", 0, 0),
                    ("think3", 0, 1), ("think4", 0, 0),
                    ("think5", 0, 1)], None),
    "wave": (160, [("wave0", 0, 0), ("wave1", 0, -1),
                   ("wave2", 0, -1), ("wave3", 0, 0)], "auto"),
}

PET_W = 104
PET_H = 116


class Pet(cv.Widget):
    """Animated sprite with position offsets inside its own box."""

    def __init__(self, x, y):
        super().__init__(x, y, PET_W, PET_H, enabled=False)
        self.frame = None
        self.dx = 0
        self.dy = 0

    def set_pose(self, image, dx, dy):
        dx = int(dx)
        dy = int(dy)
        if image is not self.frame or dx != self.dx or dy != self.dy:
            self.frame = image
            self.dx = dx
            self.dy = dy
            self.invalidate()

    def draw(self, canvas, theme):
        canvas.fill_rect(self.x, self.y, self.x1, self.y1, cv.BLACK)
        if self.frame is not None:
            self.frame.draw(canvas, self.x + 4 + self.dx,
                            self.y + 6 + self.dy)
        self.dirty = False


class Rings(cv.Widget):
    """Two concentric Activity-style rings with a center value."""

    def __init__(self, x, y, size, font_value, font_detail):
        super().__init__(x, y, size, size, enabled=False)
        self.font_value = font_value
        self.font_detail = font_detail
        self.center = size // 2
        self.radius_outer = size // 2 - 4
        self.thickness = 13
        self.radius_inner = self.radius_outer - self.thickness - 4
        self.targets = [0.0, 0.0]
        self.shown = [0.0, 0.0]
        self.center_text = "--"

    def set_values(self, frac_5h, frac_week, center_text):
        frac_5h = max(0.0, min(1.0, float(frac_5h)))
        frac_week = max(0.0, min(1.0, float(frac_week)))
        if (frac_5h, frac_week) != tuple(self.targets):
            self.targets = [frac_5h, frac_week]
            self.invalidate()
        if center_text != self.center_text:
            self.center_text = str(center_text)
            self.invalidate()

    def tick(self, now):
        changed = False
        for i in range(2):
            diff = self.targets[i] - self.shown[i]
            if abs(diff) > 0.001:
                # Full sweep in ~700 ms, frame-rate independent.
                step = max(0.004, min(abs(diff), 0.05))
                self.shown[i] += step if diff > 0 else -step
                changed = True
        if changed:
            self.invalidate()
        return changed

    def _ring(self, canvas, radius, frac, color):
        cx = self.x + self.center
        cy = self.y + self.center
        canvas.native_arc(cx, cy, radius, 0, 360, TRACK,
                          thickness=self.thickness, end_caps=True)
        if frac > 0.004:
            canvas.native_arc(cx, cy, radius, 0, 360.0 * frac, color,
                              thickness=self.thickness, end_caps=True)

    def draw(self, canvas, theme):
        canvas.fill_rect(self.x, self.y, self.x1, self.y1, cv.BLACK)
        self._ring(canvas, self.radius_outer, self.shown[0], RING_5H)
        self._ring(canvas, self.radius_inner, self.shown[1], RING_WEEK)
        cx = self.x + self.center
        self.font_value.draw_centered(canvas, self.center_text, cx,
                                      self.y + self.center - 30, theme.foreground)
        self.font_detail.draw_centered(canvas, "LEFT", cx,
                                       self.y + self.center + 24, theme.muted)
        self.dirty = False


class SettingsRow(cv.Widget):
    """iOS Settings-style cell: title left, value + chevron right."""

    def __init__(self, x, y, width, height, font, title, value="",
                 detail=None, chevron=False, on_click=None,
                 background=None, sep=False, tint=None, centered=False,
                 visible=True):
        super().__init__(x, y, width, height, visible=visible,
                         enabled=on_click is not None)
        self.font = font
        self.title = str(title)
        self.value = str(value)
        self.detail = detail if detail is None else str(detail)
        self.chevron = bool(chevron)
        self.on_click = on_click
        self.background = background
        self.sep = bool(sep)
        self.tint = tint
        self.centered = bool(centered)
        self.pressed = False

    def set_value(self, value):
        value = str(value)
        if value != self.value:
            self.value = value
            self.invalidate()

    def set_detail(self, detail):
        detail = str(detail)
        if detail != self.detail:
            self.detail = detail
            self.invalidate()

    def _set_pressed(self, value):
        value = bool(value)
        if value != self.pressed:
            self.pressed = value
            self.invalidate()

    def draw(self, canvas, theme):
        bg = theme.surface if self.background is None else self.background
        if self.pressed:
            bg = theme.surface_pressed
        canvas.fill_rect(self.x, self.y, self.x1, self.y1, bg)
        color = theme.foreground
        mid = self.y + self.height // 2
        right = self.x1
        if self.chevron:
            self.font.draw(canvas, ">", right - 14,
                           mid - self.font.line_height // 2, theme.muted)
            right -= 26
        if self.detail is None:
            if self.centered:
                self.font.draw_centered(
                    canvas, self.title, self.x + self.width // 2,
                    mid - self.font.line_height // 2,
                    theme.accent if self.tint is None else self.tint)
            else:
                self.font.draw(canvas, self.title, self.x,
                               mid - self.font.line_height // 2, color)
                width, _ = self.font.measure(self.value)
                self.font.draw(canvas, self.value, right - width,
                               mid - self.font.line_height // 2, theme.muted)
            if self.sep:
                canvas.fill_rect(self.x + 12, self.y1, self.x1, self.y1,
                                 SEPARATOR)
            self.dirty = False
            return
        self.font.draw(canvas, self.title, self.x, self.y + 1, color)
        width, _ = self.font.measure(self.value)
        self.font.draw(canvas, self.value, right - width,
                       self.y + 1, theme.muted)
        self.font.draw(canvas, self.detail, self.x,
                       self.y + self.height - self.font.line_height - 3,
                       theme.muted)
        if self.sep:
            canvas.fill_rect(self.x + 12, self.y1, self.x1, self.y1,
                             SEPARATOR)
        self.dirty = False

    def pointer_down(self, x, y):
        self._set_pressed(self.contains(x, y))

    def pointer_move(self, x, y):
        self._set_pressed(self.contains(x, y))

    def pointer_up(self, x, y):
        activate = self.pressed and self.contains(x, y)
        self._set_pressed(False)
        if activate and self.on_click is not None:
            self.on_click()


def _fmt_pct(value):
    return "{}%".format(int(value + 0.5))


def main():
    display = amoled.Display()
    display.brightness(220)
    touch = amoled.Touch()

    font_title = assets.Font("/ui_title.tgf")
    font_body = assets.Font("/ui_body.tgf")
    font_value = assets.Font("/ui_value.tgf")
    font_detail = assets.Font("/ui_detail.tgf")

    frames = {}
    for name in ("idle", "idle2", "idle3", "idle4", "idle5", "idle6",
                 "sleep", "work0", "work1", "work2", "work3", "work4",
                 "work5", "dead", "think", "think0", "think2", "think3",
                 "think4", "think5", "happy", "jump0", "jump1", "jump2",
                 "jump3", "jump4", "stress0", "stress1", "stress3",
                 "stress4", "stress5", "stress6", "stress7",
                 "spin0", "spin1", "spin2", "spin3", "spin4", "spin5",
                 "spin6", "spin7", "wave0", "wave1", "wave2", "wave3"):
        frames[name] = assets.Image("/mascot_%s.tgi" % name)

    theme = cv.Theme()
    screen = cv.Screen(display, touch, theme=theme)

    # ---- navigation title + status ----
    screen.add(cv.Label("Codex", 16, 8, 220, 36,
                        font_title, background=cv.BLACK))
    plan_label = screen.add(cv.Label("TEAM", 380, 12, 140, 20,
                                     font_detail, color=theme.muted,
                                     background=cv.BLACK, align="right"))
    status = screen.add(cv.Label("Starting...", 16, 46, 160, 20,
                                 font_detail, background=cv.BLACK))

    # ---- pet ----
    mascot = screen.add(Pet(16, 72))
    mood_cap = screen.add(cv.Label("...", 10, 190, 116, 20,
                                   font_detail, color=theme.muted,
                                   background=cv.BLACK, align="center"))

    # ---- activity rings ----
    rings = screen.add(Rings(183, 45, 170, font_value, font_detail))

    # ---- grouped inset list ----
    screen.add(cv.Card(361, 48, 167, 184, color=theme.surface, radius=16))
    row_5h = screen.add(SettingsRow(373, 54, 143, 44, font_body, "5-Hour",
                                    value="--", detail="--",
                                    background=theme.surface, sep=True))
    row_week = screen.add(SettingsRow(373, 100, 143, 44, font_body, "Weekly",
                                      value="--", detail="--",
                                      background=theme.surface, sep=True))
    row_wifi = screen.add(SettingsRow(373, 150, 143, 36, font_body, "Wi-Fi",
                                      value="", detail="", chevron=True,
                                      background=theme.surface, sep=True))
    row_refresh = screen.add(SettingsRow(373, 190, 143, 30, font_body,
                                         "Refresh", value="",
                                         background=theme.surface,
                                         centered=True))

    state = {
        "auth": codex_usage.load_auth(),
        "summary": None,
        "refresh_now": False,
        "wifi_now": False,
        "mood": "wave",
        "frame_idx": 0,
        "frame_at": 0,
        "last_primary": None,
        "working_until": 0,
    }

    MOOD_CAPTIONS = {
        "think": "hmm...",
        "work": "working...",
        "idle": "idle",
        "cheer": ":)",
        "spin": "loading...",
        "stress": "limit hit",
        "wave": "hello!",
    }

    def set_status(text, color=None):
        status.set_text(text)
        if color is not None:
            status.color = color
            status.invalidate()

    def set_mood(mood):
        state["mood"] = mood
        state["frame_idx"] = 0
        state["frame_at"] = 0
        mood_cap.set_text(MOOD_CAPTIONS.get(mood, mood))

    def fallback_mood():
        now = time.ticks_ms()
        if time.ticks_diff(state["working_until"], now) > 0:
            return "work"
        return "idle"

    def tick_mascot():
        now = time.ticks_ms()
        mood = state["mood"]
        if mood == "work" and time.ticks_diff(state["working_until"], now) <= 0:
            set_mood("idle")
            return
        step, seq, once = POSES[mood]
        if state["frame_idx"] >= len(seq):
            state["frame_idx"] = 0
        if state["frame_at"] == 0 or time.ticks_diff(now, state["frame_at"]) >= step:
            if state["frame_at"] != 0:
                nxt = state["frame_idx"] + 1
                if nxt >= len(seq):
                    if once == "auto":
                        set_mood(fallback_mood())
                        return
                    nxt = 0
                state["frame_idx"] = nxt
            state["frame_at"] = now
            name, dx, dy = seq[state["frame_idx"]]
            mascot.set_pose(frames[name], dx, dy)

    def wifi_ssid():
        try:
            saved = connect_wifi.load_saved()
            if saved[0]:
                return saved[0][:16]
        except Exception:
            pass
        return "Not Connected"

    def apply_summary(summary):
        rings.set_values(summary["primary_used"] / 100.0,
                         summary["secondary_used"] / 100.0,
                         _fmt_pct(summary["primary_left"]))
        row_5h.set_value(_fmt_pct(summary["primary_left"]))
        row_5h.set_detail("Resets in " + summary["primary_reset_in"])
        row_week.set_value(_fmt_pct(summary["secondary_left"]))
        row_week.set_detail("Resets in " + summary["secondary_reset_in"])
        row_wifi.set_detail(wifi_ssid())
        now_tm = time.localtime()
        plan_label.set_text("{} | {:02d}:{:02d}".format(
            summary["plan"].upper(), now_tm[3], now_tm[4]))
        now = time.ticks_ms()
        if summary["limited"]:
            set_mood("stress")
            set_status("LIMIT REACHED", theme.danger)
            return
        prev = state["last_primary"]
        if prev is not None and summary["primary_used"] > prev + WORK_DELTA_PCT:
            state["working_until"] = time.ticks_add(now, WORK_HOLD_MS)
        state["last_primary"] = summary["primary_used"]
        if time.ticks_diff(state["working_until"], now) > 0:
            set_status("OK - working", theme.success)
        else:
            set_status("OK", theme.success)
        set_mood("cheer")

    def poll(reason=""):
        if not connect_wifi.is_connected():
            set_status("NO WIFI", theme.warning)
            set_mood("think")
            row_wifi.set_detail("Not Connected")
            return
        if state["auth"] is None:
            state["auth"] = codex_usage.load_auth()
        if state["auth"] is None:
            set_status("NO AUTH", theme.danger)
            set_mood("stress")
            return
        set_status("Updating...", theme.muted)
        set_mood("spin")
        screen.draw()
        try:
            payload = codex_usage.get_usage(state["auth"])
        except Exception as error:
            set_status("ERR", theme.danger)
            mood_cap.set_text(str(error)[:20])
            set_mood("stress")
            return
        try:
            import gc

            gc.collect()
        except Exception:
            pass
        summary = codex_usage.summarize(payload)
        state["summary"] = summary
        apply_summary(summary)

    def on_refresh():
        state["refresh_now"] = True

    def on_wifi():
        state["wifi_now"] = True

    row_wifi.on_click = on_wifi
    row_refresh.on_click = on_refresh
    row_wifi.enabled = True
    row_refresh.enabled = True
    row_wifi.set_detail(wifi_ssid())

    set_status("WiFi...", theme.muted)
    screen.draw()
    if not connect_wifi.is_connected():
        connect_wifi.autoconnect(timeout_ms=BOOT_WIFI_TIMEOUT_MS)
    screen.draw()
    poll("boot")

    last_poll = time.ticks_ms()
    home_last = time.ticks_ms()
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

        if state["wifi_now"]:
            state["wifi_now"] = False
            connect_wifi.run(display, touch, theme=ui.Theme())
            state["auth"] = codex_usage.load_auth()
            row_wifi.set_detail(wifi_ssid())
            screen.refresh()
            screen.draw()
            last_poll = time.ticks_ms()
            poll("wifi")

        if state["refresh_now"]:
            state["refresh_now"] = False
            last_poll = time.ticks_ms()
            poll("manual")

        if time.ticks_diff(now, last_poll) >= POLL_INTERVAL_MS:
            last_poll = now
            poll("auto")

        tick_mascot()
        rings.tick(now)
        screen.update()
        time.sleep_ms(10)


main()
