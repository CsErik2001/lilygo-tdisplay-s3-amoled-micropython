"""WiFi connection demo — uses the ``connect_wifi`` module.

Upload ``connect_wifi.py`` to the board alongside this file.
"""

import amoled
import connect_wifi as wifi

display = amoled.Display()
display.brightness(220)
touch = amoled.Touch()

ssid, ip = wifi.run(display, touch)
print(f"Connected to {ssid} at {ip}")

display.clear(amoled.rgb(0, 0, 0))
display.text("Connected!", 12, 12, amoled.rgb(0, 255, 0), 2)
display.text(f"{ssid}", 12, 34, amoled.rgb(255, 255, 255), 1)
display.text(f"IP: {ip}", 12, 52, amoled.rgb(255, 255, 255), 1)
