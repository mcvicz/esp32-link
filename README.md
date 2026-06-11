# esp32-link

*Aplikacja okienkowa na system GNU/Linux do komunikacji z płytką ESP32*

Project for the AGH course on object-oriented design (prof. Cyganek). It's a Linux
desktop app written in Python with PySide6 that talks to an ESP32-WROOM-32 board
over Wi-Fi. The board runs a small AsyncWebSocket server in AP mode and pushes
telemetry (chip temperature, free heap, RSSI) at 2 Hz; the app draws three live
charts and lets you toggle the onboard LED or send a ping.

The point of the exercise is the design, not the gadget — the architecture and
the patterns used are documented in `docs/`. The actual hardware demo is just an
excuse to have something to design *around*.

## Hardware

- ESP32-WROOM-32 dev board (CP2102 USB-UART) — the one with the onboard blue LED on GPIO 2.
- USB-A cable (data, not charge-only).
- A laptop with a 2.4 GHz Wi-Fi adapter; the ESP32 only does 2.4 GHz.

## Stack

- Desktop: Python 3.12, PySide6 (Qt 6), pyqtgraph, `websockets`, `uv` for env management.
- Firmware: PlatformIO + Arduino-ESP32, ESPAsyncWebServer + AsyncTCP, ArduinoJson v7.
- Docs: Markdown + PlantUML, pandoc for the PDF build.
- CI: GitHub Actions (Python tests + firmware build).

## Quickstart

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
pio device monitor            # 115200 baud serial
```

On Windows where `pio` isn't on PATH, `python -m platformio ...` works the same.

The GUI defaults to `ws://192.168.4.1:81/ws`. Connect the host Wi-Fi to the
`ESP32-Console` SSID (password `esp32pass`) before clicking Connect.

## Repository layout

```
esp32-link/
├── desktop/      # Python + PySide6 application (src layout)
│   ├── src/esp32_link/{domain,infrastructure,application,ui}
│   └── tests/
├── firmware/     # PlatformIO project (one main.cpp)
└── docs/         # docs + PlantUML diagrams
```

## Documentation

The whole writeup lives under `docs/`:

1. [Requirements](docs/01-requirements.md)
2. [Architecture](docs/02-architecture.md)
3. [Design patterns](docs/03-design.md) — the main grade-bearing piece
4. [Wire protocol](docs/04-protocol.md)
5. [Connection state machine](docs/05-state-machine.md)
6. [Testing](docs/06-testing.md)
7. [Build and run](docs/07-build-and-run.md)

UML diagrams are in `docs/uml/` as `.puml` source. Render them with
[plantuml.com](https://www.plantuml.com/plantuml/uml/) or any PlantUML-capable
viewer. To build a single PDF from the markdown set, run `docs/build.sh`
(needs `pandoc` and a LaTeX engine).

## Known limitations / things I learned the hard way

- The first version of the firmware applied a Fahrenheit→Celsius conversion
  on `temperatureRead()` based on the Arduino-ESP32 major version. That was
  correct for older 2.x releases but wrong for 2.0.14+, which already returns
  Celsius. Symptom: chart showed −3 °C at room temperature. Fixed by dropping
  the conversion. On my board the sensor now reads ~24 °C in a 22–23 °C room.
  Per-chip variance is a couple of degrees either way. See
  `docs/04-protocol.md` for the gory details.
- WSL2's mirrored networking mode doesn't always pick up the Wi-Fi adapter on
  the first try. If `ping 192.168.4.1` from inside WSL says "Network is
  unreachable" while it works from Windows directly, the laptop is on the ESP
  AP but WSL only sees the ethernet adapter. Fix is in `.wslconfig` —
  documented in `docs/07-build-and-run.md`.
- The reconnect logic loops forever at 8 s once backoff caps out. There is no
  "give up" button; you click Disconnect to stop it.

## License

[MIT](LICENSE). Use it, fork it, break it.
