# Design patterns

This is the main design writeup. Six patterns are used in the project, listed
below in roughly the order I picked them while building. Each gets a problem
description, the pattern itself, where it lives in the code, what I tried first
or considered as an alternative, and the trade-offs I noticed in practice.

Two notes up front:

- I'm aware that hitting six named patterns can feel like a checklist. Honestly,
  Singleton was the one I argued with myself about the most (see below). Facade,
  Strategy, State, Command, and Observer fell out of the problem naturally; I
  did not have to "find a place" for them.
- The patterns map cleanly onto the layered architecture in
  [02-architecture.md](02-architecture.md). Facade and Command sit in
  `application/`, State and the value objects in `domain/`, Strategy in
  `infrastructure/`, Observer is the Qt signal glue, and Singleton is the
  `Config` accessor.

---

## 1. Facade — `Esp32Client`

To talk to the board the application has to juggle four things: a WebSocket
transport, a JSON codec, a connection state machine, and a reconnection policy.
The GUI doesn't care about any of these individually — it wants to call
`connect()`, see telemetry arrive, send a command, and not deal with asyncio.

The Facade pattern fits exactly that: give the GUI one object with a small
interface that hides the rest of the subsystem.

`application/client.py::Esp32Client` is that object. Its public surface is:

```python
client.connect(url: str) -> None
client.disconnect() -> None
client.send(command: Command) -> None
client.state -> ConnectionState
```

…plus four Qt signals (`telemetry_received`, `ack_received`, `state_changed`,
`error_occurred`). Internally it owns the transport, runs the asyncio loop in a
background thread, drives the FSM through its lifecycle, and applies the
exponential backoff on reconnect.

**Alternatives I considered.** The first version of `MainWindow` actually held
the transport directly and called `await transport.connect(...)` inline. That
worked but mixed Qt event-loop code with asyncio code in the same file, and
every widget that needed to send a command was importing `websockets`. The
Facade gave me a single place to bridge asyncio to Qt (the worker thread plus
queued signal emissions) and a single point to add reconnection later.

I also looked at the Mediator pattern but rejected it — there is no widget-to-
widget coordination here, only widgets-to-connection. Facade is the right size.

**Trade-offs.** `Esp32Client` is genuinely a "god object" if you squint —
transport ownership, codec, FSM driver, retry loop, signal emitter, all in one
class (~200 lines). I think that's fine because all of those concerns are about
*the connection* and a single class is easier to reason about than five
collaborating ones for code at this scale. If the project grew, I'd extract the
retry policy first.

---

## 2. Strategy — `Transport`

The wire is WebSocket today. It might be a USB serial link tomorrow if I
finally talk WSL into doing USB passthrough properly. I did not want the rest of
the code to care.

