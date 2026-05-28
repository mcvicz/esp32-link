# esp32-link

*Aplikacja okienkowa do komunikacji z płytką ESP32*

A GNU/Linux desktop application that communicates with an ESP32-WROOM microcontroller over Wi-Fi using WebSockets. The ESP32 acts as a Wi-Fi access point; the desktop app connects to it, streams live telemetry (internal chip temperature, free heap memory, Wi-Fi RSSI) into a real-time chart at 2 Hz, and can send commands back to toggle the onboard LED.

## Repository layout

See [CLAUDE.md](CLAUDE.md) for the authoritative directory tree and architectural rules.

```
esp32-link/
├── desktop/      # Python + PySide6 desktop application
├── firmware/     # PlatformIO project for the ESP32
└── docs/         # Markdown documentation + PlantUML diagrams
```

## Quickstart

```bash
# Desktop — first time setup
cd desktop && uv sync

# Desktop — run
uv run esp32-link

# Desktop — tests
uv run pytest

# Desktop — lint and format
uv run ruff check
uv run ruff format

# Firmware — build
cd firmware && pio run

# Firmware — flash
pio run --target upload

# Docs — build PDF (optional)
cd docs && ./build.sh
```

## Documentation

- [01 — Requirements](docs/01-requirements.md)
- [02 — Architecture](docs/02-architecture.md)
- [03 — Design](docs/03-design.md)
- [04 — Protocol](docs/04-protocol.md)
- [05 — State machine](docs/05-state-machine.md)
- [06 — Testing](docs/06-testing.md)
- [07 — Build and run](docs/07-build-and-run.md)

## License

[MIT](LICENSE).
