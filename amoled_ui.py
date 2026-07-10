"""Small touch UI toolkit for the built-in ``amoled`` MicroPython module."""

import time

try:
    import amoled as _amoled
except ImportError:
    _amoled = None


EVENT_DOWN = 0
EVENT_UP = 1
EVENT_CONTACT = 2


def _rgb(r, g, b):
    if _amoled is not None:
        return _amoled.rgb(r, g, b)
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def _ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.monotonic() * 1000)


def _ticks_diff(new, old):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(new, old)
    return new - old


def _sleep_ms(milliseconds):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(milliseconds)
    else:
        time.sleep(milliseconds / 1000)


def _text_width(text, scale):
    return len(text) * 6 * scale


def _fit_text(text, width, scale, from_end=False):
    max_chars = max(0, width // (6 * scale))
    if len(text) <= max_chars:
        return text
    if from_end:
        return text[-max_chars:] if max_chars else ""
    return text[:max_chars]


class Theme:
    """Colors and dimensions shared by widgets on a screen."""

    def __init__(self, **overrides):
        self.background = _rgb(0, 0, 0)
        self.foreground = _rgb(255, 255, 255)
        self.muted = _rgb(128, 128, 128)
        self.accent = _rgb(0, 180, 255)
        self.border = _rgb(96, 96, 96)
        self.control = _rgb(32, 32, 40)
        self.control_pressed = _rgb(0, 110, 160)
        self.control_disabled = _rgb(48, 48, 48)
        self.input_background = _rgb(16, 16, 20)
        self.padding = 6
        self.gap = 3

        for name, value in overrides.items():
            if not hasattr(self, name):
                raise ValueError("unknown theme property: " + name)
            setattr(self, name, value)


class Widget:
    """Base class for rectangular UI elements."""

    focusable = False
    preserve_focus = False
    accepts_text = False

    def __init__(self, x, y, width, height, visible=True, enabled=True):
        if width <= 0 or height <= 0:
            raise ValueError("widget width and height must be positive")
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)
        self.visible = bool(visible)
        self.enabled = bool(enabled)
        self.dirty = True
        self.screen = None

    @property
    def x1(self):
        return self.x + self.width - 1

    @property
    def y1(self):
        return self.y + self.height - 1

    def contains(self, x, y):
        return self.x <= x <= self.x1 and self.y <= y <= self.y1

    def overlaps(self, other):
        return not (
            self.x1 < other.x
            or other.x1 < self.x
            or self.y1 < other.y
            or other.y1 < self.y
        )

    def invalidate(self):
        self.dirty = True

    def set_visible(self, visible):
        visible = bool(visible)
        if visible != self.visible:
            self.visible = visible
            if self.screen is not None:
                self.screen.refresh()

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled != self.enabled:
            self.enabled = enabled
            self.invalidate()

    def draw(self, display, theme):
        raise NotImplementedError

    def pointer_down(self, x, y):
        pass

    def pointer_move(self, x, y):
        pass

    def pointer_up(self, x, y):
        pass


