"""Runtime loader for compiled images and pre-rasterized fonts.

Companion to ``amoled_canvas``: ``TGI1`` images (opaque RGB565, recolorable
A4 alpha masks, or full-color RGB565+A4) and ``TGF1`` anti-aliased fonts
with Unicode metrics. Build them on the computer with
``tools/taggie_assets.py`` (shared with the Waveshare project)::

    python3 tools/taggie_assets.py font MyFont.ttf ui_body.tgf \\
        --size 20 --charset latin-hungarian
    python3 tools/taggie_assets.py image logo.png logo.tgi \\
        --resize 96x96 --format rgb565

Drawing runs in native C (``amoled.blit_rgb565`` / ``blend_a4`` /
``blend_rgb565_a4``) and updates the canvas dirty bounds automatically.
"""


IMAGE_RGB565 = 1
IMAGE_A4 = 2
IMAGE_RGB565_A4 = 3


def _u16(data, offset):
    return data[offset] | (data[offset + 1] << 8)


def _i16(data, offset):
    value = _u16(data, offset)
    return value - 0x10000 if value & 0x8000 else value


def _u32(data, offset):
    return (_u16(data, offset) |
            (_u16(data, offset + 2) << 16))


def _read(path):
    with open(path, "rb") as source:
        return source.read()


class Image:
    """A compiled RGB565, A4, or RGB565+A4 image kept in memory."""

    def __init__(self, source):
        data = _read(source) if isinstance(source, str) else source
        if len(data) < 16 or bytes(data[:4]) != b"TGI1":
            raise ValueError("invalid asset image")
        self.data = data
        self.width = _u16(data, 4)
        self.height = _u16(data, 6)
        self.format = data[8]
        payload_length = _u32(data, 12)
        if self.width <= 0 or self.height <= 0 or len(data) != 16 + payload_length:
            raise ValueError("corrupt asset image")
        pixel_count = self.width * self.height
        view = memoryview(data)
        if self.format == IMAGE_RGB565:
            expected = pixel_count * 2
            if payload_length != expected:
                raise ValueError("bad RGB565 image length")
            self.pixels = view[16:]
            self.alpha = None
        elif self.format == IMAGE_A4:
            expected = (pixel_count + 1) // 2
            if payload_length != expected:
                raise ValueError("bad A4 image length")
            self.pixels = None
            self.alpha = view[16:]
        elif self.format == IMAGE_RGB565_A4:
            color_length = pixel_count * 2
            alpha_length = (pixel_count + 1) // 2
            if payload_length != color_length + alpha_length:
                raise ValueError("bad RGB565+A4 image length")
            self.pixels = view[16:16 + color_length]
            self.alpha = view[16 + color_length:]
        else:
            raise ValueError("unsupported asset image format")

    def draw(self, canvas, x, y, color=None):
        x = int(x)
        y = int(y)
        if self.format == IMAGE_RGB565:
            canvas.blit_rgb565(self.pixels, self.width, self.height, x, y)
        elif self.format == IMAGE_A4:
            if color is None:
                raise ValueError("A4 image needs a color")
            canvas.blend_a4(self.alpha, self.width, self.height, x, y, color)
        else:
            canvas.blend_rgb565_a4(
                self.pixels, self.alpha, self.width, self.height, x, y)


class Font:
    """Pre-rasterized anti-aliased font with Unicode and sparse kerning."""

    _GLYPH_RECORD_SIZE = 22
    _KERN_RECORD_SIZE = 10

    def __init__(self, source):
        data = _read(source) if isinstance(source, str) else source
        if len(data) < 16 or bytes(data[:4]) != b"TGF1":
            raise ValueError("invalid asset font")
        self.data = data
        self.size = _u16(data, 4)
        self.ascent = _i16(data, 6)
        self.descent = _i16(data, 8)
        self.line_height = _u16(data, 10)
        glyph_count = _u16(data, 12)
        kern_count = _u16(data, 14)
        records_end = 16 + glyph_count * self._GLYPH_RECORD_SIZE
        kerning_end = records_end + kern_count * self._KERN_RECORD_SIZE
        if kerning_end > len(data):
            raise ValueError("corrupt asset font records")

        self.glyphs = {}
        offset = 16
        for _ in range(glyph_count):
            codepoint = _u32(data, offset)
            width = _u16(data, offset + 4)
            height = _u16(data, offset + 6)
            bearing_x = _i16(data, offset + 8)
            bearing_y = _i16(data, offset + 10)
            advance = _i16(data, offset + 12)
            data_offset = _u32(data, offset + 14)
            data_length = _u32(data, offset + 18)
            if data_offset + data_length > len(data):
                raise ValueError("corrupt asset font bitmap")
            self.glyphs[codepoint] = (
                width, height, bearing_x, bearing_y, advance,
                data_offset, data_length)
            offset += self._GLYPH_RECORD_SIZE

        self.kerning = {}
        for _ in range(kern_count):
            left = _u32(data, offset)
            right = _u32(data, offset + 4)
            adjustment = _i16(data, offset + 8)
            self.kerning[(left << 21) | right] = adjustment
            offset += self._KERN_RECORD_SIZE
        self._view = memoryview(data)

    def _glyph(self, codepoint):
        glyph = self.glyphs.get(codepoint)
        if glyph is None:
            glyph = self.glyphs.get(63)
        return glyph

    def _kern(self, left, right):
        if left is None:
            return 0
        return self.kerning.get((left << 21) | right, 0)

    def measure(self, text):
        line_width = 0
        max_width = 0
        lines = 1
        previous = None
        for character in str(text):
            if character == "\n":
                max_width = max(max_width, line_width)
                line_width = 0
                previous = None
                lines += 1
                continue
            codepoint = ord(character)
            glyph = self._glyph(codepoint)
            if glyph is None:
                continue
            line_width += self._kern(previous, codepoint) + glyph[4]
            previous = codepoint
        return max(max_width, line_width), lines * self.line_height

    def draw(self, canvas, text, x, y, color, background=None):
        text = str(text)
        x = int(x)
        y = int(y)
        if background is not None:
            width, height = self.measure(text)
            if width > 0 and height > 0:
                canvas.fill_rect(x, y, x + width - 1, y + height - 1,
                                 background)

        cursor_x = x
        cursor_y = y
        previous = None
        for character in text:
            if character == "\n":
                cursor_x = x
                cursor_y += self.line_height
                previous = None
                continue
            codepoint = ord(character)
            glyph = self._glyph(codepoint)
            if glyph is None:
                continue
            width, height, bearing_x, bearing_y, advance, offset, length = glyph
            cursor_x += self._kern(previous, codepoint)
            if width > 0 and height > 0:
                draw_x = cursor_x + bearing_x
                draw_y = cursor_y + self.ascent + bearing_y
                canvas.blend_a4(
                    self._view[offset:offset + length], width, height,
                    draw_x, draw_y, color)
            cursor_x += advance
            previous = codepoint
        return cursor_x, cursor_y

    def draw_centered(self, canvas, text, center_x, y, color,
                      background=None):
        width, _ = self.measure(text)
        return self.draw(canvas, text, int(center_x) - width // 2, y,
                         color, background)
