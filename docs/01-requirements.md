# Requirements

## Course context

This project is the deliverable for the AGH course requirement *"Aplikacja okienkowa na system GNU/Linux do komunikacji z płytką ESP32"* — a windowed GNU/Linux desktop application that communicates with an ESP32 microcontroller.

## Scope

`esp32-link` is a desktop application that:

- Connects to an ESP32-WROOM-32 board over Wi-Fi using a WebSocket transport.
- Receives live telemetry from the board and renders it in a real-time chart.
- Lets the user send commands back to the board (toggle the onboard LED, ping).

The ESP32 acts as a Wi-Fi soft access point. The desktop computer joins that access point as a station and opens a single WebSocket connection.

## Target environment

| Component | Choice |
|----------|--------|
| Operating system | GNU/Linux (developed on Ubuntu under WSL2 with WSLg) |
| GUI toolkit | Qt 6 via PySide6 |
| Language (desktop) | Python 3.12 |
| Dependency manager | `uv` |
| Microcontroller | ESP32-WROOM-32 (classic ESP32, dual-core 240 MHz, 4 MB flash) |
| Firmware framework | Arduino-ESP32 under PlatformIO |
| Wire protocol | Line-delimited JSON over WebSocket |

## Functional requirements

| ID | Requirement |
|----|-------------|
| F1 | Firmware starts a Wi-Fi soft access point on boot. |
| F2 | Firmware accepts WebSocket clients on `ws://192.168.4.1:81/ws`. |
| F3 | Firmware broadcasts a telemetry frame every 500 ms to all connected clients. |
| F4 | Telemetry contains: timestamp (ms since boot), chip temperature (°C), free heap (bytes), and RSSI of the first connected station (dBm). |
| F5 | Firmware responds to `toggle_led` commands by flipping the onboard LED. |
| F6 | Firmware responds to `ping` commands with a `pong` acknowledgment. |
| F7 | Firmware acknowledges every command with an ack frame echoing the command id. |
| F8 | Desktop application connects to a user-supplied WebSocket URL. |
| F9 | Desktop application renders telemetry as a real-time chart with a 60-second rolling window. |
| F10 | Desktop application offers buttons to toggle the LED and send a ping. |
| F11 | Desktop application persists the last-used URL and window geometry between runs. |
| F12 | Desktop application automatically reconnects on connection loss using exponential backoff. |

## Non-functional requirements

| ID | Requirement |
|----|-------------|
| N1 | The code matches the documented six design patterns: Facade, Strategy, State, Command, Observer, Singleton. |
| N2 | The four-layer architecture (UI → application → domain → infrastructure) is enforced; the `domain` layer imports nothing from PySide6 or `websockets`. |
| N3 | All Python code is fully type-hinted and passes `ruff check` and `ruff format`. |
| N4 | A unit and integration test suite is provided and runs under `pytest` in continuous integration. |
| N5 | The project builds in CI: `pio run` for firmware, `uv run pytest` for the desktop app. |
| N6 | Wire-protocol message types, network constants, and pattern usage are documented in this `docs/` directory and rendered as PlantUML diagrams. |

## Out of scope

- Authentication and encryption (the AP is unsecured beyond the WPA2 passphrase).
- Multi-board orchestration; the protocol assumes one ESP32.
- Persistent storage of historical telemetry beyond the in-memory rolling window.
- Cross-platform GUI testing; only Linux is targeted.
