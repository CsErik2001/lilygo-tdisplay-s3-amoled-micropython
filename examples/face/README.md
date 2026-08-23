# Animated face pack benchmark

This example converts a directory of Bloub face SVGs into one static 536 x 240
RGB565 base image and compact eye-only animation files. It also includes eight
drawn system states: `listening`, `thinking`, `loading`, `speaking`, `success`,
`warning`, `error`, and `offline`. The demo cycles through all 24 states,
labels the active animation along the bottom of the display, and reports load
time, frame timing, missed deadlines, renderer duty cycle, and heap usage over
serial.

Each animation frame is stored as packed 4-bit grayscale. The native
`blit_gray4()` display method expands it directly to RGB565 while transferring
it to the panel. Only the small rectangle containing the animated eyes is
redrawn. The next state is prefetched from flash in small chunks during the
current animation's spare frame time. Two states at most are cached in PSRAM,
keeping transitions smooth and both flash and RAM use bounded even when the
pack contains many expressions.

Generate all assets with Pillow installed:

```bash
python3 tools/bloub_svg_to_assets.py /path/to/faces examples/face/assets
python3 tools/generate_system_faces.py examples/face/assets/faces
```

The input directory currently contains these states: `angry`, `attentive`,
`confused`, `curious`, `excited`, `happy`, `laughing`, `neutral`, `proud`,
`sad`, `scared`, `shy`, `sleepy`, `surprised`, `suspicious`, and
`unimpressed`.

Upload the pack and start the benchmark:

```bash
mpremote connect /dev/cu.usbmodem101 cp examples/face/assets/face_base.rgb565 :face_base.rgb565
mpremote connect /dev/cu.usbmodem101 cp -r examples/face/assets/faces :
mpremote connect /dev/cu.usbmodem101 cp examples/face/main.py :main.py
mpremote connect /dev/cu.usbmodem101 reset
```

Each SVG contains a 2.967-second forward pass with alternate direction and 90
source keyframes at 30 FPS. The demo plays one complete forward/reverse cycle
before advancing to the next state. The drawn system states use 60 frames at
30 FPS. Frame zero in every generated file is a pixel-identical clean crop of
the base image, preventing seams or remnants when states use different eye and
icon positions.
