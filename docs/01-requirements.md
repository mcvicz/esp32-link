# Requirements

## What the assignment asks for

The course brief (prof. Cyganek) is a single sentence:

> Aplikacja okienkowa na system GNU/Linux do komunikacji z płytką ESP32.

Translated and unpacked: a windowed application running on GNU/Linux that
communicates with an ESP32 microcontroller. Beyond that the grading focus is on
documentation, the architecture, and the design patterns used — the gadget
itself is mostly a vehicle for those.

## What I decided to build

A desktop client + firmware pair, connected over a single WebSocket:

- The ESP32-WROOM-32 runs as a Wi-Fi soft access point. It hosts a WebSocket
  server on `ws://192.168.4.1:81/ws`.
- The desktop application joins that AP, opens the WebSocket, and renders a
  live chart of telemetry data from the board.
- The user can send two commands back: toggle the onboard LED, and a no-op
  ping that round-trips through the protocol.

Wi-Fi was chosen over USB serial for one practical reason: USB device
passthrough into WSL2 is a separate adventure I did not want to take on for
this course. Networking just works.

## Target environment

| Component | Choice | Why |
|-----------|--------|-----|
| Operating system | GNU/Linux (Ubuntu under WSL2 + WSLg) | Required by the brief. WSL gives me a Linux dev environment on a Windows laptop without dual-booting. |
| GUI toolkit | Qt 6 via PySide6 | Cross-platform, modern, dark theme support, idiomatic signal/slot Observer pattern. |
| Language (desktop) | Python 3.12 | I'm comfortable in it; full type hints + dataclasses make the domain layer pleasant. |
| Dependency manager | `uv` | Fast and reproducible. Project-locked via `uv.lock`. |
| Microcontroller | ESP32-WROOM-32 | Classic ESP32, dual-core 240 MHz, 4 MB flash. The one I had in the drawer. |
| Firmware framework | Arduino-ESP32 under PlatformIO | Arduino's high-level API + PlatformIO's reproducible builds. |
| Wire protocol | Line-delimited JSON over WebSocket | Human-readable on the serial monitor, easy to debug with `curl`/Python scripts. |

## Functional requirements

The firmware must:

- Start a Wi-Fi soft access point on boot and log the bound IP over the serial
  console at 115200 baud.
- Accept WebSocket clients on `ws://192.168.4.1:81/ws`.
- Sample the chip temperature, free heap, and the RSSI of the first connected
  station every 500 ms and broadcast a `telemetry` frame to every connected
  client.
- Skip the broadcast when no clients are connected (no point burning JSON
  serialisation cycles into the void).
- Parse incoming `cmd` frames and dispatch by `action`: `toggle_led` flips
  GPIO 2, `ping` is a no-op. Unknown actions reply with an ack that has
  `ok: false`.
- Acknowledge every command with an `ack` frame echoing the original `cmd_id`.
- Drop malformed JSON and log it; never crash.

The desktop application must:

- Connect to a user-supplied WebSocket URL (pre-filled with the documented
  default).
- Render telemetry as a real-time chart with a 60-second rolling window. One
  plot per signal: temperature, free heap, RSSI.
- Offer buttons to toggle the LED and send a ping. Buttons disabled when not
  connected.
- Persist the last-used URL and the window geometry between runs.
- Automatically reconnect on connection loss using exponential backoff:
  1 s, 2 s, 4 s, 8 s, then 8 s indefinitely. User can cancel by clicking
  Disconnect.

## Non-functional requirements

- The code uses the six design patterns documented in
  [03-design.md](03-design.md) (Facade, Strategy, State, Command, Observer,
  Singleton). They appear in the code as described, not as decorations on a
  diagram.
- The application is split into four layers with one-way dependencies
  (UI → application → domain → infrastructure); the `domain` layer imports
  nothing from PySide6 or `websockets` and is therefore trivially unit-testable.
- All Python code has full type hints and passes `ruff check` + `ruff format`.
- Tests run under `pytest` (38 tests in five files). CI runs them on every
  push along with a firmware compile check.
- Wire protocol, network constants, and pattern usage are documented under
  `docs/` and the UML in `docs/uml/`.

## Out of scope

- Authentication and encryption. The AP uses WPA2 with a hardcoded passphrase
  and that's the extent of it. This is a course project, not a product.
- Multi-board orchestration. The protocol assumes one ESP32 client.
- Persistent storage of historical telemetry beyond the in-memory rolling
  window.
- Cross-platform GUI testing. Only Linux is targeted.
