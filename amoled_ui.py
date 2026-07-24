"""Small touch UI toolkit for the built-in ``amoled`` MicroPython module."""

import time

try:
    import amoled as _amoled
except ImportError:
    _amoled = None


EVENT_DOWN = 0
EVENT_UP = 1
EVENT_CONTACT = 2

_KEY_BACKSPACE = "\b"
_KEY_DONE = "\n"
_KEY_NUMBERS = "\x01"
_KEY_LETTERS = "\x02"
_KEY_SHIFT = "\x03"


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

    def set_bounds(self, x, y, width, height):
        x = int(x)
        y = int(y)
        width = int(width)
        height = int(height)
        if width <= 0 or height <= 0:
            raise ValueError("widget width and height must be positive")
        bounds = (x, y, width, height)
        if bounds == (self.x, self.y, self.width, self.height):
            return
        self.x, self.y, self.width, self.height = bounds
        self.invalidate()
        if self.screen is not None:
            self.screen.refresh()

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


class _ToggleControl(Widget):
    """Shared state and touch behavior for binary controls."""

    def __init__(
        self,
        text,
        x,
        y,
        width,
        height,
        value=False,
        on_change=None,
        color=None,
        background=None,
        visible=True,
        enabled=True,
    ):
        super().__init__(x, y, width, height, visible=visible, enabled=enabled)
        self.text = str(text)
        self.value = bool(value)
        self.on_change = on_change
        self.color = color
        self.background = background
        self.pressed = False

    def set_text(self, text):
        text = str(text)
        if text != self.text:
            self.text = text
            self.invalidate()

    def set_value(self, value, notify=True):
        value = bool(value)
        if value == self.value:
            return
        self.value = value
        self.invalidate()
        if notify and self.on_change is not None:
            self.on_change(self.value)

    def toggle(self):
        self.set_value(not self.value)

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
        if activate:
            self.toggle()

    def _draw_label(self, display, theme, x, background):
        if not self.text:
            return
        color = (
            theme.muted
            if not self.enabled
            else (theme.foreground if self.color is None else self.color)
        )
        width = max(0, self.x1 - x + 1)
        text = _fit_text(self.text, width, 1)
        text_y = self.y + max(0, (self.height - 8) // 2)
        display.text(text, x, text_y, color, 1, background)


class Checkbox(_ToggleControl):
    """Checkbox with an optional label and change callback."""

    def __init__(
        self,
        text,
        x,
        y,
        width=None,
        height=28,
        checked=False,
        on_change=None,
        color=None,
        background=None,
        visible=True,
        enabled=True,
    ):
        text = str(text)
        height = int(height)
        if height < 16:
            raise ValueError("checkbox height must be at least 16")
        box_size = max(8, min(20, height - 4))
        if width is None:
            width = box_size + (
                8 + _text_width(text, 1) if text else 2
            )
        if width < box_size + 2:
            raise ValueError("checkbox is too narrow")
        super().__init__(
            text,
            x,
            y,
            width,
            height,
            value=checked,
            on_change=on_change,
            color=color,
            background=background,
            visible=visible,
            enabled=enabled,
        )

    @property
    def checked(self):
        return self.value

    def set_checked(self, checked, notify=True):
        self.set_value(checked, notify=notify)

    def draw(self, display, theme):
        background = theme.background if self.background is None else self.background
        display.fill_rect(self.x, self.y, self.x1, self.y1, background)

        box_size = max(8, min(20, self.height - 4))
        box_x = self.x + 2
        box_y = self.y + (self.height - box_size) // 2
        box_x1 = box_x + box_size - 1
        box_y1 = box_y + box_size - 1

        if not self.enabled:
            fill = theme.control_disabled
            mark = theme.muted
        elif self.pressed:
            fill = theme.control_pressed
            mark = theme.foreground
        elif self.value:
            fill = theme.accent
            mark = theme.foreground
        else:
            fill = theme.control
            mark = theme.foreground

        display.fill_rect(box_x, box_y, box_x1, box_y1, fill)
        display.rect(box_x, box_y, box_x1, box_y1, theme.border)
        if self.value:
            mid_y = box_y + box_size // 2
            display.line(box_x + 4, mid_y, box_x + 8, box_y1 - 4, mark)
            display.line(box_x + 8, box_y1 - 4, box_x1 - 3, box_y + 4, mark)

        self._draw_label(display, theme, box_x1 + 7, background)
        self.dirty = False


class Switch(_ToggleControl):
    """Compact on/off switch with an optional label."""

    def __init__(
        self,
        text,
        x,
        y,
        width=None,
        height=28,
        value=False,
        on_change=None,
        color=None,
        background=None,
        visible=True,
        enabled=True,
    ):
        text = str(text)
        height = int(height)
        if height < 16:
            raise ValueError("switch height must be at least 16")
        track_height = max(12, min(22, height - 4))
        track_width = max(28, track_height * 2)
        if width is None:
            width = track_width + (
                8 + _text_width(text, 1) if text else 2
            )
        if width < track_width + 2:
            raise ValueError("switch is too narrow")
        super().__init__(
            text,
            x,
            y,
            width,
            height,
            value=value,
            on_change=on_change,
            color=color,
            background=background,
            visible=visible,
            enabled=enabled,
        )

    def draw(self, display, theme):
        background = theme.background if self.background is None else self.background
        display.fill_rect(self.x, self.y, self.x1, self.y1, background)

        track_height = max(12, min(22, self.height - 4))
        track_width = max(28, track_height * 2)
        track_x = self.x + 2
        track_y = self.y + (self.height - track_height) // 2
        track_x1 = track_x + track_width - 1
        track_y1 = track_y + track_height - 1

        if not self.enabled:
            track_color = theme.control_disabled
            thumb_color = theme.muted
        elif self.value and self.pressed:
            track_color = theme.accent
            thumb_color = theme.foreground
        elif self.pressed:
            track_color = theme.control
            thumb_color = theme.muted
        elif self.value:
            track_color = theme.accent
            thumb_color = theme.foreground
        else:
            track_color = theme.control
            thumb_color = theme.muted

        display.fill_rect(track_x, track_y, track_x1, track_y1, track_color)
        display.rect(track_x, track_y, track_x1, track_y1, theme.border)

        thumb_size = track_height - 6
        thumb_x = track_x1 - thumb_size - 2 if self.value else track_x + 3
        thumb_y = track_y + 3
        display.fill_rect(
            thumb_x,
            thumb_y,
            thumb_x + thumb_size - 1,
            thumb_y + thumb_size - 1,
            thumb_color,
        )

        self._draw_label(display, theme, track_x1 + 7, background)
        self.dirty = False


class Slider(Widget):
    """Horizontal slider with clamping, step rounding, and drag updates."""

    def __init__(
        self,
        x,
        y,
        width,
        height=28,
        min_value=0,
        max_value=100,
        value=0,
        step=1,
        on_change=None,
        background=None,
        track_color=None,
        fill_color=None,
        thumb_color=None,
        visible=True,
        enabled=True,
    ):
        super().__init__(x, y, width, height, visible=visible, enabled=enabled)
        if max_value <= min_value:
            raise ValueError("max_value must be greater than min_value")
        if step <= 0:
            raise ValueError("step must be positive")
        if width < 20 or height < 12:
            raise ValueError("slider must be at least 20x12")
        self.min_value = min_value
        self.max_value = max_value
        self.step = step
        self.on_change = on_change
        self.background = background
        self.track_color = track_color
        self.fill_color = fill_color
        self.thumb_color = thumb_color
        self._integral = all(
            isinstance(number, int)
            for number in (min_value, max_value, value, step)
        )
        self.value = self._normalize(value)
        self.dragging = False

    def _normalize(self, value):
        value = max(self.min_value, min(self.max_value, value))
        if value == self.min_value or value == self.max_value:
            return int(value) if self._integral else value
        steps = int((value - self.min_value) / self.step + 0.5)
        value = self.min_value + steps * self.step
        value = max(self.min_value, min(self.max_value, value))
        return int(value) if self._integral else value

    def set_value(self, value, notify=True):
        value = self._normalize(value)
        if value == self.value:
            return
        self.value = value
        self.invalidate()
        if notify and self.on_change is not None:
            self.on_change(self.value)

    def _track_bounds(self):
        thumb_width = max(8, min(14, self.height - 6))
        left = self.x + thumb_width // 2
        right = self.x1 - thumb_width // 2
        return left, right, thumb_width

    def _set_from_x(self, x):
        left, right, _ = self._track_bounds()
        x = max(left, min(right, x))
        ratio = (x - left) / (right - left)
        self.set_value(
            self.min_value + ratio * (self.max_value - self.min_value)
        )

    def draw(self, display, theme):
        background = theme.background if self.background is None else self.background
        display.fill_rect(self.x, self.y, self.x1, self.y1, background)

        left, right, thumb_width = self._track_bounds()
        ratio = (self.value - self.min_value) / (
            self.max_value - self.min_value
        )
        thumb_x = left + int((right - left) * ratio)
        track_y = self.y + self.height // 2
        track_top = track_y - 2
        track_bottom = track_y + 1

        if not self.enabled:
            empty_color = theme.control_disabled
            active_color = theme.muted
            knob_color = theme.muted
        else:
            empty_color = (
                theme.border if self.track_color is None else self.track_color
            )
            active_color = (
                theme.accent if self.fill_color is None else self.fill_color
            )
            knob_color = (
                theme.foreground if self.thumb_color is None else self.thumb_color
            )

        display.fill_rect(left, track_top, right, track_bottom, empty_color)
        display.fill_rect(left, track_top, thumb_x, track_bottom, active_color)

        thumb_height = self.height - 6
        thumb_left = thumb_x - thumb_width // 2
        thumb_top = self.y + 3
        display.fill_rect(
            thumb_left,
            thumb_top,
            thumb_left + thumb_width - 1,
            thumb_top + thumb_height - 1,
            knob_color,
        )
        display.rect(
            thumb_left,
            thumb_top,
            thumb_left + thumb_width - 1,
            thumb_top + thumb_height - 1,
            theme.border,
        )
        self.dirty = False

    def pointer_down(self, x, y):
        if self.contains(x, y):
            self.dragging = True
            self._set_from_x(x)

    def pointer_move(self, x, y):
        if self.dragging:
            self._set_from_x(x)

    def pointer_up(self, x, y):
        if self.dragging:
            self._set_from_x(x)
            self.dragging = False


class ProgressBar(Widget):
    """Horizontal progress bar with a centered percentage label."""

    def __init__(
        self, x, y, width, height=16, value=0.0, min_value=0,
        max_value=100, color=None, background=None, visible=True,
    ):
        super().__init__(x, y, width, height, visible=visible)
        if max_value <= min_value:
            raise ValueError("max_value must be greater than min_value")
        self.min_value = min_value
        self.max_value = max_value
        self.color = color
        self.background = background
        self.value = self._clamp(value)

    def _clamp(self, value):
        return max(self.min_value, min(self.max_value, value))

    def set_value(self, value):
        value = self._clamp(value)
        if value != self.value:
            self.value = value
            self.invalidate()

    def draw(self, display, theme):
        background = theme.control if self.background is None else self.background
        color = theme.accent if self.color is None else self.color
        display.fill_rect(self.x, self.y, self.x1, self.y1, background)

        ratio = (self.value - self.min_value) / (
            self.max_value - self.min_value
        )
        fill_width = int(self.width * ratio)
        if fill_width > 0:
            display.fill_rect(
                self.x, self.y, self.x + fill_width - 1, self.y1, color
            )

        text = str(int(ratio * 100 + 0.5)) + "%"
        text_x = self.x + max(0, (self.width - _text_width(text, 1)) // 2)
        text_y = self.y + max(0, (self.height - 8) // 2)
        display.text(text, text_x, text_y, theme.foreground, 1)
        self.dirty = False


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
        password=False,
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
        self.password = bool(password)
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
            visible_value = "*" * len(self.value) if self.password else self.value
            text = visible_value + ("_" if self.focused else "")
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

    MODE_LETTERS = "letters"
    MODE_NUMBERS = "numbers"
    ACTION_NUMBERS = _KEY_NUMBERS
    ACTION_LETTERS = _KEY_LETTERS
    ACTION_SHIFT = _KEY_SHIFT
    ACTION_DONE = _KEY_DONE

    LETTER_ROWS = (
        (
            ("q", "q", 1), ("w", "w", 1), ("e", "e", 1),
            ("r", "r", 1), ("t", "t", 1), ("y", "y", 1),
            ("u", "u", 1), ("i", "i", 1), ("o", "o", 1),
            ("p", "p", 1),
        ),
        (
            ("a", "a", 1), ("s", "s", 1), ("d", "d", 1),
            ("f", "f", 1), ("g", "g", 1), ("h", "h", 1),
            ("j", "j", 1), ("k", "k", 1), ("l", "l", 1),
        ),
        (
            ("LOW", _KEY_SHIFT, 2),
            ("z", "z", 1), ("x", "x", 1), ("c", "c", 1),
            ("v", "v", 1), ("b", "b", 1), ("n", "n", 1),
            ("m", "m", 1),
        ),
        (
            ("123", _KEY_NUMBERS, 2),
            ("BKSP", _KEY_BACKSPACE, 2),
            ("SPACE", " ", 4),
            ("DONE", _KEY_DONE, 2),
        ),
    )

    SHIFTED_ROWS = (
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
            ("CAPS", _KEY_SHIFT, 2),
            ("Z", "Z", 1), ("X", "X", 1), ("C", "C", 1),
            ("V", "V", 1), ("B", "B", 1), ("N", "N", 1),
            ("M", "M", 1),
        ),
        (
            ("123", _KEY_NUMBERS, 2),
            ("BKSP", _KEY_BACKSPACE, 2),
            ("SPACE", " ", 4),
            ("DONE", _KEY_DONE, 2),
        ),
    )

    NUMBER_ROWS = (
        (
            ("1", "1", 1), ("2", "2", 1), ("3", "3", 1),
            ("4", "4", 1), ("5", "5", 1), ("6", "6", 1),
            ("7", "7", 1), ("8", "8", 1), ("9", "9", 1),
            ("0", "0", 1),
        ),
        (
            ("!", "!", 1), ("@", "@", 1), ("#", "#", 1),
            ("$", "$", 1), ("%", "%", 1), ("^", "^", 1),
            ("&", "&", 1), ("*", "*", 1), ("(", "(", 1),
            (")", ")", 1),
        ),
        (
            ("-", "-", 1), ("_", "_", 1), ("=", "=", 1),
            ("+", "+", 1), ("[", "[", 1), ("]", "]", 1),
            ("/", "/", 1), ("\\", "\\", 1),
        ),
        (
            ("ABC", _KEY_LETTERS, 2), (".", ".", 1),
            (",", ",", 1), (":", ":", 1), (";", ";", 1),
            ("?", "?", 1), ("BKSP", _KEY_BACKSPACE, 2),
            ("DONE", _KEY_DONE, 2),
        ),
    )

    def __init__(
        self,
        x,
        y,
        width,
        height,
        target=None,
        rows=None,
        shifted_rows=None,
        number_rows=None,
        mode=MODE_LETTERS,
        gap=2,
        visible=True,
    ):
        super().__init__(x, y, width, height, visible=visible)
        self.target = target
        self._shifted = False
        self.letter_rows = self.LETTER_ROWS if rows is None else rows
        self.shifted_rows = (
            self.SHIFTED_ROWS
            if rows is None and shifted_rows is None
            else shifted_rows
        )
        self.number_rows = self.NUMBER_ROWS if number_rows is None else number_rows
        if mode not in (self.MODE_LETTERS, self.MODE_NUMBERS):
            raise ValueError("keyboard mode must be letters or numbers")
        self.mode = mode
        self.rows = self._rows_for_mode(mode)
        self.gap = int(gap)
        self._keys = []
        self._pressed_key = None
        self._dirty_keys = []
        self._full_dirty = True
        self._build_keys()

    def set_bounds(self, x, y, width, height):
        old_bounds = (self.x, self.y, self.width, self.height)
        super().set_bounds(x, y, width, height)
        if old_bounds != (self.x, self.y, self.width, self.height):
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

    def _set_rows(self, rows):
        self.rows = rows
        self._pressed_key = None
        self._build_keys()
        self.invalidate()

    def _rows_for_mode(self, mode):
        if mode == self.MODE_NUMBERS:
            return self.number_rows
        if self._shifted and self.shifted_rows is not None:
            return self.shifted_rows
        return self.letter_rows

    def set_letter_rows(self, rows, shifted_rows=None):
        self.letter_rows = rows
        if shifted_rows is not None:
            self.shifted_rows = shifted_rows
        if self.mode == self.MODE_LETTERS:
            self._set_rows(self._rows_for_mode(self.mode))

    def set_mode(self, mode):
        if mode not in (self.MODE_LETTERS, self.MODE_NUMBERS):
            raise ValueError("keyboard mode must be letters or numbers")
        if mode == self.mode:
            return
        self.mode = mode
        self._set_rows(self._rows_for_mode(mode))

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

    def _key_colors(self, theme, index, value):
        pressed = index == self._pressed_key
        if self.target is None:
            return theme.control_disabled, theme.muted
        if pressed:
            return theme.control_pressed, theme.foreground
        if value in (_KEY_NUMBERS, _KEY_LETTERS, _KEY_DONE):
            return theme.accent, theme.foreground
        if value == _KEY_SHIFT:
            if self._shifted:
                return theme.accent, theme.foreground
            return theme.control, theme.muted
        return theme.control, theme.foreground

    def _draw_key(self, display, theme, index):
        x, y, width, height, label, value = self._keys[index]
        background, color = self._key_colors(theme, index, value)

        x1 = x + width - 1
        y1 = y + height - 1
        display.fill_rect(x, y, x1, y1, background)
        display.rect(x, y, x1, y1, theme.border)
        s = 2
        text = _fit_text(label, width - 4, s)
        text_x = x + max(0, (width - _text_width(text, s)) // 2)
        text_y = y + max(0, (height - 8 * s) // 2)
        display.text(text, text_x, text_y, color, s, background)

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

    def _activate_value(self, value):
        if value == _KEY_NUMBERS:
            self.set_mode(self.MODE_NUMBERS)
        elif value == _KEY_LETTERS:
            self.set_mode(self.MODE_LETTERS)
        elif value == _KEY_SHIFT:
            self._shifted = not self._shifted
            self._set_rows(self._rows_for_mode(self.mode))
        elif value == _KEY_BACKSPACE:
            self.target.backspace()
        elif value == _KEY_DONE:
            target = self.target
            target.submit()
            if target.screen is not None:
                target.screen.set_focus(None)
        else:
            self.target.insert(value)

    def pointer_up(self, x, y):
        pressed_key = self._pressed_key
        released_key = self._key_at(x, y)
        self._pressed_key = None
        self._invalidate_key(pressed_key)
        if pressed_key is None or pressed_key != released_key or self.target is None:
            return

        self._activate_value(self._keys[pressed_key][5])


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
        action_bar_y=8,
    ):
        self.display = display
        self.touch = touch
        self.theme = Theme() if theme is None else theme
        self.background = (
            self.theme.background if background is None else background
        )
        self.poll_ms = int(poll_ms)
        self.release_ms = int(release_ms)
        self.action_bar_y = int(action_bar_y)
        if self.action_bar_y < 0:
            raise ValueError("action_bar_y cannot be negative")
        self.widgets = []
        self.focused = None
        self.keyboard = None
        self._active = None
        self._last_x = 0
        self._last_y = 0
        self._last_touch = _ticks_ms()
        self._wait_for_clear = False
        self._full_redraw = True
        self._saved_bounds = {}
        self._saved_visibility = {}
        self._keyboard_mode = False
        self._clear_focus_on_release = None

    def add(self, widget):
        if widget.screen is not None and widget.screen is not self:
            raise ValueError("widget already belongs to another screen")
        widget.screen = self
        widget.invalidate()
        self.widgets.append(widget)
        return widget

    def remove(self, widget):
        if self.focused is widget:
            self.set_focus(None)
        if self.keyboard is widget:
            self._restore_keyboard_layout()
            self.keyboard = None
        self.widgets.remove(widget)
        widget.screen = None
        self.refresh()

    def set_keyboard(self, keyboard):
        self._restore_keyboard_layout()
        if keyboard not in self.widgets:
            self.add(keyboard)
        self.keyboard = keyboard
        target = (
            self.focused if getattr(self.focused, "accepts_text", False) else None
        )
        keyboard.set_target(target)
        keyboard.visible = False
        if target is not None:
            self._show_keyboard_layout(target)
        else:
            self.refresh()
        return keyboard

    def _display_size(self):
        dimensions = []
        for name in ("width", "height"):
            value = getattr(self.display, name, None)
            value = value() if callable(value) else value
            if value is None and _amoled is not None:
                value = getattr(_amoled, name.upper(), None)
            dimensions.append(int(value) if value is not None else 0)

        width, height = dimensions
        if width <= 0:
            width = max([widget.x1 + 1 for widget in self.widgets] or [1])
        if height <= 0:
            height = max([widget.y1 + 1 for widget in self.widgets] or [1])
        return width, height

    def _set_widget_bounds(self, widget, bounds):
        x, y, width, height = bounds
        changed = (widget.x, widget.y, widget.width, widget.height) != bounds
        widget.x = int(x)
        widget.y = int(y)
        widget.width = int(width)
        widget.height = int(height)
        if changed and isinstance(widget, Keyboard):
            widget._build_keys()
        widget.invalidate()

    def _action_button(self, focused):
        best = None
        best_distance = None
        for widget in self.widgets:
            if (
                widget is self.keyboard
                or not isinstance(widget, Button)
                or not self._saved_visibility.get(widget, False)
            ):
                continue
            distance = abs(widget.y - focused.y) + abs(widget.x - focused.x)
            if best_distance is None or distance < best_distance:
                best = widget
                best_distance = distance
        return best

    def _show_keyboard_layout(self, focused):
        if self.keyboard is None or self._keyboard_mode:
            return
        self._saved_bounds = {
            widget: (widget.x, widget.y, widget.width, widget.height)
            for widget in self.widgets
        }
        self._saved_visibility = {
            widget: widget.visible for widget in self.widgets
        }
        self._keyboard_mode = True

        action_button = self._action_button(focused)
        action_widgets = [focused]
        if action_button is not None:
            action_widgets.append(action_button)

        for widget in self.widgets:
            if widget is self.keyboard:
                continue
            x, _, width, height = self._saved_bounds[widget]
            self._set_widget_bounds(
                widget,
                (x, self.action_bar_y, width, height),
            )
            widget.visible = widget in action_widgets

        action_bar_bottom = self.action_bar_y + max(
            widget.height for widget in action_widgets
        )
        screen_width, screen_height = self._display_size()
        action_bar_bottom = min(action_bar_bottom, max(1, screen_height - 1))
        self.keyboard.visible = True
        self._set_widget_bounds(
            self.keyboard,
            (
                0,
                action_bar_bottom,
                screen_width,
                max(1, screen_height - action_bar_bottom),
            ),
        )
        self.refresh()

    def _restore_keyboard_layout(self):
        if not self._keyboard_mode:
            if self.keyboard is not None:
                self.keyboard.visible = False
            return
        saved_bounds = self._saved_bounds
        saved_visibility = self._saved_visibility
        self._saved_bounds = {}
        self._saved_visibility = {}
        self._keyboard_mode = False
        for widget, bounds in saved_bounds.items():
            if widget.screen is self and widget in self.widgets:
                self._set_widget_bounds(widget, bounds)
                widget.visible = saved_visibility.get(widget, True)
        if self.keyboard is not None:
            self.keyboard.visible = False
        self.refresh()

    def set_focus(self, widget):
        if widget is not None and not widget.focusable:
            raise ValueError("widget cannot receive focus")
        if widget is self.focused:
            if widget is None and self._keyboard_mode:
                self._restore_keyboard_layout()
            return
        self._restore_keyboard_layout()
        if self.focused is not None:
            self.focused.set_focused(False)
        self.focused = widget
        if self.focused is not None:
            self.focused.set_focused(True)
        if self.keyboard is not None:
            target = widget if getattr(widget, "accepts_text", False) else None
            self.keyboard.set_target(target)
            if target is not None:
                self._show_keyboard_layout(target)
            else:
                self.keyboard.visible = False

    def refresh(self):
        self._full_redraw = True

    def draw(self):
        full_redraw = self._full_redraw
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
            if full_redraw and isinstance(widget, Keyboard):
                # The screen clear already painted the keyboard gaps. Avoid a
                # second full-area fill before drawing every key cell.
                for key_index in range(len(widget._keys)):
                    widget._draw_key(self.display, self.theme, key_index)
                widget._full_dirty = False
                widget._dirty_keys = []
                widget.dirty = False
            else:
                widget.draw(self.display, self.theme)

    def _hit_test(self, x, y):
        for widget in reversed(self.widgets):
            if widget.visible and widget.enabled and widget.contains(x, y):
                return widget
        return None

    def _pointer_down(self, x, y):
        self._clear_focus_on_release = None
        target = self._hit_test(x, y)
        if target is None:
            self.set_focus(None)
            return
        if target.focusable:
            self.set_focus(target)
        elif not target.preserve_focus:
            if self._keyboard_mode:
                self._clear_focus_on_release = self.focused
            else:
                self.set_focus(None)
        self._active = target
        target.pointer_down(x, y)

    def _pointer_up(self, x, y):
        if self._active is None:
            return
        active = self._active
        self._active = None
        active.pointer_up(x, y)
        focus_to_clear = self._clear_focus_on_release
        self._clear_focus_on_release = None
        if focus_to_clear is not None and self.focused is focus_to_clear:
            self.set_focus(None)
        elif self.focused is None and self._keyboard_mode:
            self._restore_keyboard_layout()

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
