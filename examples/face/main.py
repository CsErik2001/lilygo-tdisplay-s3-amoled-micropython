"""Cycle through the animated Bloub face pack and benchmark it."""

import gc
import struct
import time

import amoled


BASE_ASSET = "face_base.rgb565"
FACE_DIR = "faces"
FACE_NAMES = (
    "neutral",
    "listening",
    "thinking",
    "loading",
    "speaking",
    "success",
    "warning",
    "error",
    "offline",
    "attentive",
    "curious",
    "happy",
    "excited",
    "laughing",
    "proud",
    "shy",
    "confused",
    "suspicious",
    "unimpressed",
    "sad",
    "scared",
    "angry",
    "sleepy",
    "surprised",
)
HEADER_FORMAT = "<4sHHHHhhI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAGIC = b"BLG4"
REPORT_INTERVAL_MS = 3000
PREFETCH_CHUNK = 3072
BRIGHTNESS = 120
LABEL_Y = 230
LABEL_BACKGROUND = amoled.rgb(0, 0, 0)
LABEL_COLOR = amoled.rgb(255, 255, 255)


def _ticks_us():
    return time.ticks_us()


def _diff_us(new, old):
    return time.ticks_diff(new, old)


def _add_us(value, delta):
    return time.ticks_add(value, delta)


def _read_header(stream, name):
    raw = stream.read(HEADER_SIZE)
    if len(raw) != HEADER_SIZE:
        raise ValueError(name + " header is truncated")
    magic, width, height, frames, fps, x, y, frame_bytes = struct.unpack(
        HEADER_FORMAT, raw
    )
    if magic != MAGIC:
        raise ValueError(name + " uses an unsupported face format")
    if frame_bytes != (width * height + 1) // 2:
        raise ValueError(name + " has an invalid packed frame size")
    if frames < 2 or fps < 1:
        raise ValueError(name + " has invalid animation timing")
    return width, height, frames, fps, x, y, frame_bytes


def _load_first_face(name):
    started = _ticks_us()
    with open(FACE_DIR + "/" + name + ".blg4", "rb") as stream:
        metadata = _read_header(stream, name)
        payload = stream.read()
    expected = (metadata[2] + 1) * metadata[6]
    if len(payload) != expected:
        raise OSError(name + " animation payload is truncated")
    return (payload,) + metadata, _diff_us(_ticks_us(), started)


def _begin_prefetch(name):
    gc.collect()
    stream = open(FACE_DIR + "/" + name + ".blg4", "rb")
    metadata = _read_header(stream, name)
    payload = bytearray((metadata[2] + 1) * metadata[6])
    # name, stream, payload, writable view, cursor, metadata, active read time
    return [name, stream, payload, memoryview(payload), 0, metadata, 0]


def _prefetch_step(prefetch):
    stream = prefetch[1]
    if stream is None:
        return 0
    started = _ticks_us()
    cursor = prefetch[4]
    end = min(cursor + PREFETCH_CHUNK, len(prefetch[2]))
    target = prefetch[3][cursor:end]
    count = stream.readinto(target)
    if count != end - cursor:
        stream.close()
        raise OSError(prefetch[0] + " animation payload is truncated")
    prefetch[4] = end
    if end == len(prefetch[2]):
        stream.close()
        prefetch[1] = None
        prefetch[3] = None
    elapsed = _diff_us(_ticks_us(), started)
    prefetch[6] += elapsed
    return elapsed


def _finish_prefetch(prefetch):
    while prefetch[1] is not None:
        _prefetch_step(prefetch)
    face = (prefetch[2],) + prefetch[5]
    return face, prefetch[6]


def _blit_patch(display, face, frame_index):
    payload, width, height, _, _, x, y, frame_bytes = face
    display.blit_gray4(
        payload,
        x,
        y,
        x + width - 1,
        y + height - 1,
        frame_index * frame_bytes,
    )


