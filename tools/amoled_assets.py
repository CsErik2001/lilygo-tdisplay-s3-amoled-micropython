#!/usr/bin/env python3
"""Compile images and fonts into fast AMOLED runtime assets.

Shared TGI1/TGF1 asset format with the Waveshare project: opaque RGB565
images, recolorable A4 alpha masks, full-color RGB565+A4 images and
anti-aliased pre-rasterized fonts. Loaded on-device by
``amoled_assets.py``, drawn with the native renderers in
``amoled_canvas.Canvas``.
"""

import argparse
import io
import json
import shutil
import struct
import subprocess
from pathlib import Path


IMAGE_RGB565 = 1
IMAGE_A4 = 2
IMAGE_RGB565_A4 = 3
FORMAT_IDS = {
    "rgb565": IMAGE_RGB565,
    "a4": IMAGE_A4,
    "rgb565a4": IMAGE_RGB565_A4,
}
HUNGARIAN = "áéíóöőúüűÁÉÍÓÖŐÚÜŰ"


def pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required: python3 -m pip install pillow") from exc
    return Image, ImageDraw, ImageFont


def pixels(image):
    flattened = getattr(image, "get_flattened_data", None)
    return flattened() if callable(flattened) else image.getdata()


def parse_size(value):
    if value is None or isinstance(value, tuple):
        return value
    parts = str(value).lower().split("x", 1)
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("size must look like 128x128")
    width, height = int(parts[0]), int(parts[1])
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("size must be positive")
    return width, height


def parse_color(value):
    value = str(value).lstrip("#")
    if len(value) not in (6, 8):
        raise argparse.ArgumentTypeError("color must be RRGGBB or RRGGBBAA")
    channels = tuple(int(value[index:index + 2], 16)
                     for index in range(0, len(value), 2))
    return channels + (255,) if len(channels) == 3 else channels


def rgb565(red, green, blue):
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


