import amoled
import amoled_ui as ui


display = amoled.Display()
display.brightness(220)
touch = amoled.Touch()

theme = ui.Theme(accent=amoled.rgb(0, 200, 255))
screen = ui.Screen(display, touch, theme=theme)

screen.add(ui.Title("Profile", x=12, y=8))

name = screen.add(
    ui.TextInput(
        x=12,
        y=36,
        width=250,
        height=30,
        placeholder="Name",
        max_length=24,
    )
)

status = screen.add(
    ui.Label(
        "Not saved",
        x=380,
        y=43,
        width=144,
        color=theme.muted,
    )
)


def save():
    status.color = theme.foreground
    status.set_text("Saved: " + (name.value or "-"))


screen.add(
    ui.Button(
        "Save",
        x=276,
        y=36,
        width=90,
        height=30,
        on_click=save,
    )
)

screen.add(
    ui.Switch(
        "Online",
        x=380,
        y=72,
        value=True,
        on_change=lambda value: status.set_text("Online" if value else "Offline"),
    )
)

screen.add(
    ui.Checkbox(
        "Remember",
        x=380,
        y=106,
        checked=True,
    )
)

screen.add(ui.Label("Brightness", x=380, y=142, width=144))
screen.add(
    ui.Slider(
        x=380,
        y=160,
        width=144,
        min_value=20,
        max_value=255,
        value=220,
        step=5,
        on_change=display.brightness,
    )
)

keyboard = ui.Keyboard(x=0, y=72, width=368, height=168)
screen.set_keyboard(keyboard)
screen.set_focus(name)
screen.run()