def _draw_label(display, name):
    label = name.upper()
    x = (amoled.WIDTH - len(label) * 6) // 2
    display.fill_rect(0, 228, amoled.WIDTH - 1, amoled.HEIGHT - 1, LABEL_BACKGROUND)
    display.text(label, x, LABEL_Y, LABEL_COLOR)


def _play_face(display, name, face, next_name):
    _, _, _, frame_count, fps, _, _, _ = face
    frame_period_us = 1000000 // fps
    prefetch = _begin_prefetch(next_name)

    index = 0
    direction = 1
    completed_cycles = 0
    deadline = _ticks_us()
    report_started = deadline
    frames_rendered = 0
    late_frames = 0
    total_read_us = 0
    total_blit_us = 0
    max_read_us = 0
    max_blit_us = 0

    while completed_cycles < 1:
        blit_started = _ticks_us()
        # Packed frame zero is the clean background used between states.
        _blit_patch(display, face, index + 1)
        blit_finished = _ticks_us()
        read_us = _prefetch_step(prefetch)

        blit_us = _diff_us(blit_finished, blit_started)
        total_read_us += read_us
        total_blit_us += blit_us
        if read_us > max_read_us:
            max_read_us = read_us
        if blit_us > max_blit_us:
            max_blit_us = blit_us
        frames_rendered += 1

        index += direction
        if index >= frame_count:
            index = frame_count - 2
            direction = -1
        elif index < 0:
            index = 1
            direction = 1
            completed_cycles += 1

        deadline = _add_us(deadline, frame_period_us)
        remaining_us = _diff_us(deadline, _ticks_us())
        if remaining_us > 0:
            time.sleep_us(remaining_us)
        else:
            late_frames += 1
            if remaining_us < -frame_period_us:
                deadline = _ticks_us()

        now = _ticks_us()
        elapsed_us = _diff_us(now, report_started)
        if elapsed_us >= REPORT_INTERVAL_MS * 1000:
            gc.collect()
            print(
                "FACE_BENCH name={} fps={:.2f} read_ms={:.3f} "
                "blit_ms={:.3f} max_read_ms={:.3f} max_blit_ms={:.3f} "
                "duty={:.1f}% late={} mem_free={}".format(
                    name,
                    frames_rendered * 1000000 / elapsed_us,
                    total_read_us / frames_rendered / 1000,
                    total_blit_us / frames_rendered / 1000,
                    max_read_us / 1000,
                    max_blit_us / 1000,
                    (total_read_us + total_blit_us) * 100 / elapsed_us,
                    late_frames,
                    gc.mem_free(),
                )
            )
            deadline = _ticks_us()
            report_started = deadline
            frames_rendered = 0
            late_frames = 0
            total_read_us = 0
            total_blit_us = 0
            max_read_us = 0
            max_blit_us = 0

    return _finish_prefetch(prefetch)


def main():
    display = amoled.Display()
    display.rotation(0)
    display.brightness(BRIGHTNESS)
    display.draw_image(BASE_ASSET, 0, 0, amoled.WIDTH, amoled.HEIGHT)

    state_index = 0
    face, ready_us = _load_first_face(FACE_NAMES[state_index])
    print(
        "FACE_PACK_START states={} brightness={} mem_free={}".format(
            len(FACE_NAMES), BRIGHTNESS, gc.mem_free()
        )
    )
    while True:
        name = FACE_NAMES[state_index]
        next_index = (state_index + 1) % len(FACE_NAMES)
        next_name = FACE_NAMES[next_index]
        gc.collect()
        print(
            "FACE_STATE name={} ready_ms={:.1f} patch={}x{} bytes={} mem_free={}".format(
                name,
                ready_us / 1000,
                face[1],
                face[2],
                len(face[0]),
                gc.mem_free(),
            )
        )
        _draw_label(display, name)
        next_face, next_ready_us = _play_face(display, name, face, next_name)
        _blit_patch(display, face, 0)
        face = None
        gc.collect()
        face = next_face
        ready_us = next_ready_us
        state_index = next_index


main()