class Label(Widget):
    """Opaque text label that can be updated without clearing the screen."""

    def __init__(
        self,
        text,
        x,
        y,
        width=None,
        height=None,
        color=None,
        background=None,
        scale=1,
        align="left",
        visible=True,
    ):
        self.text = str(text)
        self.scale = int(scale)
        if self.scale < 1:
            raise ValueError("scale must be at least 1")
        self._auto_width = width is None
        if width is None:
            width = max(1, _text_width(self.text, self.scale))
        if height is None:
            height = 8 * self.scale
        super().__init__(x, y, width, height, visible=visible)
        if align not in ("left", "center", "right"):
            raise ValueError("align must be left, center, or right")
        self.color = color
        self.background = background
        self.align = align

    def set_text(self, text):
        text = str(text)
        if text == self.text:
            return
        old_width = self.width
        self.text = text
        if self._auto_width:
            self.width = max(1, _text_width(self.text, self.scale))
        if self.screen is not None and self.width != old_width:
            self.screen.refresh()
        else:
            self.invalidate()

    def draw(self, display, theme):
        background = theme.background if self.background is None else self.background
        color = theme.foreground if self.color is None else self.color
        display.fill_rect(self.x, self.y, self.x1, self.y1, background)

        text = _fit_text(self.text, self.width, self.scale)
        text_width = _text_width(text, self.scale)
        if self.align == "center":
            text_x = self.x + max(0, (self.width - text_width) // 2)
        elif self.align == "right":
            text_x = self.x + max(0, self.width - text_width)
        else:
            text_x = self.x
        text_y = self.y + max(0, (self.height - 8 * self.scale) // 2)
        display.text(text, text_x, text_y, color, self.scale, background)
        self.dirty = False


class Title(Label):
    """Convenience label with a larger default scale."""

    def __init__(self, text, x, y, width=None, **kwargs):
        if "scale" not in kwargs:
            kwargs["scale"] = 2
        super().__init__(text, x, y, width=width, **kwargs)


class Button(Widget):
    """Touch button with pressed feedback and a release callback."""

    def __init__(
        self,
        text,
        x,
        y,
        width,
        height,
        on_click=None,
        color=None,
        background=None,
        pressed_background=None,
        border=None,
        scale=1,
        visible=True,
        enabled=True,
    ):
        super().__init__(x, y, width, height, visible=visible, enabled=enabled)
        self.text = str(text)
        self.on_click = on_click
        self.color = color
        self.background = background
        self.pressed_background = pressed_background
        self.border = border
        self.scale = int(scale)
        if self.scale < 1:
            raise ValueError("scale must be at least 1")
        self.pressed = False

    def set_text(self, text):
        text = str(text)
        if text != self.text:
            self.text = text
            self.invalidate()

    def draw(self, display, theme):
        if not self.enabled:
            background = theme.control_disabled
            color = theme.muted
        elif self.pressed:
            background = (
                theme.control_pressed
                if self.pressed_background is None
                else self.pressed_background
            )
            color = theme.foreground if self.color is None else self.color
        else:
            background = theme.control if self.background is None else self.background
            color = theme.foreground if self.color is None else self.color
        border = theme.border if self.border is None else self.border

        display.fill_rect(self.x, self.y, self.x1, self.y1, background)
        display.rect(self.x, self.y, self.x1, self.y1, border)
        text = _fit_text(self.text, self.width - 4, self.scale)
        text_x = self.x + max(0, (self.width - _text_width(text, self.scale)) // 2)
        text_y = self.y + max(0, (self.height - 8 * self.scale) // 2)
        display.text(text, text_x, text_y, color, self.scale, background)
        self.dirty = False

    def _set_pressed(self, pressed):
        pressed = bool(pressed)
        if pressed != self.pressed:
            self.pressed = pressed
            self.invalidate()

    def pointer_down(self, x, y):
        self._set_pressed(self.contains(x, y))

    def pointer_move(self, x, y):
        self._set_pressed(self.contains(x, y))

    def pointer_up(self, x, y):
        activate = self.pressed and self.contains(x, y)
        self._set_pressed(False)
        if activate and self.on_click is not None:
            self.on_click()


class TextInput(Widget):
    """Single-line editable text field for use with ``Keyboard``."""

    focusable = True
    accepts_text = True

    def __init__(
        self,
        x,
        y,
        width,
        height=28,
        value="",
        placeholder="",
        on_change=None,
        on_submit=None,
        max_length=None,
        color=None,
        background=None,
        border=None,
        scale=1,
        visible=True,
        enabled=True,
    ):
        super().__init__(x, y, width, height, visible=visible, enabled=enabled)
        self.value = str(value)
        self.placeholder = str(placeholder)
        self.on_change = on_change
        self.on_submit = on_submit
        self.max_length = max_length
        if self.max_length is not None and self.max_length < 0:
            raise ValueError("max_length cannot be negative")
        self.color = color
        self.background = background
        self.border = border
        self.scale = int(scale)
        if self.scale < 1:
            raise ValueError("scale must be at least 1")
        self.focused = False
        if self.max_length is not None:
            self.value = self.value[: self.max_length]

    def set_focused(self, focused):
        focused = bool(focused)
        if focused != self.focused:
            self.focused = focused
            self.invalidate()

    def set_value(self, value, notify=True):
        value = str(value)
        if self.max_length is not None:
            value = value[: self.max_length]
        if value == self.value:
            return
        self.value = value
        self.invalidate()
        if notify and self.on_change is not None:
            self.on_change(self.value)

    def insert(self, text):
        self.set_value(self.value + str(text))

    def backspace(self):
        if self.value:
            self.set_value(self.value[:-1])

    def clear(self):
        self.set_value("")

    def submit(self):
        if self.on_submit is not None:
            self.on_submit(self.value)

    def draw(self, display, theme):
        background = (
            theme.input_background if self.background is None else self.background
        )
        color = theme.foreground if self.color is None else self.color
        border = (
            theme.accent
            if self.focused
            else (theme.border if self.border is None else self.border)
        )

        display.fill_rect(self.x, self.y, self.x1, self.y1, background)
        display.rect(self.x, self.y, self.x1, self.y1, border)

        if self.value:
            text = self.value + ("_" if self.focused else "")
            text_color = color
        elif self.focused:
            text = "_"
            text_color = color
        else:
            text = self.placeholder
            text_color = theme.muted

        padding = theme.padding
        inner_width = max(0, self.width - 2 * padding)
        text = _fit_text(text, inner_width, self.scale, from_end=bool(self.value))
        text_y = self.y + max(0, (self.height - 8 * self.scale) // 2)
        display.text(
            text,
            self.x + padding,
            text_y,
            text_color,
            self.scale,
            background,
        )
        self.dirty = False


class Keyboard(Widget):
    """Compact touch keyboard that redraws only changed key cells."""

    preserve_focus = True

    DEFAULT_ROWS = (
        (
            ("1", "1", 1), ("2", "2", 1), ("3", "3", 1),
            ("4", "4", 1), ("5", "5", 1), ("6", "6", 1),
            ("7", "7", 1), ("8", "8", 1), ("9", "9", 1),
            ("0", "0", 1),
        ),
        (
            ("Q", "Q", 1), ("W", "W", 1), ("E", "E", 1),
            ("R", "R", 1), ("T", "T", 1), ("Y", "Y", 1),
            ("U", "U", 1), ("I", "I", 1), ("O", "O", 1),
            ("P", "P", 1),
        ),
        (
            ("A", "A", 1), ("S", "S", 1), ("D", "D", 1),
            ("F", "F", 1), ("G", "G", 1), ("H", "H", 1),
            ("J", "J", 1), ("K", "K", 1), ("L", "L", 1),
        ),
        (
            ("Z", "Z", 1), ("X", "X", 1), ("C", "C", 1),
            ("V", "V", 1), ("B", "B", 1), ("N", "N", 1),
            ("M", "M", 1), ("BKSP", "\b", 2),
        ),
        (("SPACE", " ", 7), ("DONE", "\n", 3)),
    )

    def __init__(
        self,
        x,
        y,
        width,
        height,
        target=None,
        rows=None,
        gap=2,
        visible=True,
    ):
        super().__init__(x, y, width, height, visible=visible)
        self.target = target
        self.rows = self.DEFAULT_ROWS if rows is None else rows
        self.gap = int(gap)
        self._keys = []
        self._pressed_key = None
        self._dirty_keys = []
        self._full_dirty = True
        self._build_keys()

    def _build_keys(self):
        self._keys = []
        row_count = len(self.rows)
        content_height = self.height - self.gap * (row_count + 1)
        y = self.y + self.gap
        remaining_height = content_height

        for row_index, row in enumerate(self.rows):
            rows_left = row_count - row_index
            key_height = remaining_height // rows_left
            content_width = self.width - self.gap * (len(row) + 1)
            remaining_width = content_width
            remaining_weight = sum(key[2] for key in row)
            x = self.x + self.gap

            for label, value, weight in row:
                key_width = remaining_width * weight // remaining_weight
                self._keys.append((x, y, key_width, key_height, label, value))
                x += key_width + self.gap
                remaining_width -= key_width
                remaining_weight -= weight

            y += key_height + self.gap
            remaining_height -= key_height

    def invalidate(self):
        self._full_dirty = True
        self._dirty_keys = []
        Widget.invalidate(self)

    def _invalidate_key(self, index):
        if index is not None and index not in self._dirty_keys:
            self._dirty_keys.append(index)
        Widget.invalidate(self)

    def set_target(self, target):
        if target is not None and not getattr(target, "accepts_text", False):
            raise ValueError("keyboard target must accept text")
        if target is not self.target:
            self.target = target
            self.invalidate()

    def _key_at(self, x, y):
        for index, key in enumerate(self._keys):
            key_x, key_y, width, height = key[:4]
            if key_x <= x < key_x + width and key_y <= y < key_y + height:
                return index
        return None

    def _draw_key(self, display, theme, index):
        x, y, width, height, label, value = self._keys[index]
        pressed = index == self._pressed_key
        if self.target is None:
            background = theme.control_disabled
            color = theme.muted
        elif pressed:
            background = theme.control_pressed
            color = theme.foreground
        else:
            background = theme.control
            color = theme.foreground

        x1 = x + width - 1
        y1 = y + height - 1
        display.fill_rect(x, y, x1, y1, background)
        display.rect(x, y, x1, y1, theme.border)
        text = _fit_text(label, width - 4, 1)
        text_x = x + max(0, (width - _text_width(text, 1)) // 2)
        text_y = y + max(0, (height - 8) // 2)
        display.text(text, text_x, text_y, color, 1, background)

    def draw(self, display, theme):
        if self._full_dirty:
            display.fill_rect(self.x, self.y, self.x1, self.y1, theme.background)
            indices = range(len(self._keys))
        else:
            indices = self._dirty_keys

        for index in indices:
            self._draw_key(display, theme, index)

        self._full_dirty = False
        self._dirty_keys = []
        self.dirty = False

    def pointer_down(self, x, y):
        if self.target is None:
            return
        self._pressed_key = self._key_at(x, y)
        self._invalidate_key(self._pressed_key)

    def pointer_move(self, x, y):
        if self.target is None:
            return
        new_key = self._key_at(x, y)
        if new_key != self._pressed_key:
            old_key = self._pressed_key
            self._pressed_key = new_key
            self._invalidate_key(old_key)
            self._invalidate_key(new_key)

    def pointer_up(self, x, y):
        pressed_key = self._pressed_key
        released_key = self._key_at(x, y)
        self._pressed_key = None
        self._invalidate_key(pressed_key)
        if pressed_key is None or pressed_key != released_key or self.target is None:
            return

        value = self._keys[pressed_key][5]
        if value == "\b":
            self.target.backspace()
        elif value == "\n":
            target = self.target
            target.submit()
            if target.screen is not None:
                target.screen.set_focus(None)
        else:
            self.target.insert(value)


class Screen:
    """Widget collection, dirty renderer, and CST816 touch dispatcher."""

    def __init__(
        self,
        display,
        touch,
        theme=None,
        background=None,
        poll_ms=10,
        release_ms=60,
    ):
        self.display = display
        self.touch = touch
        self.theme = Theme() if theme is None else theme
        self.background = (
            self.theme.background if background is None else background
        )
        self.poll_ms = int(poll_ms)
        self.release_ms = int(release_ms)
        self.widgets = []
        self.focused = None
        self.keyboard = None
        self._active = None
        self._last_x = 0
        self._last_y = 0
        self._last_touch = _ticks_ms()
        self._wait_for_clear = False
        self._full_redraw = True

    def add(self, widget):
        if widget.screen is not None and widget.screen is not self:
            raise ValueError("widget already belongs to another screen")
        widget.screen = self
        widget.invalidate()
        self.widgets.append(widget)
        return widget

    def remove(self, widget):
        self.widgets.remove(widget)
        if self.focused is widget:
            self.set_focus(None)
        if self.keyboard is widget:
            self.keyboard = None
        widget.screen = None
        self.refresh()

    def set_keyboard(self, keyboard):
        if keyboard not in self.widgets:
            self.add(keyboard)
        self.keyboard = keyboard
        keyboard.set_target(
            self.focused if getattr(self.focused, "accepts_text", False) else None
        )
        return keyboard

    def set_focus(self, widget):
        if widget is not None and not widget.focusable:
            raise ValueError("widget cannot receive focus")
        if widget is self.focused:
            return
        if self.focused is not None:
            self.focused.set_focused(False)
        self.focused = widget
        if self.focused is not None:
            self.focused.set_focused(True)
        if self.keyboard is not None:
            self.keyboard.set_target(
                widget if getattr(widget, "accepts_text", False) else None
            )

    def refresh(self):
        self._full_redraw = True

    def draw(self):
        if self._full_redraw:
            self.display.clear(self.background)
            for widget in self.widgets:
                widget.dirty = True
                if isinstance(widget, Keyboard):
                    widget._full_dirty = True
            self._full_redraw = False

        for index, widget in enumerate(self.widgets):
            if not widget.visible or not widget.dirty:
                continue
            for overlay in self.widgets[index + 1 :]:
                if overlay.visible and widget.overlaps(overlay):
                    overlay.dirty = True
            widget.draw(self.display, self.theme)

    def _hit_test(self, x, y):
        for widget in reversed(self.widgets):
            if widget.visible and widget.enabled and widget.contains(x, y):
                return widget
        return None

    def _pointer_down(self, x, y):
        target = self._hit_test(x, y)
        if target is None:
            self.set_focus(None)
            return
        if target.focusable:
            self.set_focus(target)
        elif not target.preserve_focus:
            self.set_focus(None)
        self._active = target
        target.pointer_down(x, y)

    def _pointer_up(self, x, y):
        if self._active is None:
            return
        active = self._active
        self._active = None
        active.pointer_up(x, y)

    def update(self):
        self.draw()
        now = _ticks_ms()
        point = self.touch.read()

        if point is not None:
            x, y, event = point
            self._last_x = x
            self._last_y = y
            self._last_touch = now
            if not self._wait_for_clear:
                if self._active is None:
                    self._pointer_down(x, y)
                else:
                    self._active.pointer_move(x, y)
                if event == EVENT_UP:
                    self._pointer_up(x, y)
                    self._wait_for_clear = True
        else:
            self._wait_for_clear = False
            if self._active is not None:
                if _ticks_diff(now, self._last_touch) >= self.release_ms:
                    self._pointer_up(self._last_x, self._last_y)

        self.draw()
        return point is not None

    def run(self):
        while True:
            self.update()
            _sleep_ms(self.poll_ms)
