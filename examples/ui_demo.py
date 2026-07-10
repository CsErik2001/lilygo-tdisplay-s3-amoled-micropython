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

keyboard = ui.Keyboard(x=0, y=72, width=amoled.WIDTH, height=168)
screen.set_keyboard(keyboard)
screen.set_focus(name)
screen.run()
