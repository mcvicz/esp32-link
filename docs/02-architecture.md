# Architecture

## High-level view

The system has two halves connected by a single WebSocket:

```
+--------------------+        ws://192.168.4.1:81/ws        +-----------------+
|   Desktop (Linux)  |  <----------------------------->     |  ESP32-WROOM    |
|   PySide6 GUI      |        line-delimited JSON           |  Arduino + ESP- |
|                    |                                      |  AsyncWebServer |
+--------------------+                                      +-----------------+
```

The ESP32 acts as a Wi-Fi access point and a WebSocket server. The desktop joins the AP and connects as a client.

## Desktop layering

The desktop application is split into four layers. Dependencies flow downward only.

```
+-----------------------------------------------------------+
|  ui/                                                      |   PySide6 widgets,
|    main_window, chart_widget, control_panel, status_bar   |   Qt signal/slot
+-----------------------------------------------------------+
                            v
+-----------------------------------------------------------+
|  application/                                             |   Esp32Client (Facade),
|    client.py, commands.py                                 |   Command objects
+-----------------------------------------------------------+
                            v
+-----------------------------------------------------------+
|  domain/                                                  |   Pure logic.
|    messages.py, state.py                                  |   No Qt. No websockets.
+-----------------------------------------------------------+
                            v
+-----------------------------------------------------------+
|  infrastructure/                                          |   Transport (Strategy),
|    transport.py, websocket_transport.py, codec.py         |   WebSocket I/O, JSON
+-----------------------------------------------------------+
```

### Layer responsibilities

**`ui/`**: visual widgets and user input. Knows about `application.Esp32Client`
and `domain.ConnectionState`. Never imports `infrastructure` directly. Builds
`Command` objects and hands them to the client.

**`application/`**: orchestrates the use cases. Owns the `Esp32Client` facade
that wraps the transport, codec, FSM, and reconnection policy. Owns the
`Command` hierarchy that captures user intent.

**`domain/`**: framework-free data model. `Telemetry` and `Ack` dataclasses,
the `ConnectionState` enum, and the `ConnectionStateMachine`. Imports nothing
from Qt or the `websockets` library, which is what makes it easy to unit-test
without spinning up a GUI or a network.

**`infrastructure/`**: adapters to the outside world. The `Transport` abstract
base class (Strategy), the concrete `WebSocketTransport`, and the JSON `codec`.
Hides all I/O and serialization details from the upper layers.

### Why the split is enforced

A few concrete payoffs I noticed while writing the code:

- The `domain` layer's tests run in milliseconds. No event loop, no port to
  bind, no Qt application to instantiate.
- The `Transport` abstraction means a future `SerialTransport` slots in without
  touching `domain`, `ui`, or `application`. I have not actually written one,
  but the abstract base class is shaped to allow it.
- The UI does not know that telemetry comes over a WebSocket or that messages
  are JSON. It connects slots to Qt signals and that's it. If we swapped to
  Protobuf over a serial port tomorrow, `ui/` would not change.

## Firmware structure

`firmware/src/main.cpp` is a single file but is organized into logical units so it can be documented as components (see `class_firmware.puml`):

| Component | Role |
|-----------|------|
| `cfg` namespace | Network constants (SSID, password, port, path, interval, LED pin). |
| `Telemetry` struct | Samples chip temperature, free heap, RSSI of the first connected station. |
| `Protocol` namespace | Encodes telemetry and ack frames using ArduinoJson v7. |
| `CommandDispatcher` | Parses inbound JSON, dispatches by `action`, emits ack frames. |
| `WsServer` class | Wraps `AsyncWebServer` and `AsyncWebSocket`; exposes `begin`, `broadcast`, and a message callback. |
| `setup` / `loop` | Wi-Fi AP startup; non-blocking 500 ms telemetry tick driven by `millis()`. |

This organization mirrors the desktop layering: `Telemetry` and the protocol live in their own logical "domain", the dispatcher is "application", and `WsServer` is "infrastructure".

## Cross-layer threading model

`Esp32Client` runs the asyncio loop and `websockets` client inside a background `threading.Thread` so that the GUI's Qt event loop never blocks on I/O. Qt signals emitted from that worker thread cross to the GUI thread via Qt's default `Qt::QueuedConnection`, which is thread-safe.

The user-facing API is synchronous: the UI calls `client.connect(url)`, `client.disconnect()`, and `client.send(command)` from the GUI thread; internal scheduling onto the asyncio loop uses `asyncio.run_coroutine_threadsafe` and `loop.call_soon_threadsafe`.
