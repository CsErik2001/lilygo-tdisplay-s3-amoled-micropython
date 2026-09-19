"""Retained-canvas rectangular UI over the native ``amoled`` driver.

Companion to ``amoled_assets``: widgets draw into a full-frame RGB565
canvas in PSRAM (536 x 240 x 2 bytes) and ``Screen`` transfers only the
dirty rectangle with ``Display.blit``. Text and icons use pre-compiled
``.tgf`` / ``.tgi`` assets; arcs and alpha compositing run in native C.

Requires firmware with ``amoled.fill_arc``, ``amoled.blit_rgb565``,
``amoled.blend_a4`` and ``amoled.blend_rgb565_a4``.
"""

import math
import time

import amoled

WIDTH = amoled.WIDTH
HEIGHT = amoled.HEIGHT

EVENT_DOWN = 0
EVENT_UP = 1
EVENT_CONTACT = 2


def rgb(r, g, b):
    return amoled.rgb(r, g, b)


BLACK = rgb(0, 0, 0)
WHITE = rgb(248, 248, 250)
SYSTEM_BLUE = rgb(10, 132, 255)
SYSTEM_GREEN = rgb(48, 209, 88)
SYSTEM_YELLOW = rgb(255, 214, 10)
SYSTEM_RED = rgb(255, 69, 58)
SYSTEM_GRAY = rgb(142, 142, 147)
SURFACE = rgb(28, 28, 30)
SURFACE_PRESSED = rgb(58, 58, 62)
BORDER = rgb(72, 72, 76)


def _clamp(value, low, high):
    return low if value < low else high if value > high else value


