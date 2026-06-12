# Connection state machine

The desktop client tracks a single connection through a five-state FSM defined
in `domain/state.py`. The FSM owns the current state and checks every
transition against a table; `Esp32Client` calls `transition_to(...)` at
well-defined points in its `_main()` reconnection loop.

The full diagram is `uml/state_connection.puml`. The companion design notes are
in [03-design.md § State](03-design.md#3-state--connectionstatemachine).

## States

| State | Meaning |
|-------|---------|
| `DISCONNECTED` | Idle. No background thread is running. This is the initial state and the state we land in after a clean `disconnect()`. |
| `CONNECTING` | First connection attempt in a new session. The transport's `connect(url)` coroutine is in flight. |
| `CONNECTED` | TCP+WebSocket handshake completed; the receive loop is consuming frames. |
| `RECONNECTING` | A previously established connection dropped (or a retry attempt is in flight). The backoff timer or the next `connect()` call is running. |
| `ERROR` | The most recent attempt failed. A brief transient state immediately followed by `RECONNECTING` (the loop keeps retrying indefinitely per the backoff schedule). The user-facing message displayed in the status bar comes from `error_occurred`. |

## Transition table

```
DISCONNECTED   → { CONNECTING }
CONNECTING     → { CONNECTED, ERROR, DISCONNECTED }
CONNECTED      → { DISCONNECTED, RECONNECTING, ERROR }
RECONNECTING   → { CONNECTED, ERROR, DISCONNECTED }
ERROR          → { DISCONNECTED, CONNECTING, RECONNECTING }
```

`ConnectionStateMachine.transition_to(target)` raises `IllegalTransitionError` if `target` is not in the legal successors of the current state. `Esp32Client._set_state(target)` calls `can_transition_to` first and silently drops illegal requests (logging at DEBUG) so the client's loop is forgiving of duplicate emissions.

## Where transitions originate

| Trigger | Transition | Code location |
|---------|------------|---------------|
| User clicks **Connect** | `DISCONNECTED → CONNECTING` | `Esp32Client._main` (first iteration) |
| Handshake succeeds | `CONNECTING → CONNECTED` or `RECONNECTING → CONNECTED` | `Esp32Client._main` after `transport.connect()` returns |
| Handshake fails | `CONNECTING → ERROR` or `RECONNECTING → ERROR` | `Esp32Client._main` exception handler |
| Receive loop ends (peer closed) | `CONNECTED → RECONNECTING` | `Esp32Client._main` after `_run_receive_until_stop_or_close` |
| Next retry begins | `ERROR → RECONNECTING` | `Esp32Client._main` next iteration |
| User clicks **Disconnect** | any → `DISCONNECTED` | `Esp32Client._main` finally block |

The user-visible "Connect/Disconnect" button label is derived from the state in `ControlPanel.on_state_changed`. While the client is in `CONNECTING` or `RECONNECTING`, the button reads **Disconnect** so the user can cancel an in-flight retry. The two command buttons (Toggle LED, Ping) are only enabled in `CONNECTED`.

## Backoff schedule

`RECONNECT_BACKOFF_SEC = (1.0, 2.0, 4.0, 8.0)` in `application/client.py`. The `_backoff(attempt)` helper clamps the attempt index to the last entry, so retries after the fourth use 8-second waits indefinitely. The waiting itself is done with `asyncio.wait_for(stop_event.wait(), timeout=delay)` so that a user-issued disconnect interrupts the sleep cleanly.

## Why the FSM lives in `domain/`

`ConnectionStateMachine` has no dependency on Qt, asyncio, or `websockets`,
which is the whole reason it sits in `domain/`. The transition tests
(`tests/test_state_machine.py`) run in milliseconds — no event loop, no sockets,
no widgets to instantiate. The reconnection *policy* (when each transition
fires) lives in `Esp32Client` because that layer is the one that actually owns
the timer; the *rules* about which transitions are legal stay framework-free.

## Notes on what bit me

I shipped the FSM first with `ERROR` having only two outgoing transitions
(`{DISCONNECTED, CONNECTING}`), which seemed cleaner — Error is "user must
acknowledge before retrying". When I ran the GUI against an unreachable host I
realised the auto-retry loop was hitting `ERROR → RECONNECTING` and getting
silently dropped, so the status bar stayed red while the client was actually
retrying behind the scenes. Adding `RECONNECTING` to the outgoing set fixed it.
The single-commit change is `domain: allow ERROR -> RECONNECTING transition
during auto-retry`.

Lesson for me: when the GUI seems "stuck" in a state, the FSM transition log at
DEBUG level (`logger.debug("skipping illegal transition ...")`) is the first
thing to check.
