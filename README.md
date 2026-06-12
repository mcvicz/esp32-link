# esp32-link

*Aplikacja okienkowa na system GNU/Linux do komunikacji z płytką ESP32*

Project for the AGH course on object-oriented design (prof. Cyganek). A Linux
desktop app written in Python with PySide6 that talks to an ESP32-WROOM-32 over
Wi-Fi. The board runs a small AsyncWebSocket server in AP mode and pushes
telemetry (chip temperature, free heap, RSSI) at 2 Hz; the app draws three
live charts and lets you toggle the onboard LED or send a ping.

The point of the exercise is the design, not the gadget — the architecture and
the patterns used are documented in [`docs/`](docs/). The hardware demo is
just an excuse to have something to design *around*.

![Demo of the running app, GUI on the left, ESP32 serial monitor on the right](docs/screenshots/demo.png)

*Left: the desktop GUI with three live plots after about 4½ minutes of uptime.
Right: the ESP32 serial monitor showing boot lines, an incoming client, and a
log of `[cmd]` actions as the user clicked Toggle LED and Ping in the GUI.*

## Hardware

- ESP32-WROOM-32 dev board (CP2102 USB-UART), the kind with an onboard blue
  LED on GPIO 2.
- USB-A cable (data, not charge-only).
- A laptop with a 2.4 GHz Wi-Fi adapter; the ESP32 only does 2.4 GHz.

## Stack

- **Desktop:** Python 3.12, PySide6 (Qt 6), pyqtgraph, `websockets`, `uv` for
  env management.
- **Firmware:** PlatformIO + Arduino-ESP32, ESPAsyncWebServer + AsyncTCP,
  ArduinoJson v7.
- **Docs:** Markdown + PlantUML, pandoc for the optional PDF build.
- **CI:** GitHub Actions (Python tests + firmware compile).

## Quickstart (developer / repeat run)

```bash
# desktop
cd desktop
uv sync                # first time
uv run esp32-link      # launch the GUI
uv run pytest          # run the test suite

# firmware
cd firmware
pio run                       # build
pio run --target upload       # flash via USB
pio device monitor            # 115200 baud serial console
```

On Windows where `pio` isn't on PATH, `python -m platformio ...` works the same.

The GUI defaults to `ws://192.168.4.1:81/ws`. Connect the host Wi-Fi to the
`ESP32-Console` SSID (password `esp32pass`) before clicking Connect.

## Runbook (first-time tester / grader)

If you've just cloned this fresh and want the full demo running from zero, this
is the path I'd take. It assumes Linux (or WSL2 on Windows with WSLg). About
10 minutes of wall time, most of it spent on PlatformIO downloading the ESP32
toolchain on first build.

### 1. Install the toolchains

```bash
# uv (Python env manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# PlatformIO (for the firmware)
pip install --user platformio    # or: pipx install platformio
```

### 2. Build and flash the firmware

Plug the ESP32 into a USB port (data cable!). Then:

```bash
cd firmware
pio device list                  # confirm the board enumerates as COMx / /dev/ttyUSBx
pio run --target erase           # optional, wipes any old firmware
pio run --target upload          # builds + flashes; ~5-10 min on first run
pio device monitor               # 115200 baud, Ctrl+C to quit
```

On the serial monitor you should see, within a second of reset:

```
[boot] esp32-link firmware booted
[wifi] AP started: ESP32-Console @ 192.168.4.1
[ws]   listening on port 81 path /ws
```

If those three lines appear, the firmware is healthy.

### 3. Join the ESP32's Wi-Fi

From the host's Wi-Fi settings, connect to:

| SSID | Password |
|------|----------|
| `ESP32-Console` | `esp32pass` |

The host gets `192.168.4.2` via DHCP. Windows will say "no internet" — that's
expected, the ESP32 isn't a router.

### 4. Run the desktop app

```bash
cd desktop
uv sync                          # one-off, ~2 min, downloads Qt
uv run esp32-link                # dark window opens via WSLg / X11
```

Click **Connect**. The status badge should go yellow (Connecting) for under a
second, then green (Connected), and the three plots begin filling at 2 Hz.

### 5. What to verify

- **Temperature plot** climbs slowly from room temperature toward ~30 °C as the
  chip warms up under Wi-Fi load.
- **Free heap plot** is a flat green line around 235 kB with brief dips to
  ~234.9 kB once or twice a minute (that's the AsyncWebSocket buffer cycle —
  see `docs/04-protocol.md`). Flat = no memory leak.
- **RSSI plot** sits around −40 to −50 dBm; moving the laptop closer or farther
  from the board should visibly shift it.
- Clicking **Toggle LED** in the GUI flips the blue LED on the board on/off,
  and the serial monitor logs `[cmd] toggle_led -> led on` (or `off`).
- Clicking **Ping** is silent in the GUI but the monitor shows
  `[cmd] ping -> pong`.

Above screenshot shows this state.

### 6. WSL2 networking gotcha

WSL2 default NAT routes 192.168.4.1 through the wrong adapter when ethernet is
also plugged in. If `ping 192.168.4.1` from inside WSL returns "Network is
unreachable" while the same command from Windows replies in 2 ms, add to
`%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
firewall=false

[experimental]
hostAddressLoopback=true
```

Then `wsl --shutdown` in PowerShell and reopen WSL. The Wi-Fi adapter should
appear in `ip addr` with the `192.168.4.x` address.

## Repository layout

```
esp32-link/
├── desktop/      # Python + PySide6 application (src layout)
│   ├── src/esp32_link/{domain,infrastructure,application,ui}
│   └── tests/
├── firmware/     # PlatformIO project (one main.cpp)
└── docs/         # docs + PlantUML diagrams + screenshots
```

## Documentation

The whole writeup lives under [`docs/`](docs/):

1. [Requirements](docs/01-requirements.md)
2. [Architecture](docs/02-architecture.md)
3. [Design patterns](docs/03-design.md) — the main grade-bearing piece
4. [Wire protocol](docs/04-protocol.md)
5. [Connection state machine](docs/05-state-machine.md)
6. [Testing](docs/06-testing.md)
7. [Build and run](docs/07-build-and-run.md)

UML diagrams are in [`docs/uml/`](docs/uml/) as `.puml` source. Render them
with [plantuml.com](https://www.plantuml.com/plantuml/uml/) or any
PlantUML-capable viewer. To build a single PDF from the markdown set, run
[`docs/build.sh`](docs/build.sh) (needs `pandoc` and a LaTeX engine).

## Known limitations / things I learned the hard way

- The first version of the firmware applied a Fahrenheit→Celsius conversion on
  `temperatureRead()` based on the Arduino-ESP32 major version. That was
  correct for older 2.x releases but wrong for 2.0.14+, which already returns
  Celsius. Symptom: chart showed −3 °C at room temperature. Fixed by dropping
  the conversion. On my board the sensor now reads ~24 °C in a 22–23 °C room.
  Per-chip variance is a couple of degrees either way; see
  [`docs/04-protocol.md`](docs/04-protocol.md) for the gory details.
- WSL2's mirrored networking mode doesn't always pick up the Wi-Fi adapter on
  the first try. If `ping 192.168.4.1` from inside WSL says "Network is
  unreachable" while it works from Windows directly, see step 6 of the runbook
  above.
- The reconnect logic loops forever at 8 s once backoff caps out. There is no
  "give up" button — you click Disconnect to stop it.

## License

[MIT](LICENSE). Use it, fork it, break it.
