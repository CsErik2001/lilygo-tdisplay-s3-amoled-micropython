#!/usr/bin/env python3
import argparse
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


DISPLAY_LANDSCAPE = (536, 240)
DISPLAY_PORTRAIT = (240, 536)


def parse_size(value):
    if value is None:
        return None
    if "x" not in value.lower():
        raise argparse.ArgumentTypeError("formatum: 536x240")
    w, h = value.lower().split("x", 1)
    return int(w), int(h)


def parse_hex_color(value):
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise argparse.ArgumentTypeError("formatum: RRGGBB vagy #RRGGBB")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def write_amg0(path, width, height, pixels):
    with open(path, "wb") as fp:
        fp.write(b"AMG0")
        fp.write(struct.pack("<HH", width, height))
        for r, g, b in pixels:
            fp.write(struct.pack("<H", rgb565(r, g, b)))


def fit_size(src_w, src_h, canvas_w, canvas_h, fit):
    if fit == "stretch":
        return canvas_w, canvas_h
    scale_w = canvas_w / src_w
    scale_h = canvas_h / src_h
    scale = max(scale_w, scale_h) if fit == "cover" else min(scale_w, scale_h)
    return max(1, round(src_w * scale)), max(1, round(src_h * scale))


def convert_with_pillow(args, canvas):
    try:
        from PIL import Image
    except ImportError:
        return False

    img = Image.open(args.input).convert("RGB")
    if args.rotate:
        img = img.rotate(-args.rotate, expand=True)

    if args.resize:
        img = img.resize(args.resize, Image.Resampling.LANCZOS)
        write_amg0(args.output, img.width, img.height, img.getdata())
        return True

    if canvas is None:
        write_amg0(args.output, img.width, img.height, img.getdata())
        return True

    target = fit_size(img.width, img.height, canvas[0], canvas[1], args.fit)
    img = img.resize(target, Image.Resampling.LANCZOS)

    bg = args.bg
    out = Image.new("RGB", canvas, bg)
    x = (canvas[0] - img.width) // 2
    y = (canvas[1] - img.height) // 2
    out.paste(img, (x, y))
    write_amg0(args.output, out.width, out.height, out.getdata())
    return True


def sips_props(path):
    out = subprocess.check_output(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    width = height = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("pixelWidth:"):
            width = int(line.split(":", 1)[1])
        elif line.startswith("pixelHeight:"):
            height = int(line.split(":", 1)[1])
    if width is None or height is None:
        raise RuntimeError("sips nem tudta kiolvasni a kep meretet")
    return width, height


def read_bmp_rgb(path):
    data = Path(path).read_bytes()
    if data[:2] != b"BM":
        raise RuntimeError("sips nem BMP-t irt")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    if dib_size < 40:
        raise RuntimeError(f"nem tamogatott BMP header: {dib_size}")
    width = struct.unpack_from("<i", data, 18)[0]
    height_signed = struct.unpack_from("<i", data, 22)[0]
    planes = struct.unpack_from("<H", data, 26)[0]
    bpp = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]
    if planes != 1 or compression != 0 or bpp not in (24, 32):
        raise RuntimeError(f"nem tamogatott BMP: bpp={bpp}, compression={compression}")

    height = abs(height_signed)
    top_down = height_signed < 0
    row_stride = ((width * bpp + 31) // 32) * 4
    bytes_per_px = bpp // 8
    rows = []
    for y in range(height):
        src_y = y if top_down else (height - 1 - y)
        row_start = pixel_offset + src_y * row_stride
        row = []
        for x in range(width):
            px = row_start + x * bytes_per_px
            b, g, r = data[px], data[px + 1], data[px + 2]
            row.append((r, g, b))
        rows.append(row)
    return width, height, rows


def convert_with_sips(args, canvas):
    if shutil.which("sips") is None:
        return False

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        work = tmp_dir / "work.img"
        rotated = tmp_dir / "rotated.img"
        resized = tmp_dir / "resized.img"
        bmp = tmp_dir / "image.bmp"

        work.write_bytes(Path(args.input).read_bytes())
        current = work
        if args.rotate:
            subprocess.check_call(
                ["sips", "-r", str(args.rotate), str(current), "--out", str(rotated)],
                stdout=subprocess.DEVNULL,
            )
            current = rotated

        src_w, src_h = sips_props(current)
        if args.resize:
            target = args.resize
            canvas = None
        elif canvas is not None:
            target = fit_size(src_w, src_h, canvas[0], canvas[1], args.fit)
        else:
            target = (src_w, src_h)

        subprocess.check_call(
            ["sips", "-z", str(target[1]), str(target[0]), str(current), "--out", str(resized)],
            stdout=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["sips", "-s", "format", "bmp", str(resized), "--out", str(bmp)],
            stdout=subprocess.DEVNULL,
        )
        img_w, img_h, rows = read_bmp_rgb(bmp)

        if canvas is None:
            pixels = [pixel for row in rows for pixel in row]
            write_amg0(args.output, img_w, img_h, pixels)
            return True

        bg = args.bg
        canvas_w, canvas_h = canvas
        out = [bg] * (canvas_w * canvas_h)
        start_x = (canvas_w - img_w) // 2
        start_y = (canvas_h - img_h) // 2
        for sy, row in enumerate(rows):
            dy = start_y + sy
            if dy < 0 or dy >= canvas_h:
                continue
            for sx, pixel in enumerate(row):
                dx = start_x + sx
                if 0 <= dx < canvas_w:
                    out[dy * canvas_w + dx] = pixel

        write_amg0(args.output, canvas_w, canvas_h, out)
        return True


def main():
    parser = argparse.ArgumentParser(description="Kep konvertalasa AMG0 RGB565 .bin formatumba.")
    parser.add_argument("input", help="bemeneti kep, pl. image.png vagy image.jpg")
    parser.add_argument("output", help="kimeneti .bin")
    parser.add_argument("--resize", type=parse_size, help="pontos kimeneti meret, pl. 536x240")
    parser.add_argument("--canvas", type=parse_size, help="vaszon meret, pl. 536x240")
    parser.add_argument("--orientation", choices=("landscape", "portrait"), help="shortcut: landscape=536x240, portrait=240x536")
    parser.add_argument("--fit", choices=("contain", "cover", "stretch"), default="contain")
    parser.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0)
    parser.add_argument("--bg", type=parse_hex_color, default=(0, 0, 0), help="hatter szin, pl. 000000")
    args = parser.parse_args()

    canvas = args.canvas
    if args.orientation == "landscape":
        canvas = DISPLAY_LANDSCAPE
    elif args.orientation == "portrait":
        canvas = DISPLAY_PORTRAIT

    if not convert_with_pillow(args, canvas) and not convert_with_sips(args, canvas):
        raise SystemExit("Pillow vagy macOS sips kell a konvertalashoz")

    print(f"{args.output}: AMG0 RGB565")


if __name__ == "__main__":
    main()