Strategy: define an abstract interface for the algorithm (here, "a bidirectional
text transport"), implement one or more concrete strategies, let callers pick.

`infrastructure/transport.py::Transport` is the ABC:

```python
class Transport(ABC):
    @abstractmethod async def connect(self, url: str) -> None: ...
    @abstractmethod async def disconnect(self) -> None: ...
    @abstractmethod async def send(self, text: str) -> None: ...
    @abstractmethod def messages(self) -> AsyncIterator[str]: ...
```

`infrastructure/websocket_transport.py::WebSocketTransport` is the only concrete
strategy in production. `Esp32Client.__init__` takes an optional `transport`
parameter and defaults to a fresh `WebSocketTransport()`. The tests inject a
fake one when they want to drive the client without touching the network.

**Alternatives.** I could have imported `websockets` straight into
`Esp32Client`. It would be five lines shorter. But then the integration tests
would need a real WebSocket server on a real port (which is what the
`fake_ws_server` fixture is — but at least it sits behind the same interface as
production), and a future serial backend would require ripping things up.

**Trade-offs.** One extra layer of indirection that today has exactly one
concrete implementation, so by YAGNI you could argue it's premature. I keep it
because the abstraction is small (four methods), the win on testability is
already real, and a serial backend is not hypothetical — it's the obvious next
step if I keep working on this.

---

## 3. State — `ConnectionStateMachine`

The connection lifecycle has five distinct phases (Disconnected, Connecting,
Connected, Reconnecting, Error). Different code in different layers asks "are
we connected?" or "should we try again?" and earlier versions of this question
were two boolean flags. That gave me four possible flag combinations for five
real states, with most combinations meaningless and at least one bug where the
GUI thought we were both reconnecting and disconnected at the same time.

State pattern, in the lightweight sense: an enum for the states, a transition
table for what's allowed, and one method on the FSM that validates a requested
transition. The full diagram is in `uml/state_connection.puml` and the
companion writeup is [05-state-machine.md](05-state-machine.md).

The FSM lives in `domain/` and has no Qt or async dependencies. That keeps the
tests fast and makes the transition rules easy to read in one file. The
reconnection *policy* (which transitions fire and when) is in `Esp32Client`
because that's the layer that actually owns the timer.

**Alternatives.** Boolean flags were the original sin. The classic GoF rendering
with one class per state (and dispatched methods per state) is overkill here —
my states have no per-state behaviour beyond "is this transition allowed". A
table-driven FSM is the right weight.

**Trade-offs.** A static transition table can't express "auto-progress after N
seconds" — but I don't want it to. The FSM models legality, not policy.

---

## 4. Command — `ToggleLedCommand`, `PingCommand`

When the user clicks the LED button, we need to send a JSON message that names
an action and carries a UUID for the matching ack. Two buttons, two payloads.

I went back and forth on whether this was worth a hierarchy. With two commands,
a pair of `if action == "toggle_led": ...` branches on a string would have done
the job. I chose the hierarchy mostly so that adding a third command (or a
command with arguments, like `SetIntervalCommand(ms=250)`) doesn't require
changing the signature of `Esp32Client.send()`.

`application/commands.py` has an abstract `Command` dataclass:

```python
@dataclass(frozen=True)
class Command(ABC):
    cmd_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @abstractmethod
    def action(self) -> str: ...

    def serialize(self) -> dict[str, Any]:
        return {"type": "cmd", "cmd_id": self.cmd_id, "action": self.action()}
```

`ToggleLedCommand` and `PingCommand` each just override `action()`. The UUID
default factory means the UI never has to think about correlation ids.

**Trade-offs.** I could equally have used a string enum (`Action.TOGGLE_LED`)
and a single `send(action: Action)` method, which would be smaller. The
hierarchy pays off the first time I add a command that needs arguments — until
then it is on the heavy side.

---

## 5. Observer — Qt signals on `Esp32Client`

Telemetry arrives whenever the ESP feels like it (every 500 ms, but unpredictable
in jitter). State changes happen on connect, drop, retry, etc. Three widgets
need to react: the chart, the control panel, the status bar. None of them
should be coupled to one another and `Esp32Client` shouldn't even know they
exist.

Qt's signals and slots are an Observer implementation hiding in a different
costume. The subject (`Esp32Client`) declares typed signals. Each observer
widget connects a slot to the signal it cares about. The dispatch is
thread-safe by default — emissions from the asyncio worker thread land on the
GUI thread via Qt's queued connection.

The wiring is centralised in `MainWindow.__init__`:

```python
self._client.telemetry_received.connect(self._chart.append_sample)
self._client.state_changed.connect(self._control_panel.on_state_changed)
self._client.state_changed.connect(self._status_bar.on_state_changed)
self._client.error_occurred.connect(self._status_bar.on_error)
```

Adding a new observer is one line.

**Trade-offs.** Qt signal/slot type-checking is runtime only — if I declare a
slot with the wrong signature the binding silently does nothing at emission time
or PySide6 logs a warning. Mitigated by the widget tests in
`tests/test_ui.py` that emit each signal and assert the slot ran.

---

## 6. Singleton — `Config.instance()`

This is the one I argued with myself about. The application has two persisted
settings: the last URL entered into the URL field and the window geometry. They
load from `~/.config/esp32-link/config.json` on startup and save in
`MainWindow.closeEvent`.

The textbook objection to Singleton is that it's global state in disguise, and
global state hurts testability. The reason I kept it anyway:

- The "load once from disk" lifecycle is real, not pretend. A second instance
  wouldn't be a logically different config, just a stale copy of the same one.
- The widget that triggers a save (`MainWindow` on close) and the widget that
  reads it on construction (also `MainWindow`) are far apart in time and don't
  share a constructor — passing a `Config` instance through dependency injection
  would have meant threading it through `app.py → MainWindow.__init__ → ...`.
  Worth it if there were several pieces of state to manage; not worth it for
  two strings.

`config.py::Config` is a dataclass with a classmethod:

```python
@classmethod
def instance(cls) -> Self:
    if cls._instance is None:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls._load()
    return cls._instance
```

The double-checked locking is mostly habit — the GUI is single-threaded for
config access, so it doesn't strictly matter, but the explicit lock made me
feel better about it during the asyncio-thread bridging work.

A `Config.reset()` classmethod exists purely as a test hook to clear the cached
instance. Tests that monkeypatch `CONFIG_PATH` to a tmpdir call this so they
don't see each other's state.

**Alternatives.** `QSettings` would do the same job and is what an actual Qt
person would use — it handles per-platform paths cleanly. I went with a plain
JSON file because the rest of the persistence layer didn't already depend on
Qt and I didn't want it to.

**Trade-offs.** Global state is global state. For a two-field config used at
startup and shutdown, the convenience of `Config.instance().last_url` was worth
the slight smell. If `Config` grew a dozen settings I'd reconsider.

---

## Incidental patterns

A few other patterns are used without being documented as featured ones:

- **Value Object** — `Telemetry` and `Ack` are immutable frozen dataclasses
  with `slots=True` and structural equality. Idiomatic Python; not really a
  "pattern decision" so much as the natural representation for inbound message
  data.
- **Template Method** — `Command.serialize()` is the common skeleton, subclasses
  fill in `action()`. Same shape as the GoF pattern but applied at the smallest
  possible scope.

These are useful idioms but I didn't make them part of the headline six because
they don't structure the architecture the way the six above do.
