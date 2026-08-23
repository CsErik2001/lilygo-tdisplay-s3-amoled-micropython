#!/usr/bin/env python3
"""Convert Bloub animated SVGs into efficient AMOLED face assets.

The Bloub export keeps the body static and animates the two eye capsules with
CSS matrix keyframes. The ESP32 only needs a full-screen RGB565 base image once
and then a small packed 4-bit grayscale eye patch for each animation frame.
"""

from __future__ import annotations

import argparse
import math
import re
import struct
from pathlib import Path

from PIL import Image, ImageDraw


MAGIC = b"BLG4"
HEADER = struct.Struct("<4sHHHHhhI")
BACKGROUND = (0, 0, 0)
BODY = (255, 255, 255)
EYES = (0, 0, 0)
BODY_RADIUS_SVG = 100.0


def parse_keyframes(svg_text: str, name: str) -> list[tuple[float, tuple[float, ...]]]:
    marker = "@keyframes " + name + "{"
    start = svg_text.find(marker)
    if start < 0:
        raise ValueError("missing CSS keyframes: " + name)
    body_start = start + len(marker)
    next_keyframes = svg_text.find("@keyframes ", body_start)
    style_end = svg_text.find("</style>", body_start)
    body_end = min(pos for pos in (next_keyframes, style_end) if pos >= 0)
    body = svg_text[body_start:body_end]
    pattern = re.compile(
        r"([0-9]+(?:\.[0-9]+)?)%\{transform:matrix\(([^)]+)\)\}"
    )
    frames = []
    for match in pattern.finditer(body):
        percent = float(match.group(1))
        matrix = tuple(float(value) for value in match.group(2).split(","))
        if len(matrix) != 6:
            raise ValueError("expected six values in " + name + " matrix")
        frames.append((percent, matrix))
    if len(frames) < 2:
        raise ValueError("not enough keyframes in " + name)
    return frames


def parse_eye_shape(svg_text: str) -> tuple[float, float]:
    match = re.search(
        r'<path d="M(-?[0-9.]+) (-?[0-9.]+)A[^"]+" class="oeil0"',
        svg_text,
    )
    if not match:
        raise ValueError("could not read the oeil0 capsule geometry")
    half_width = abs(float(match.group(1)))
    straight_half = abs(float(match.group(2)))
    if half_width <= 0 or straight_half < 0:
        raise ValueError("invalid eye capsule geometry")
    return half_width, straight_half


def capsule_points(
    half_width: float, straight_half: float, steps: int = 32
) -> list[tuple[float, float]]:
    points = []
    for index in range(steps + 1):
        angle = math.pi + (math.pi * index / steps)
        points.append(
            (
                math.cos(angle) * half_width,
                -straight_half + math.sin(angle) * half_width,
            )
        )
    for index in range(steps + 1):
        angle = math.pi * index / steps
        points.append(
            (
                math.cos(angle) * half_width,
                straight_half + math.sin(angle) * half_width,
            )
        )
    return points


def transform_points(
    points: list[tuple[float, float]], matrix: tuple[float, ...]
) -> list[tuple[float, float]]:
    a, b, c, d, e, f = matrix
    return [(a * x + c * y + e, b * x + d * y + f) for x, y in points]


def rgb565_bytes(image: Image.Image) -> bytes:
    rgb = image.convert("RGB")
    output = bytearray(rgb.width * rgb.height * 2)
    offset = 0
    pixels = (
        rgb.get_flattened_data()
        if hasattr(rgb, "get_flattened_data")
        else rgb.getdata()
    )
    for red, green, blue in pixels:
        value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        output[offset] = value & 0xFF
        output[offset + 1] = value >> 8
        offset += 2
    return bytes(output)


