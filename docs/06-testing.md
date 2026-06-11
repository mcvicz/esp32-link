# Testing

## Layers and what they cover

The test suite is in `desktop/tests/` and is divided into four layers, matching the application layout.

| File | Layer | What it covers |
|------|-------|----------------|
| `test_codec.py` | infrastructure | JSON encode/decode round-trips; malformed JSON, unknown types, missing fields, empty lines, non-object payloads — all return `None` and log. |
| `test_state_machine.py` | domain | The FSM transition table: legal and illegal transitions, the happy path, error recovery, and the rule that `CONNECTED → CONNECTING` is illegal (must go via `RECONNECTING`). |
| `test_commands.py` | application | Each `Command` subclass serialises to the documented JSON shape; `cmd_id` is unique per instance unless explicitly set; payloads are JSON-safe. |
| `test_client_integration.py` | application + infrastructure | `Esp32Client` against the `fake_ws_server` fixture: receiving telemetry frames, receiving acks, sending commands, state changes, and clean shutdown. |
| `test_ui.py` | ui | Widget construction; control-panel signal emission; button enable/disable logic across states; chart sample append/clear; status-bar updates; window construction. |
| `conftest.py` | fixtures | `fake_ws_server` fixture; forces Qt's `offscreen` platform plugin for headless runs. |

## The `fake_ws_server` fixture

`conftest.py::fake_ws_server` is a real WebSocket server run by the `websockets` library on `127.0.0.1` on a free random port, inside a background `threading.Thread` so synchronous pytest tests (including pytest-qt tests) can drive it. Tests can:

- Install an `on_connect_handler` to push canned frames at handshake time.
- Read `received_from_clients` to assert what the client sent.

This lets us cover the full Esp32Client → codec → transport stack against a real WebSocket without depending on the actual ESP32 hardware.

## Headless Qt

`conftest.py` sets `QT_QPA_PLATFORM=offscreen` before pytest-qt initialises so the suite runs in CI without a display. Locally on WSLg the env var doesn't break anything because Qt simply doesn't render visible windows; `pytest-qt` still wires up signals correctly.

## Running the suite

```bash
cd desktop
uv sync                    # one-off, installs dev dependencies
uv run pytest              # full suite
uv run pytest -x           # stop at first failure
uv run pytest tests/test_codec.py        # one file
uv run pytest -k "state"   # by keyword
```

Expected count: **38 tests, all passing** (10 codec + 7 state machine + 5 commands + 5 client integration + 11 UI = 38).

## Linting and formatting

`ruff` is the linter and formatter, configured in `pyproject.toml`:

- `line-length = 100`
- `target-version = py312`
- `select = ["E", "F", "I", "UP", "B"]`

```bash
uv run ruff check          # lint
uv run ruff format         # auto-format
uv run ruff format --check # verify formatting without modifying
```

The CI pipeline runs `uv run pytest`; lint and format checks should be run locally before pushing.

## Continuous integration

`.github/workflows/ci.yml` defines two jobs:

| Job | Runs |
|-----|------|
| `python-tests` | Installs Qt runtime libraries (`libegl1`, `libgl1`, `libxkbcommon-x11-0`, `libdbus-1-3`, `libfontconfig1`, `libxcb-cursor0`), installs `uv`, runs `uv sync` and `uv run pytest` with `QT_QPA_PLATFORM=offscreen`. |
| `firmware-build` | Sets up Python 3.12, installs PlatformIO, runs `pio run` in `firmware/` to verify the firmware compiles cleanly against the pinned framework version. |

Both jobs run on `ubuntu-latest` on every push and every pull request.

## What is not tested automatically

- The GUI is not driven end-to-end in CI. We have widget smoke tests, but full user-flow tests (click Connect → see chart fill) require a live ESP32 and are performed manually as part of a release check.
- Firmware behaviour is not run on real hardware in CI. CI only verifies that the C++ compiles; functional verification is done manually with the desktop client against the board.
- The internal temperature sensor reading is not asserted against a reference (sensor is uncalibrated; see `04-protocol.md`).