def pack_a4(values):
    result = bytearray((len(values) + 1) // 2)
    for index, value in enumerate(values):
        nibble = max(0, min(15, (int(value) + 8) // 17))
        if index & 1:
            result[index >> 1] |= nibble
        else:
            result[index >> 1] = nibble << 4
    return bytes(result)


def load_svg(path, requested_size=None):
    Image, _, _ = pillow()
    try:
        import cairosvg
        kwargs = {}
        if requested_size is not None:
            kwargs["output_width"], kwargs["output_height"] = requested_size
        rendered = cairosvg.svg2png(url=str(path), **kwargs)
        return Image.open(io.BytesIO(rendered)).convert("RGBA")
    except (ImportError, OSError):
        pass

    converter = shutil.which("rsvg-convert")
    if converter is not None:
        command = [converter, str(path)]
        if requested_size is not None:
            command[1:1] = ["-w", str(requested_size[0]),
                            "-h", str(requested_size[1])]
        rendered = subprocess.check_output(command)
        return Image.open(io.BytesIO(rendered)).convert("RGBA")

    node = shutil.which("node")
    if node is not None:
        script = (
            "const sharp=require('sharp');"
            "let p=sharp(process.argv[1],{density:192});"
            "const w=Number(process.argv[2]),h=Number(process.argv[3]);"
            "if(w&&h)p=p.resize(w,h,{fit:'fill'});"
            "p.png().toBuffer().then(b=>process.stdout.write(b))"
            ".catch(e=>{console.error(e.message);process.exit(1)});"
        )
        width, height = requested_size or (0, 0)
        try:
            rendered = subprocess.check_output(
                [node, "-e", script, str(path), str(width), str(height)],
                stderr=subprocess.DEVNULL)
            return Image.open(io.BytesIO(rendered)).convert("RGBA")
        except subprocess.CalledProcessError:
            pass

    raise SystemExit(
        "SVG support needs CairoSVG, rsvg-convert, or Node.js sharp; "
        "install tools/requirements.txt")


def load_image(path, requested_size=None):
    Image, _, _ = pillow()
    path = Path(path)
    if path.suffix.lower() == ".svg":
        return load_svg(path, requested_size)
    return Image.open(path).convert("RGBA")


def fit_image(image, resize=None, canvas=None, fit="contain", background=(0, 0, 0, 0)):
    Image, _, _ = pillow()
    if resize is not None:
        return image.resize(resize, Image.Resampling.LANCZOS)
    if canvas is None:
        return image
    if fit == "stretch":
        scaled = image.resize(canvas, Image.Resampling.LANCZOS)
    else:
        scale_x = canvas[0] / image.width
        scale_y = canvas[1] / image.height
        scale = max(scale_x, scale_y) if fit == "cover" else min(scale_x, scale_y)
        target = (max(1, round(image.width * scale)),
                  max(1, round(image.height * scale)))
        scaled = image.resize(target, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", canvas, background)
    x = (canvas[0] - scaled.width) // 2
    y = (canvas[1] - scaled.height) // 2
    output.alpha_composite(scaled, (x, y))
    return output


def compile_image(args):
    Image, _, _ = pillow()
    source_size = args.resize or args.canvas
    image = load_image(args.input, source_size)
    if args.trim:
        alpha_box = image.getchannel("A").getbbox()
        if alpha_box is not None:
            image = image.crop(alpha_box)
    image = fit_image(image, args.resize, args.canvas, args.fit, args.background)

    alpha = list(pixels(image.getchannel("A")))
    format_name = args.format
    if format_name == "auto":
        format_name = "rgb565a4" if min(alpha, default=255) < 255 else "rgb565"
    format_id = FORMAT_IDS[format_name]
    rgba = list(pixels(image))

    colors = bytearray()
    if format_id in (IMAGE_RGB565, IMAGE_RGB565_A4):
        for red, green, blue, opacity in rgba:
            if format_id == IMAGE_RGB565 and opacity < 255:
                bg_r, bg_g, bg_b, _ = args.background
                red = (red * opacity + bg_r * (255 - opacity) + 127) // 255
                green = (green * opacity + bg_g * (255 - opacity) + 127) // 255
                blue = (blue * opacity + bg_b * (255 - opacity) + 127) // 255
            colors.extend(struct.pack("<H", rgb565(red, green, blue)))

    mask = b""
    if format_id in (IMAGE_A4, IMAGE_RGB565_A4):
        if args.mask_source == "luma" or (
                args.mask_source == "auto" and min(alpha, default=255) == 255):
            mask_values = [
                ((54 * red + 183 * green + 19 * blue) >> 8) * opacity // 255
                for red, green, blue, opacity in rgba]
        else:
            mask_values = alpha
        mask = pack_a4(mask_values)

    payload = bytes(colors) + mask
    header = struct.pack(
        "<4sHHBBHI", b"TGI1", image.width, image.height,
        format_id, 0, 0, len(payload))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(header + payload)
    if args.preview:
        preview = Path(args.preview)
        preview.parent.mkdir(parents=True, exist_ok=True)
        image.save(preview)
    print(f"{output}: {image.width}x{image.height} {format_name}, "
          f"{len(header) + len(payload)} bytes")


def charset(value, extra=""):
    if value == "ascii":
        characters = "".join(chr(code) for code in range(32, 127))
    elif value == "latin-hungarian":
        characters = "".join(chr(code) for code in range(32, 127)) + HUNGARIAN
    else:
        characters = value
    characters += extra
    characters += " ?"
    return "".join(dict.fromkeys(characters))


def compile_font(args):
    Image, ImageDraw, ImageFont = pillow()
    font = ImageFont.truetype(str(args.input), args.size)
    if getattr(args, 'style', None):
        font.set_variation_by_name(args.style)
    ascent, descent = font.getmetrics()
    line_height = ascent + descent + args.line_gap
    characters = charset(args.charset, args.text or "")
    glyphs = []

    for character in characters:
        bbox = font.getbbox(character, anchor="ls")
        if bbox is None:
            continue
        left, top, right, bottom = bbox
        width = max(0, right - left)
        height = max(0, bottom - top)
        advance = int(round(font.getlength(character)))
        if width and height:
            bitmap = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(bitmap)
            draw.text((-left, -top), character, font=font,
                      fill=255, anchor="ls")
            packed = pack_a4(list(pixels(bitmap)))
        else:
            packed = b""
        glyphs.append({
            "codepoint": ord(character),
            "width": width,
            "height": height,
            "bearing_x": left,
            "bearing_y": top,
            "advance": advance,
            "bitmap": packed,
        })

    kerning = []
    if not args.no_kerning:
        advances = {item["codepoint"]: item["advance"] for item in glyphs}
        for left in characters:
            left_code = ord(left)
            if left_code not in advances:
                continue
            for right in characters:
                right_code = ord(right)
                if right_code not in advances:
                    continue
                pair = int(round(font.getlength(left + right)))
                adjustment = pair - advances[left_code] - advances[right_code]
                if adjustment:
                    kerning.append((left_code, right_code, adjustment))

    header_size = 16
    glyph_record_size = 22
    kern_record_size = 10
    bitmap_offset = (header_size + len(glyphs) * glyph_record_size +
                     len(kerning) * kern_record_size)
    records = bytearray()
    bitmaps = bytearray()
    for item in glyphs:
        records.extend(struct.pack(
            "<IHHhhhII", item["codepoint"], item["width"], item["height"],
            item["bearing_x"], item["bearing_y"], item["advance"],
            bitmap_offset + len(bitmaps), len(item["bitmap"])))
        bitmaps.extend(item["bitmap"])
    kern_records = b"".join(
        struct.pack("<IIh", left, right, adjustment)
        for left, right, adjustment in kerning)
    header = struct.pack(
        "<4sHhhHHH", b"TGF1", args.size, ascent, descent,
        line_height, len(glyphs), len(kerning))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(header + records + kern_records + bitmaps)
    print(f"{output}: {args.size}px, {len(glyphs)} glyphs, "
          f"{len(kerning)} kern pairs, {output.stat().st_size} bytes")


def manifest_path(base, value):
    path = Path(value)
    return path if path.is_absolute() else base / path


def build_manifest(args):
    manifest_file = Path(args.manifest).resolve()
    base = manifest_file.parent
    config = json.loads(manifest_file.read_text(encoding="utf-8"))
    for item in config.get("images", []):
        compile_image(argparse.Namespace(
            input=manifest_path(base, item["input"]),
            output=manifest_path(base, item["output"]),
            resize=parse_size(item.get("resize")),
            canvas=parse_size(item.get("canvas")),
            fit=item.get("fit", "contain"),
            background=parse_color(item.get("background", "00000000")),
            format=item.get("format", "auto"),
            mask_source=item.get("mask_source", "auto"),
            trim=bool(item.get("trim", False)),
            preview=(manifest_path(base, item["preview"])
                     if item.get("preview") else None),
        ))
    for item in config.get("fonts", []):
        compile_font(argparse.Namespace(
            input=manifest_path(base, item["input"]),
            output=manifest_path(base, item["output"]),
            size=int(item["size"]),
            charset=item.get("charset", "latin-hungarian"),
            text=item.get("text", ""),
            line_gap=int(item.get("line_gap", 0)),
            no_kerning=not bool(item.get("kerning", True)),
            style=item.get("style"),
        ))


def parser():
    root = argparse.ArgumentParser(
        description="Compile fast images and fonts for the AMOLED UI")
    commands = root.add_subparsers(dest="command", required=True)

    image = commands.add_parser("image", help="compile PNG/JPEG/SVG")
    image.add_argument("input", type=Path)
    image.add_argument("output", type=Path)
    image.add_argument("--resize", type=parse_size)
    image.add_argument("--canvas", type=parse_size)
    image.add_argument("--fit", choices=("contain", "cover", "stretch"),
                       default="contain")
    image.add_argument("--background", type=parse_color,
                       default=(0, 0, 0, 0))
    image.add_argument("--format",
                       choices=("auto", "rgb565", "a4", "rgb565a4"),
                       default="auto")
    image.add_argument("--mask-source", choices=("auto", "alpha", "luma"),
                       default="auto")
    image.add_argument("--trim", action="store_true")
    image.add_argument("--preview")
    image.set_defaults(func=compile_image)

    font = commands.add_parser("font", help="compile TTF/OTF font")
    font.add_argument("input", type=Path)
    font.add_argument("output", type=Path)
    font.add_argument("--size", type=int, required=True)
    font.add_argument("--charset", default="latin-hungarian",
                      help="ascii, latin-hungarian, or literal characters")
    font.add_argument("--text", default="",
                      help="extra glyphs to include")
    font.add_argument("--line-gap", type=int, default=0)
    font.add_argument("--no-kerning", action="store_true")
    font.add_argument("--style", help="named variable-font instance, e.g. Regular")
    font.set_defaults(func=compile_font)

    build = commands.add_parser("build", help="compile a JSON manifest")
    build.add_argument("manifest", type=Path)
    build.set_defaults(func=build_manifest)
    return root


def main():
    args = parser().parse_args()
    if getattr(args, "size", 1) <= 0:
        raise SystemExit("font size must be positive")
    args.func(args)


if __name__ == "__main__":
    main()