def gray4_bytes(image: Image.Image) -> bytes:
    grayscale = image.convert("L")
    output = bytearray((grayscale.width * grayscale.height + 1) // 2)
    pixels = (
        grayscale.get_flattened_data()
        if hasattr(grayscale, "get_flattened_data")
        else grayscale.getdata()
    )
    for index, value in enumerate(pixels):
        shade = (value * 15 + 127) // 255
        if index & 1:
            output[index >> 1] |= shade
        else:
            output[index >> 1] = shade << 4
    return bytes(output)


def render_assets(
    svg_path: Path,
    output_dir: Path,
    width: int,
    height: int,
    scale: float,
    fps: int,
    supersampling: int,
) -> tuple[Path, Path, dict[str, int]]:
    svg_text = svg_path.read_text(encoding="utf-8")
    left_frames = parse_keyframes(svg_text, "oeil0")
    right_frames = parse_keyframes(svg_text, "oeil1")
    left_percent = [item[0] for item in left_frames]
    right_percent = [item[0] for item in right_frames]
    if left_percent != right_percent:
        raise ValueError("left and right eye keyframe percentages differ")

    half_width, straight_half = parse_eye_shape(svg_text)
    shape = capsule_points(half_width, straight_half)
    transformed = []
    for (_, left), (_, right) in zip(left_frames, right_frames):
        transformed.append((transform_points(shape, left), transform_points(shape, right)))

    all_points = [point for pair in transformed for eye in pair for point in eye]
    padding = 5
    min_x = math.floor(min(point[0] for point in all_points) * scale) - padding
    max_x = math.ceil(max(point[0] for point in all_points) * scale) + padding
    min_y = math.floor(min(point[1] for point in all_points) * scale) - padding
    max_y = math.ceil(max(point[1] for point in all_points) * scale) + padding
    crop_width = max_x - min_x + 1
    crop_height = max_y - min_y + 1
    center_x = width // 2
    center_y = height // 2
    crop_x = center_x + min_x
    crop_y = center_y + min_y

    output_dir.mkdir(parents=True, exist_ok=True)
    base_path = output_dir / "face_base.rgb565"
    faces_dir = output_dir / "faces"
    faces_dir.mkdir(parents=True, exist_ok=True)
    animation_path = faces_dir / (svg_path.stem + ".blg4")

    ss = supersampling
    base = Image.new("RGB", (width * ss, height * ss), BACKGROUND)
    base_draw = ImageDraw.Draw(base)
    radius = BODY_RADIUS_SVG * scale * ss
    cx = center_x * ss
    cy = center_y * ss
    base_draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=BODY)
    base = base.resize((width, height), Image.Resampling.LANCZOS)
    base_path.write_bytes(rgb565_bytes(base))

    frame_bytes = (crop_width * crop_height + 1) // 2
    clean_patch = base.crop(
        (crop_x, crop_y, crop_x + crop_width, crop_y + crop_height)
    )
    with animation_path.open("wb") as output:
        output.write(
            HEADER.pack(
                MAGIC,
                crop_width,
                crop_height,
                len(transformed),
                fps,
                crop_x,
                crop_y,
                frame_bytes,
            )
        )
        output.write(gray4_bytes(clean_patch))
        for left, right in transformed:
            layer = Image.new(
                "RGBA", (crop_width * ss, crop_height * ss), (0, 0, 0, 0)
            )
            draw = ImageDraw.Draw(layer)
            for eye in (left, right):
                pixels = [
                    (
                        (x * scale - min_x) * ss,
                        (y * scale - min_y) * ss,
                    )
                    for x, y in eye
                ]
                draw.polygon(pixels, fill=EYES + (255,))
            layer = layer.resize((crop_width, crop_height), Image.Resampling.LANCZOS)
            frame = Image.alpha_composite(clean_patch.convert("RGBA"), layer)
            output.write(gray4_bytes(frame))

    metadata = {
        "display_width": width,
        "display_height": height,
        "body_diameter": round(BODY_RADIUS_SVG * scale * 2),
        "crop_x": crop_x,
        "crop_y": crop_y,
        "crop_width": crop_width,
        "crop_height": crop_height,
        "frames": len(transformed),
        "fps": fps,
        "frame_bytes": frame_bytes,
        "asset_bytes": HEADER.size + (len(transformed) + 1) * frame_bytes,
    }
    return base_path, animation_path, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "svg", type=Path, help="Bloub SVG file or a directory of face SVGs"
    )
    parser.add_argument("output", type=Path, help="asset output directory")
    parser.add_argument("--width", type=int, default=536)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--scale", type=float, default=1.05)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--supersampling", type=int, default=4)
    args = parser.parse_args()
    svg_paths = sorted(args.svg.glob("*.svg")) if args.svg.is_dir() else [args.svg]
    if not svg_paths:
        parser.error("no SVG files found")
    for svg_path in svg_paths:
        base, animation, metadata = render_assets(
            svg_path,
            args.output,
            args.width,
            args.height,
            args.scale,
            args.fps,
            args.supersampling,
        )
        print(svg_path.stem + ":", animation, metadata)
    print("base:", base)


if __name__ == "__main__":
    main()
