# Wire protocol

## Transport

A single WebSocket connection between the desktop client and the ESP32 server.

| Property | Value |
|----------|-------|
| URL | `ws://192.168.4.1:81/ws` |
| Subprotocol | none |
| Framing | text frames; one JSON object per frame; each payload terminates with `\n` |
| Encoding | UTF-8 |

A single TCP connection carries both directions: the ESP32 pushes telemetry at 2 Hz and answers commands; the desktop pushes commands.

## Network constants

These are hardcoded on both sides. Changing one requires changing the other.

| Constant | Value |
|----------|-------|
| Wi-Fi SSID | `ESP32-Console` |
| Wi-Fi password (WPA2) | `esp32pass` |
| ESP32 IP (soft AP, default) | `192.168.4.1` |
| WebSocket port | `81` |
| WebSocket path | `/ws` |
| Telemetry rate | 2 Hz (500 ms interval) |
| Reconnect backoff | 1 s, 2 s, 4 s, 8 s, 8 s, … |

## Message types

There are three message types in two directions.

### `telemetry` — ESP32 → desktop

Pushed by the firmware every 500 ms.

```json
{"type":"telemetry","ts":12345,"temp_c":47.2,"free_heap":218456,"rssi":-52}
```

| Field | Type | Notes |
|-------|------|-------|
| `type` | string | constant `"telemetry"` |
| `ts` | uint32 | milliseconds since ESP32 boot (`millis()`) |
| `temp_c` | float (one decimal) | internal chip temperature in Celsius |
| `free_heap` | uint32 | free heap in bytes (`ESP.getFreeHeap()`) |
| `rssi` | int | RSSI of the first connected station in dBm (typical −30 … −90); `0` if no station |

The firmware skips telemetry broadcasts when no clients are connected, so the desktop never sees frames it didn't ask for.

#### Sensor accuracy note

The ESP32's internal temperature sensor on the classic ESP32 family is roughly
within ±1–2 °C of ambient on a given chip and drifts slowly with self-heating.
Earlier versions of this firmware applied a Fahrenheit-to-Celsius conversion
based on `ESP_ARDUINO_VERSION_MAJOR`, but Arduino-ESP32 2.0.14 and newer return
Celsius directly on the classic ESP32 — the extra conversion produced nonsense
negative values until that was fixed.

On my test board the sensor reads about 24 °C at idle in a 22–23 °C room, which
is fine for the demo. Per-chip variance can shift the absolute value a few
degrees in either direction without a calibration step; the *trend* (warming up
under load, cooling when idle) is always reliable. If you need ±0.5 °C absolute
accuracy, add an external sensor (DS18B20, BMP280, etc.) — that's a hardware
change, not a firmware tweak.

### `ack` — ESP32 → desktop

Sent in response to every successfully parsed `cmd` frame.

```json
{"type":"ack","cmd_id":"550e8400-e29b-41d4-a716-446655440000","ok":true,"msg":"led on"}
```

| Field | Type | Notes |
|-------|------|-------|
| `type` | string | constant `"ack"` |
| `cmd_id` | string | echoes the `cmd_id` from the originating command |
| `ok` | bool | `true` if the action succeeded |
| `msg` | string | human-readable status (`"led on"`, `"led off"`, `"pong"`, or an error description) |

### `cmd` — desktop → ESP32

```json
{"type":"cmd","cmd_id":"550e8400-e29b-41d4-a716-446655440000","action":"toggle_led"}
```

| Field | Type | Notes |
|-------|------|-------|
| `type` | string | constant `"cmd"` |
| `cmd_id` | string | client-generated UUID v4; echoed back in the matching `ack` |
| `action` | string | one of the defined actions |

## Defined actions

| Action | Effect | Ack on success |
|--------|--------|----------------|
| `toggle_led` | Flip GPIO 2 (onboard LED). | `{"ok":true,"msg":"led on"}` or `{"ok":true,"msg":"led off"}` |
| `ping` | No side effect. | `{"ok":true,"msg":"pong"}` |

An unknown `action` value is acked with `{"ok": false, "msg": "unknown action: <name>"}`. The firmware does not crash and does not close the connection.

## Robustness rules

The protocol is intentionally permissive:

- **Malformed JSON** on either side is logged at WARNING level and dropped. The peer is not notified.
- **Unknown `type`** values are logged and dropped.
- **Missing required fields** (e.g. a `telemetry` without `ts`) are logged and dropped; partial structures are not reconstructed.
- **Unknown extra fields** are ignored by both encoder and decoder. New fields can be added without breaking older peers.

These rules are enforced in `infrastructure/codec.py::decode` on the desktop side and in `CommandDispatcher::dispatch` on the firmware side.

## Backwards compatibility

Adding a new optional field to `telemetry` is non-breaking. Adding a new `action` value is non-breaking. Renaming or changing the meaning of an existing field is breaking and requires updating both this document and both implementations in the same change.
