# Build and run

## Prerequisites

| Tool | Where | Why |
|------|-------|-----|
| `uv` | host (Linux / WSL) | Python environment + dependency management |
| Python 3.12 | host | Runtime for the desktop application |
| PlatformIO | Windows or Linux with USB access to the board | Build and flash the firmware |
| ESP32-WROOM-32 dev board | hardware | The microcontroller target |
| A 2.4 GHz Wi-Fi-capable laptop | hardware | To join the ESP32 access point |

The desktop application was developed on Windows 11 with WSL2 + WSLg rendering. Native Linux works the same way.

## First-time setup

```bash
# clone
git clone <repo-url> esp32-link
cd esp32-link

# desktop dependencies
cd desktop
uv sync
cd ..

# firmware toolchain (downloads ~500 MB on first build)
cd firmware
pio run         # or: python -m platformio run
cd ..
```

On Windows where `pio` may not be on `PATH`, use `python -m platformio` instead — every PlatformIO command supports this form.

## Build firmware

```bash
cd firmware
pio run
```

This produces `firmware/.pio/build/esp32dev/firmware.bin` and reports flash and RAM usage.

## Flash firmware

Plug the ESP32 into a USB port that supports data.

```bash
cd firmware
pio device list                 # confirm the COM/tty port appears
pio run --target erase          # optional, wipes any existing firmware
pio run --target upload         # build (if needed) and flash
pio device monitor              # 115200 baud serial console
```

Expected boot output:

```
[boot] esp32-link firmware booted
[wifi] AP started: ESP32-Console @ 192.168.4.1
[ws]   listening on port 81 path /ws
```

Press the **EN** (reset) button on the board to force a reboot if the serial monitor was attached after boot.

Quit the monitor with `Ctrl+C`.

## Join the ESP32 access point

Connect the host machine's Wi-Fi to the network:

| SSID | Password |
|------|----------|
| `ESP32-Console` | `esp32pass` |

Windows will warn that this network has no internet — that's expected. The desktop application talks only to `192.168.4.1` on this network.

### WSL2 networking note

If you run the desktop application from WSL2, ensure WSL is in **mirrored networking mode** so it can see the Wi-Fi adapter. Add the following to `%USERPROFILE%\.wslconfig` on Windows:

```ini
[wsl2]
networkingMode=mirrored
firewall=false

[experimental]
hostAddressLoopback=true
```

Then `wsl --shutdown` in PowerShell. After WSL restarts, `ip addr` inside WSL should list an interface with the `192.168.4.x` address assigned by the ESP32's DHCP, and `ping 192.168.4.1` should reply.

## Run the desktop application

```bash
cd desktop
uv run esp32-link
```

The window opens with three empty plots, a URL field pre-filled with `ws://192.168.4.1:81/ws`, and Connect / Toggle LED / Ping buttons.

Click **Connect**. The status badge transitions Connecting (yellow) → Connected (green) and the three plots start filling at 2 Hz with temperature, free heap, and RSSI. Toggle LED flips the onboard blue LED; Ping is a no-op round-trip.

Closing the window persists the last URL and window geometry to `~/.config/esp32-link/config.json`.

### Logging

Default log level is INFO and goes to stdout. For verbose logs (raw JSON in/out, FSM transition debug):

```bash
ESP32_LINK_DEBUG=1 uv run esp32-link
```

## Run the tests

```bash
cd desktop
uv run pytest               # full suite
uv run ruff check           # lint
uv run ruff format --check  # formatting
```

See `06-testing.md` for what each test file covers.

## Build the documentation PDF (optional)

A `pandoc`-based one-liner is provided in `docs/build.sh`:

```bash
cd docs
./build.sh
```

This requires `pandoc` and a LaTeX engine (typically `texlive-xetex`) installed on the host. The output is `docs/esp32-link.pdf`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `pip install --user platformio` fails with "externally-managed-environment" | Ubuntu 24.04+ blocks system-site pip installs (PEP 668) | `sudo apt install pipx` then `pipx install platformio`. Or install PIO on Windows side (recommended — see next row). |
| `pio device list` returns nothing inside WSL while Windows sees the COM port | WSL2 doesn't expose USB devices by default | Run firmware commands from **Windows PowerShell** instead. The README runbook is explicit about which terminal to use at each step. If you really need PIO in WSL, set up `usbipd-win`. |
| `pio` command not found | PIO installed but its Scripts directory is not on PATH | Use `python -m platformio` instead, or add the Scripts dir to PATH. |
| Upload fails with "no upload port" / "Please specify upload_port" | USB cable is charge-only, the board's USB-UART driver is missing, or you're in WSL (see USB row above) | Use a known-good USB-data cable; install the Silicon Labs CP210x driver (or CH340 depending on the board variant); flash from Windows PowerShell. |
| Wi-Fi `ESP32-Console` not visible from any device | The board didn't boot, or the laptop's Wi-Fi adapter doesn't pick up 2.4 GHz at low signal | Reset the board (EN button); move within ~1 m of the board; verify the three boot lines in the serial monitor. |
| Wi-Fi `ESP32-Console` visible but Windows says "connected, no internet" and GUI still can't reach it | Mostly expected — the ESP32 isn't a router. If the GUI is failing, it's a routing problem, not a Wi-Fi problem. | Check the next row. |
| GUI shows "connect failed: timed out during opening handshake" | Laptop is not on the `ESP32-Console` network, or WSL is not in mirrored networking mode and can't reach the Wi-Fi adapter | Connect Windows Wi-Fi to the ESP AP; from WSL run `ping 192.168.4.1` — if it says "Network is unreachable" while the same ping works from Windows, fix `.wslconfig` per § "WSL2 networking note" above. |
| Tests fail with `libEGL.so.1: cannot open shared object file` | Qt runtime libraries missing | Already handled in CI; locally on Ubuntu install `libegl1 libgl1 libxkbcommon-x11-0 libdbus-1-3 libfontconfig1 libxcb-cursor0`. |
| Temperature plot shows nonsense negative values like −3 °C | An older revision of this firmware had a Fahrenheit-to-Celsius conversion that's wrong for Arduino-ESP32 ≥ 2.0.14 | Pull latest `master` (commit `5871e9f` and later) and reflash. |
