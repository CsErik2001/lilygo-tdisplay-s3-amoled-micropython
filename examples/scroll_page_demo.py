"""ScrollView + PageView demo — swipe pages, scroll lists."""

import time
import amoled
import amoled_ui as ui


def main():
    display = amoled.Display()
    display.brightness(220)
    touch = amoled.Touch()

    pages = ui.PageView(display, touch)

    pages.add_page([
        ui.Title("Page 1 — Swipe →", x=10, y=8),
        ui.Label("Swipe right to see Page 2", x=10, y=40, color=ui._rgb(128, 128, 128)),
        ui.Button("Tap me", x=10, y=70, width=120, height=28,
                  on_click=lambda: print("button on page 1")),
        ui.Slider(x=10, y=110, width=300, min_value=0, max_value=255, value=128,
                  on_change=display.brightness),
        ui.Label("Brightness", x=10, y=150),
    ])

    scroll = ui.ScrollView(x=10, y=60, width=516, height=170)
    for i in range(20):
        scroll.add(ui.Label(f"Scroll item {i + 1}", x=0, y=i * 24, width=516))
    pages.add_page([
        ui.Title("Page 2 — Scroll ↓", x=10, y=8),
        ui.Label("Drag the list below", x=10, y=40, color=ui._rgb(128, 128, 128)),
        scroll,
    ])

    pages.add_page([
        ui.Title("Page 3 — Done", x=10, y=8),
        ui.Label("Side button = sleep/wake", x=10, y=40, color=ui._rgb(128, 128, 128)),
        ui.Button("Last page", x=10, y=70, width=120, height=28,
                  on_click=lambda: print("page 3")),
    ])

    pages.run()


main()
