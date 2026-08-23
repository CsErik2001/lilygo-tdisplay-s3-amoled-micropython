#!/usr/bin/env python3
"""Draw compact animated system-state faces for the Bloub demo."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

from bloub_svg_to_assets import (
    BACKGROUND,
    BODY,
    BODY_RADIUS_SVG,
    HEADER,
    MAGIC,
    gray4_bytes,
)


INK = (0, 0, 0)
FRAMES = 60
FPS = 30


STATE_BOUNDS = {
    "listening": (-70, -55, 55, 55),
    "thinking": (-50, -65, 75, 45),
    "loading": (-55, -55, 55, 70),
    "speaking": (-55, -50, 55, 65),
    "success": (-60, -55, 60, 70),
    "warning": (-65, -55, 65, 75),
    "error": (-65, -55, 65, 65),
    "offline": (-65, -55, 65, 70),
}


class Canvas:
    def __init__(
        self,
        image: Image.Image,
        draw: ImageDraw.ImageDraw,
        min_x: int,
        min_y: int,
        scale: float,
        supersampling: int,
    ) -> None:
        self.image = image
        self.draw = draw
        self.min_x = min_x
        self.min_y = min_y
        self.scale = scale
        self.ss = supersampling

    @staticmethod
    def color(fill):
        return fill if len(fill) == 4 else fill + (255,)

    def point(self, x: float, y: float) -> tuple[float, float]:
        return (
            (x * self.scale - self.min_x) * self.ss,
            (y * self.scale - self.min_y) * self.ss,
        )

    def width(self, value: float) -> int:
        return max(1, round(value * self.scale * self.ss))

    def ellipse(
        self, cx: float, cy: float, rx: float, ry: float, fill=INK
    ) -> None:
        x0, y0 = self.point(cx - rx, cy - ry)
        x1, y1 = self.point(cx + rx, cy + ry)
        self.draw.ellipse((x0, y0, x1, y1), fill=self.color(fill))

    def line(self, points, width: float = 4, fill=INK) -> None:
        self.draw.line(
            [self.point(x, y) for x, y in points],
            fill=self.color(fill),
            width=self.width(width),
            joint="curve",
        )

    def polygon(self, points, fill=INK) -> None:
        self.draw.polygon(
            [self.point(x, y) for x, y in points], fill=self.color(fill)
        )

    def arc(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        start: float,
        end: float,
        width: float = 4,
        fill=INK,
    ) -> None:
        x0, y0 = self.point(cx - rx, cy - ry)
        x1, y1 = self.point(cx + rx, cy + ry)
        self.draw.arc(
            (x0, y0, x1, y1),
            start=start,
            end=end,
            fill=self.color(fill),
            width=self.width(width),
        )

    def capsule(
        self,
        cx: float,
        cy: float,
        half_width: float,
        half_height: float,
        angle: float = 0,
        scale_y: float = 1,
        fill=INK,
    ) -> None:
        straight = max(0, half_height - half_width)
        points = []
        radians = math.radians(angle)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        for side in (-1, 1):
            base_angle = math.pi if side < 0 else 0
            for index in range(17):
                theta = base_angle + math.pi * index / 16
                x = math.cos(theta) * half_width
                y = (side * straight + math.sin(theta) * half_width) * scale_y
                points.append(
                    (
                        cx + x * cosine - y * sine,
                        cy + x * sine + y * cosine,
                    )
                )
        self.polygon(points, fill=fill)


def blink(t: float, center: float = 0.52, width: float = 0.045) -> float:
    distance = abs(t - center)
    if distance >= width:
        return 1.0
    return 0.12 + 0.88 * distance / width


def draw_listening(canvas: Canvas, t: float) -> None:
    bob = math.sin(t * math.tau) * 1.5
    eye_scale = blink(t)
    canvas.capsule(-22, -15 + bob, 9, 21, -5, eye_scale)
    canvas.capsule(24, -15 - bob, 9, 21, 5, eye_scale)
    pulse = (math.sin(t * math.tau * 3) + 1) / 2
    for index, radius in enumerate((12, 22, 32)):
        shade = round(70 + 185 * max(0, pulse - index * 0.18))
        canvas.arc(-48, 13, radius, radius, 120, 240, 4, (shade, shade, shade))


def draw_thinking(canvas: Canvas, t: float) -> None:
    drift = math.sin(t * math.tau) * 3
    eye_scale = blink(t, 0.63)
    canvas.capsule(-18 + drift, -18, 9, 19, -12, eye_scale)
    canvas.capsule(24 + drift, -23, 9, 19, -12, eye_scale)
    for index, (x, y, radius) in enumerate(((45, -43, 4), (57, -52, 6), (72, -60, 8))):
        pulse = 0.65 + 0.35 * math.sin(t * math.tau + index * 0.8)
        shade = round(255 * pulse)
        canvas.ellipse(x, y, radius, radius, (shade, shade, shade))


def draw_loading(canvas: Canvas, t: float) -> None:
    canvas.ellipse(-20, -30, 7, 9)
    canvas.ellipse(20, -30, 7, 9)
    for index in range(8):
        angle = index * math.tau / 8
        phase = (index / 8 - t) % 1
        shade = round(35 + 220 * (1 - phase) ** 2)
        canvas.ellipse(
            math.cos(angle) * 28,
            25 + math.sin(angle) * 28,
            4.5,
            4.5,
            (shade, shade, shade),
        )


def draw_speaking(canvas: Canvas, t: float) -> None:
    eye_scale = blink(t, 0.72)
    canvas.capsule(-23, -22, 8, 18, 0, eye_scale)
    canvas.capsule(23, -22, 8, 18, 0, eye_scale)
    for index, x in enumerate((-24, -12, 0, 12, 24)):
        wave = (math.sin(t * math.tau * 4 + index * 1.25) + 1) / 2
        half_height = 4 + wave * (16 - abs(index - 2) * 1.5)
        canvas.capsule(x, 28, 3.5, half_height)


def draw_success(canvas: Canvas, t: float) -> None:
    lift = math.sin(t * math.pi) * 2
    canvas.arc(-24, -15 - lift, 17, 13, 200, 340, 6)
    canvas.arc(24, -15 - lift, 17, 13, 200, 340, 6)
    progress = min(1, t * 3)
    start = (-22, 30)
    middle = (-5, 47)
    end = (31, 10)
    if progress <= 0.38:
        part = progress / 0.38
        point = (
            start[0] + (middle[0] - start[0]) * part,
            start[1] + (middle[1] - start[1]) * part,
        )
        canvas.line((start, point), 7)
    else:
        canvas.line((start, middle), 7)
        part = (progress - 0.38) / 0.62
        point = (
            middle[0] + (end[0] - middle[0]) * part,
            middle[1] + (end[1] - middle[1]) * part,
        )
        canvas.line((middle, point), 7)


def draw_warning(canvas: Canvas, t: float) -> None:
    shake = math.sin(t * math.tau * 4) * 2.5 * math.sin(t * math.pi)
    canvas.capsule(-24 + shake, -29, 8, 17, 18)
    canvas.capsule(24 + shake, -29, 8, 17, -18)
    pulse = 1 + 0.04 * math.sin(t * math.tau * 2)
    triangle = ((0, -2), (-38, 57), (38, 57), (0, -2))
    canvas.line(((x * pulse + shake, y * pulse) for x, y in triangle), 5)
    canvas.capsule(shake, 28, 4, 14)
    canvas.ellipse(shake, 48, 4, 4)


def draw_error(canvas: Canvas, t: float) -> None:
    shake = math.sin(t * math.tau * 6) * 4 * math.sin(t * math.pi)
    for center in (-25, 25):
        canvas.line(((center - 10 + shake, -32), (center + 10 + shake, -10)), 6)
        canvas.line(((center + 10 + shake, -32), (center - 10 + shake, -10)), 6)
    canvas.line(
        ((-30 + shake, 35), (-16 + shake, 25), (0 + shake, 38),
         (16 + shake, 25), (30 + shake, 35)),
        6,
    )


def draw_offline(canvas: Canvas, t: float) -> None:
    droop = 2 + math.sin(t * math.tau) * 2
    canvas.arc(-23, -20 + droop, 15, 12, 15, 165, 6)
    canvas.arc(23, -20 + droop, 15, 12, 15, 165, 6)
    pulse = 0.55 + 0.45 * math.sin(t * math.pi) ** 2
    shade = round(255 * pulse)
    ink = (shade, shade, shade)
    canvas.arc(0, 42, 37, 32, 205, 335, 5, ink)
    canvas.arc(0, 42, 24, 21, 205, 335, 5, ink)
    canvas.arc(0, 42, 11, 10, 205, 335, 5, ink)
    canvas.ellipse(0, 43, 4, 4, ink)
    canvas.line(((-42, 4), (42, 65)), 6)


DRAWERS = {
    "listening": draw_listening,
    "thinking": draw_thinking,
    "loading": draw_loading,
    "speaking": draw_speaking,
    "success": draw_success,
    "warning": draw_warning,
    "error": draw_error,
    "offline": draw_offline,
}


def render_state(
    name: str,
    output_dir: Path,
    width: int,
    height: int,
    scale: float,
    supersampling: int,
) -> tuple[Path, dict[str, int]]:
    min_svg_x, min_svg_y, max_svg_x, max_svg_y = STATE_BOUNDS[name]
    padding = 5
    min_x = math.floor(min_svg_x * scale) - padding
    min_y = math.floor(min_svg_y * scale) - padding
    max_x = math.ceil(max_svg_x * scale) + padding
    max_y = math.ceil(max_svg_y * scale) + padding
    patch_width = max_x - min_x + 1
    patch_height = max_y - min_y + 1
    patch_x = width // 2 + min_x
    patch_y = height // 2 + min_y
    ss = supersampling

    base = Image.new("RGB", (width * ss, height * ss), BACKGROUND)
    base_draw = ImageDraw.Draw(base)
    radius = BODY_RADIUS_SVG * scale * ss
    center_x = width // 2 * ss
    center_y = height // 2 * ss
    base_draw.ellipse(
        (
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
        ),
        fill=BODY,
    )
    base = base.resize((width, height), Image.Resampling.LANCZOS)
    clean_patch = base.crop(
        (patch_x, patch_y, patch_x + patch_width, patch_y + patch_height)
    )

    def make_layer() -> tuple[Image.Image, Canvas]:
        image = Image.new(
            "RGBA", (patch_width * ss, patch_height * ss), (0, 0, 0, 0)
        )
        draw = ImageDraw.Draw(image)
        canvas = Canvas(image, draw, min_x, min_y, scale, ss)
        return image, canvas

    frame_bytes = (patch_width * patch_height + 1) // 2
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (name + ".blg4")
    with path.open("wb") as output:
        output.write(
            HEADER.pack(
                MAGIC,
                patch_width,
                patch_height,
                FRAMES,
                FPS,
                patch_x,
                patch_y,
                frame_bytes,
            )
        )
        output.write(gray4_bytes(clean_patch))
        for frame_index in range(FRAMES):
            layer, canvas = make_layer()
            DRAWERS[name](canvas, frame_index / (FRAMES - 1))
            layer = layer.resize(
                (patch_width, patch_height), Image.Resampling.LANCZOS
            )
            image = Image.alpha_composite(clean_patch.convert("RGBA"), layer)
            output.write(gray4_bytes(image))

    metadata = {
        "crop_x": patch_x,
        "crop_y": patch_y,
        "crop_width": patch_width,
        "crop_height": patch_height,
        "frames": FRAMES,
        "fps": FPS,
        "frame_bytes": frame_bytes,
        "asset_bytes": HEADER.size + (FRAMES + 1) * frame_bytes,
    }
    return path, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="face asset output directory")
    parser.add_argument("--width", type=int, default=536)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--scale", type=float, default=1.05)
    parser.add_argument("--supersampling", type=int, default=4)
    args = parser.parse_args()
    for name in DRAWERS:
        path, metadata = render_state(
            name,
            args.output,
            args.width,
            args.height,
            args.scale,
            args.supersampling,
        )
        print(name + ":", path, metadata)


if __name__ == "__main__":
    main()