class Canvas:
    """Full-frame RGB565 canvas with one batched panel transfer per redraw."""

    def __init__(self, width=None, height=None):
        import framebuf

        self._width = int(width or WIDTH)
        self._height = int(height or HEIGHT)
        self.buffer = bytearray(self._width * self._height * 2)
        self._view = memoryview(self.buffer)
        self._framebuf = framebuf.FrameBuffer(
            self.buffer, self._width, self._height, framebuf.RGB565)
        self._dirty = None

    def width(self):
        return self._width

    def height(self):
        return self._height

    def _mark(self, x0, y0, x1, y1):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self._width - 1, int(x1))
        y1 = min(self._height - 1, int(y1))
        if x0 > x1 or y0 > y1:
            return
        if self._dirty is None:
            self._dirty = [x0, y0, x1, y1]
        else:
            self._dirty[0] = min(self._dirty[0], x0)
            self._dirty[1] = min(self._dirty[1], y0)
            self._dirty[2] = max(self._dirty[2], x1)
            self._dirty[3] = max(self._dirty[3], y1)

    def invalidate(self, x0=0, y0=0, x1=None, y1=None):
        self._mark(x0, y0,
                   self._width - 1 if x1 is None else x1,
                   self._height - 1 if y1 is None else y1)

    def clear(self, color=0):
        self._framebuf.fill(int(color))
        self.invalidate()

    def pixel(self, x, y, color):
        self._framebuf.pixel(int(x), int(y), int(color))
        self._mark(x, y, x, y)

    def line(self, x0, y0, x1, y1, color):
        self._framebuf.line(int(x0), int(y0), int(x1), int(y1), int(color))
        self._mark(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def rect(self, x0, y0, x1, y1, color):
        left = min(int(x0), int(x1))
        top = min(int(y0), int(y1))
        right = max(int(x0), int(x1))
        bottom = max(int(y0), int(y1))
        self._framebuf.rect(left, top, right - left + 1, bottom - top + 1,
                            int(color))
        self._mark(left, top, right, bottom)

    def fill_rect(self, x0, y0, x1, y1, color):
        left = min(int(x0), int(x1))
        top = min(int(y0), int(y1))
        right = max(int(x0), int(x1))
        bottom = max(int(y0), int(y1))
        self._framebuf.fill_rect(
            left, top, right - left + 1, bottom - top + 1, int(color))
        self._mark(left, top, right, bottom)

    def filled_circle(self, cx, cy, radius, color):
        cx = int(cx)
        cy = int(cy)
        radius = max(0, int(radius))
        self._framebuf.ellipse(cx, cy, radius, radius, int(color), True)
        self._mark(cx - radius, cy - radius, cx + radius, cy + radius)

    def native_arc(self, cx, cy, radius, start, end, color,
                   thickness=3, end_caps=False):
        bounds = amoled.fill_arc(
            self.buffer, self._width, self._height,
            float(cx), float(cy), float(radius), float(start), float(end),
            int(color), float(thickness), bool(end_caps))
        if bounds is not None:
            self._mark(bounds[0], bounds[1], bounds[2], bounds[3])

    def text(self, value, x, y, color, scale=1, bg=-1):
        value = str(value)
        x = int(x)
        y = int(y)
        scale = max(1, int(scale))
        self._framebuf.text(value, x, y, int(color))
        self._mark(x, y, x + len(value) * 8 * scale - 1, y + 8 * scale - 1)

    def blit_rgb565(self, pixels, width, height, x, y):
        bounds = amoled.blit_rgb565(
            self.buffer, self._width, self._height, pixels,
            int(width), int(height), int(x), int(y))
        self._mark(bounds[0], bounds[1], bounds[2], bounds[3])

    def blend_a4(self, mask, width, height, x, y, color):
        bounds = amoled.blend_a4(
            self.buffer, self._width, self._height, mask,
            int(width), int(height), int(x), int(y), int(color))
        self._mark(bounds[0], bounds[1], bounds[2], bounds[3])

    def blend_rgb565_a4(self, pixels, mask, width, height, x, y):
        bounds = amoled.blend_rgb565_a4(
            self.buffer, self._width, self._height, pixels, mask,
            int(width), int(height), int(x), int(y))
        self._mark(bounds[0], bounds[1], bounds[2], bounds[3])

    def present(self, display):
        """Transfer the dirty rectangle to the panel."""
        if self._dirty is None:
            return 0
        x0, y0, x1, y1 = self._dirty
        width = x1 - x0 + 1
        height = y1 - y0 + 1
        if x0 == 0 and y0 == 0 and x1 == self._width - 1 and y1 == self._height - 1:
            display.blit(self._view, x0, y0, x1, y1)
        else:
            chunk = bytearray(width * height * 2)
            target = memoryview(chunk)
            stride = self._width * 2
            row_bytes = width * 2
            for row in range(height):
                src = ((y0 + row) * self._width + x0) * 2
                dst = row * row_bytes
                target[dst:dst + row_bytes] = self._view[src:src + row_bytes]
            display.blit(chunk, x0, y0, x1, y1)
        self._dirty = None
        return width * height


def fill_circle(canvas, cx, cy, radius, color):
    canvas.filled_circle(cx, cy, radius, color)


def circle(canvas, cx, cy, radius, color, thickness=1, fill=0):
    radius = max(0, int(radius))
    thickness = max(1, min(radius + 1, int(thickness)))
    fill_circle(canvas, cx, cy, radius, color)
    inner = radius - thickness
    if inner >= 0:
        fill_circle(canvas, cx, cy, inner, fill)


def fill_round_rect(canvas, x, y, width, height, radius, color):
    x = int(x)
    y = int(y)
    width = max(1, int(width))
    height = max(1, int(height))
    x1 = x + width - 1
    y1 = y + height - 1
    radius = max(0, min(int(radius), width // 2, height // 2))
    if radius <= 1:
        canvas.fill_rect(x, y, x1, y1, color)
        return
    if y + radius <= y1 - radius:
        canvas.fill_rect(x, y + radius, x1, y1 - radius, color)
    rr = radius * radius
    for offset in range(radius):
        dy = radius - offset
        half = int(math.sqrt(max(0, rr - dy * dy)))
        left = x + radius - half
        right = x1 - radius + half
        canvas.fill_rect(left, y + offset, right, y + offset, color)
        canvas.fill_rect(left, y1 - offset, right, y1 - offset, color)


def round_rect(canvas, x, y, width, height, radius, color,
               thickness=1, fill=0):
    thickness = max(1, int(thickness))
    fill_round_rect(canvas, x, y, width, height, radius, color)
    inner_w = int(width) - 2 * thickness
    inner_h = int(height) - 2 * thickness
    if inner_w > 0 and inner_h > 0:
        fill_round_rect(
            canvas, int(x) + thickness, int(y) + thickness,
            inner_w, inner_h, max(0, int(radius) - thickness), fill)


def arc(canvas, cx, cy, radius, start, end, color, thickness=3,
        end_caps=False):
    canvas.native_arc(cx, cy, radius, start, end, color,
                      thickness=thickness, end_caps=end_caps)


class Theme:
    def __init__(self, **overrides):
        self.background = BLACK
        self.surface = SURFACE
        self.surface_pressed = SURFACE_PRESSED
        self.foreground = WHITE
        self.muted = SYSTEM_GRAY
        self.accent = SYSTEM_BLUE
        self.success = SYSTEM_GREEN
        self.warning = SYSTEM_YELLOW
        self.danger = SYSTEM_RED
        self.border = BORDER
        for name, value in overrides.items():
            if not hasattr(self, name):
                raise ValueError("unknown theme property: " + name)
            setattr(self, name, value)


class Widget:
    def __init__(self, x, y, width, height, visible=True, enabled=True):
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)
        if self.width <= 0 or self.height <= 0:
            raise ValueError("widget width and height must be positive")
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

    def invalidate(self):
        self.dirty = True

    def set_visible(self, visible):
        visible = bool(visible)
        if visible != self.visible:
            self.visible = visible
            if self.screen is not None:
                self.screen.refresh()

    def draw(self, canvas, theme):
        raise NotImplementedError

    def pointer_down(self, x, y):
        pass

    def pointer_move(self, x, y):
        pass

    def pointer_up(self, x, y):
        pass


class Card(Widget):
    def __init__(self, x, y, width, height, color=None, border=None,
                 radius=14, visible=True):
        super().__init__(x, y, width, height, visible=visible, enabled=False)
        self.color = color
        self.border = border
        self.radius = int(radius)

    def draw(self, canvas, theme):
        color = theme.surface if self.color is None else self.color
        border = theme.border if self.border is None else self.border
        round_rect(canvas, self.x, self.y, self.width, self.height,
                   self.radius, border, 1, color)
        self.dirty = False


class Label(Widget):
    """Opaque anti-aliased text label."""

    def __init__(self, text, x, y, width, height, font, color=None,
                 background=None, align="left", visible=True):
        super().__init__(x, y, width, height, visible=visible, enabled=False)
        self.text = str(text)
        self.font = font
        self.color = color
        self.background = background
        if align not in ("left", "center", "right"):
            raise ValueError("align must be left, center, or right")
        self.align = align

    def set_text(self, text):
        text = str(text)
        if text != self.text:
            self.text = text
            self.invalidate()

    def draw(self, canvas, theme):
        background = theme.background if self.background is None else self.background
        color = theme.foreground if self.color is None else self.color
        canvas.fill_rect(self.x, self.y, self.x1, self.y1, background)
        width, _ = self.font.measure(self.text)
        if self.align == "center":
            x = self.x + (self.width - width) // 2
        elif self.align == "right":
            x = self.x1 - width + 1
        else:
            x = self.x
        self.font.draw(canvas, self.text, x,
                       self.y + max(0, (self.height - self.font.line_height) // 2),
                       color)
        self.dirty = False


class Button(Widget):
    def __init__(self, text, x, y, width, height, font, on_click=None,
                 color=None, background=None, visible=True, enabled=True):
        super().__init__(x, y, width, height, visible, enabled)
        self.text = str(text)
        self.font = font
        self.on_click = on_click
        self.color = color
        self.background = background
        self.pressed = False

    def set_text(self, text):
        text = str(text)
        if text != self.text:
            self.text = text
            self.invalidate()

    def _set_pressed(self, value):
        value = bool(value)
        if value != self.pressed:
            self.pressed = value
            self.invalidate()

    def draw(self, canvas, theme):
        if not self.enabled:
            background, color = theme.surface, theme.muted
        elif self.pressed:
            background, color = theme.surface_pressed, theme.foreground
        else:
            background = theme.accent if self.background is None else self.background
            color = theme.foreground if self.color is None else self.color
        fill_round_rect(canvas, self.x, self.y, self.width, self.height,
                        self.height // 2, background)
        self.font.draw_centered(canvas, self.text, self.x + self.width // 2,
                                self.y + (self.height - self.font.line_height) // 2,
                                color)
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


class Bar(Widget):
    """Rounded progress bar; fill redraws only on value change."""

    def __init__(self, x, y, width, height=18, value=0, min_value=0,
                 max_value=100, color=None, track=None, visible=True):
        super().__init__(x, y, width, height, visible, enabled=False)
        self.min_value = min_value
        self.max_value = max_value
        self.value = _clamp(value, min_value, max_value)
        self.color = color
        self.track = track

    def set_value(self, value):
        value = _clamp(value, self.min_value, self.max_value)
        if value != self.value:
            self.value = value
            self.invalidate()

    def draw(self, canvas, theme):
        canvas.fill_rect(self.x, self.y, self.x1, self.y1, theme.background)
        track = theme.surface if self.track is None else self.track
        fill_round_rect(canvas, self.x, self.y, self.width, self.height,
                        self.height // 2, track)
        ratio = ((self.value - self.min_value) /
                 max(1, self.max_value - self.min_value))
        fill_width = int(self.width * ratio)
        if fill_width > 2:
            fill_round_rect(canvas, self.x, self.y, fill_width, self.height,
                            self.height // 2,
                            theme.accent if self.color is None else self.color)
        self.dirty = False


class Mascot(Widget):
    """Compiled .tgi sprite; swap frames with ``set_image``."""

    def __init__(self, x, y, image):
        super().__init__(x, y, image.width, image.height, enabled=False)
        self.image = image

    def set_image(self, image):
        if image is not self.image:
            self.image = image
            self.width = image.width
            self.height = image.height
            self.invalidate()

    def draw(self, canvas, theme):
        self.image.draw(canvas, self.x, self.y)
        self.dirty = False


class Screen:
    """Widget ownership, dirty Canvas rendering and touch dispatch."""

    def __init__(self, display, touch, theme=None, background=None,
                 poll_ms=10, release_ms=60):
        self.display = display
        self.touch = touch
        self.theme = Theme() if theme is None else theme
        self.background = (
            self.theme.background if background is None else background)
        self.poll_ms = int(poll_ms)
        self.release_ms = int(release_ms)
        self.canvas = Canvas(display.width(), display.height())
        self.widgets = []
        self._active = None
        self._last_x = 0
        self._last_y = 0
        self._last_touch = time.ticks_ms()
        self._wait_for_clear = False
        self._full_redraw = True

    def add(self, widget):
        widget.screen = self
        widget.invalidate()
        self.widgets.append(widget)
        return widget

    def refresh(self):
        self._full_redraw = True

    def clear_widgets(self):
        for widget in self.widgets:
            widget.screen = None
        self.widgets = []
        self._active = None
        self.refresh()

    def draw(self):
        if self._full_redraw:
            self.canvas.clear(self.background)
            for widget in self.widgets:
                widget.dirty = True
            self._full_redraw = False
        for widget in self.widgets:
            if widget.visible and widget.dirty:
                widget.draw(self.canvas, self.theme)
        self.canvas.present(self.display)

    def _hit_test(self, x, y):
        for widget in reversed(self.widgets):
            if widget.visible and widget.enabled and widget.contains(x, y):
                return widget
        return None

    def _pointer_down(self, x, y):
        target = self._hit_test(x, y)
        if target is None:
            return
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
        now = time.ticks_ms()
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
                if time.ticks_diff(now, self._last_touch) >= self.release_ms:
                    self._pointer_up(self._last_x, self._last_y)
        self.draw()
        return point is not None

    def run(self):
        while True:
            self.update()
            time.sleep_ms(self.poll_ms)
