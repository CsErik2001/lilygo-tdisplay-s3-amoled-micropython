import unittest

import amoled_ui as ui


class MockDisplay:
    def __init__(self):
        self.calls = []

    def clear(self, color):
        self.calls.append(("clear", color))

    def fill_rect(self, x0, y0, x1, y1, color):
        self.calls.append(("fill_rect", x0, y0, x1, y1, color))

    def rect(self, x0, y0, x1, y1, color):
        self.calls.append(("rect", x0, y0, x1, y1, color))

    def text(self, text, x, y, color, scale=1, background=None):
        self.calls.append(("text", text, x, y, color, scale, background))


class MockTouch:
    def __init__(self, points=None):
        self.points = list(points or [])

    def read(self):
        if self.points:
            return self.points.pop(0)
        return None


class AmoledUiTests(unittest.TestCase):
    def test_label_only_redraws_after_change(self):
        display = MockDisplay()
        screen = ui.Screen(display, MockTouch())
        label = screen.add(ui.Label("Ready", 2, 3, width=60))

        screen.draw()
        first_call_count = len(display.calls)
        screen.draw()
        self.assertEqual(len(display.calls), first_call_count)

        label.set_text("Saved")
        screen.draw()
        self.assertGreater(len(display.calls), first_call_count)
        self.assertEqual(display.calls[-1][0:2], ("text", "Saved"))

    def test_button_fires_once_on_release(self):
        clicks = []
        touch = MockTouch([(15, 15, ui.EVENT_DOWN), (15, 15, ui.EVENT_UP)])
        screen = ui.Screen(MockDisplay(), touch)
        screen.add(ui.Button("OK", 10, 10, 50, 24, on_click=lambda: clicks.append(1)))

        screen.update()
        screen.update()
        screen.update()
        self.assertEqual(clicks, [1])

    def test_button_drag_outside_does_not_fire(self):
        clicks = []
        touch = MockTouch(
            [
                (15, 15, ui.EVENT_DOWN),
                (100, 100, ui.EVENT_CONTACT),
                (100, 100, ui.EVENT_UP),
            ]
        )
        screen = ui.Screen(MockDisplay(), touch)
        screen.add(ui.Button("OK", 10, 10, 50, 24, on_click=lambda: clicks.append(1)))

        screen.update()
        screen.update()
        screen.update()
        self.assertEqual(clicks, [])

    def test_keyboard_edits_focused_input(self):
        display = MockDisplay()
        touch = MockTouch()
        screen = ui.Screen(display, touch)
        field = screen.add(ui.TextInput(0, 0, 120, value="A"))
        keyboard = ui.Keyboard(0, 40, 300, 150)
        screen.set_keyboard(keyboard)
        screen.set_focus(field)

        key_index = next(
            index for index, key in enumerate(keyboard._keys) if key[5] == "1"
        )
        x, y, width, height = keyboard._keys[key_index][:4]
        touch.points.extend(
            [
                (x + width // 2, y + height // 2, ui.EVENT_DOWN),
                (x + width // 2, y + height // 2, ui.EVENT_UP),
            ]
        )

        screen.update()
        screen.update()
        self.assertEqual(field.value, "A1")

    def test_keyboard_backspace_and_done(self):
        submitted = []
        field = ui.TextInput(
            0,
            0,
            120,
            value="AB",
            on_submit=lambda value: submitted.append(value),
        )
        screen = ui.Screen(MockDisplay(), MockTouch())
        screen.add(field)
        keyboard = ui.Keyboard(0, 40, 300, 150, target=field)
        screen.set_keyboard(keyboard)
        screen.set_focus(field)

        backspace = next(i for i, key in enumerate(keyboard._keys) if key[5] == "\b")
        done = next(i for i, key in enumerate(keyboard._keys) if key[5] == "\n")
        keyboard._pressed_key = backspace
        key = keyboard._keys[backspace]
        keyboard.pointer_up(key[0] + 1, key[1] + 1)
        self.assertEqual(field.value, "A")

        keyboard._pressed_key = done
        key = keyboard._keys[done]
        keyboard.pointer_up(key[0] + 1, key[1] + 1)
        self.assertEqual(submitted, ["A"])
        self.assertIsNone(screen.focused)

    def test_text_input_enforces_max_length(self):
        field = ui.TextInput(0, 0, 100, value="ABCDE", max_length=3)
        self.assertEqual(field.value, "ABC")
        field.insert("Z")
        self.assertEqual(field.value, "ABC")

    def test_overlapping_widget_is_redrawn_above_dirty_widget(self):
        display = MockDisplay()
        screen = ui.Screen(display, MockTouch())
        lower = screen.add(ui.Label("LOW", 0, 0, width=40))
        screen.add(ui.Label("TOP", 10, 0, width=40))
        screen.draw()
        display.calls = []

        lower.set_text("NEW")
        screen.draw()
        drawn_text = [call[1] for call in display.calls if call[0] == "text"]
        self.assertEqual(drawn_text, ["NEW", "TOP"])


if __name__ == "__main__":
    unittest.main()
