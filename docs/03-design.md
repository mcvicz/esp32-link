# Design patterns

Six design patterns are used. Each section follows the same structure: **Problem → Pattern → Application → Alternatives considered → Trade-offs**.

---

## 1. Facade — `Esp32Client`

**Problem.** The desktop application has to coordinate four moving parts to talk to the ESP32: a transport (WebSocket), a codec (JSON), a state machine (connection state), and a reconnection policy (exponential backoff). Without a deliberate seam, every UI widget that wants telemetry or sends a command would need to know about all four. That couples Qt widgets to asyncio, to `websockets`, and to JSON shapes.

**Pattern.** *Facade* (GoF structural pattern). Provide a unified, small interface in front of a larger subsystem so client code talks to one object instead of many.

**Application.** `application/client.py::Esp32Client` exposes a tiny API:

```python
client.connect(url: str) -> None
client.disconnect() -> None
client.send(command: Command) -> None
client.state -> ConnectionState
```

…plus four Qt signals: `telemetry_received`, `ack_received`, `state_changed`, `error_occurred`.

Internally `Esp32Client` owns:
- a `Transport` (Strategy) for the wire,
- the `codec.encode`/`codec.decode` helpers,
- a `ConnectionStateMachine` (State),
- a background thread driving an asyncio event loop,
- the reconnection backoff schedule.

The UI never imports `websockets`, never imports `asyncio`, never builds a JSON string.

**Alternatives considered.**
- *No facade*: every widget would import the transport, codec, and FSM directly. Tight coupling; refactoring any of the four would touch UI code.
- *A separate Mediator object* that brokered messages between widgets and infrastructure. Heavier; we don't need bidirectional widget-to-widget coordination.
- *Service locator / dependency injection container.* Overkill for a single application object.

**Trade-offs.**
- The Facade is a single class with multiple responsibilities; it's bigger than a leaf component. We accept that because everything it coordinates is genuinely one cohesive concern: "the connection to the board".
- Hiding asyncio means we have to bridge to Qt explicitly (background thread + queued signal emissions). That bridge is encapsulated *inside* the Facade — exactly what the pattern is for.

---

## 2. Strategy — `Transport`

**Problem.** The connection between desktop and ESP32 currently uses WebSocket over Wi-Fi, but a future variant (serial over USB, or a different protocol stack) is plausible. Hard-coding the `websockets` library throughout `Esp32Client` would lock us in.

**Pattern.** *Strategy* (GoF behavioural pattern). Define a family of algorithms, encapsulate each one behind a common interface, and make them interchangeable at runtime.

**Application.** `infrastructure/transport.py::Transport` is an abstract base class:

```python
class Transport(ABC):
    @abstractmethod async def connect(self, url: str) -> None: ...
    @abstractmethod async def disconnect(self) -> None: ...
    @abstractmethod async def send(self, text: str) -> None: ...
    @abstractmethod def messages(self) -> AsyncIterator[str]: ...
```

`infrastructure/websocket_transport.py::WebSocketTransport` is the only concrete strategy used in production. `Esp32Client.__init__` accepts a `transport: Transport | None` parameter and defaults to `WebSocketTransport()`. Tests inject a fake.

**Alternatives considered.**
- *Direct use of `websockets`* in `Esp32Client`: simpler, but couples the facade to a specific library and makes integration testing harder (you'd need to start a real WebSocket server even for fast tests).
- *Plain function with library inside*: works, but doesn't capture the lifecycle (connect/disconnect/send/receive) as a coherent object.
- *Duck-typing without an ABC*: would compile, but the ABC documents the contract and catches missing methods at import time.

**Trade-offs.**
- One extra layer of indirection for code that today only has one implementation. Justified because the abstraction lets us write the integration tests against a `fake_ws_server` fixture cleanly and would let a `SerialTransport` slot in without touching anything above `infrastructure/`.
- The abstract `messages()` is an async generator — slightly less obvious than a callback, but composes naturally with `async for` inside the client.

---

## 3. State — `ConnectionStateMachine`

**Problem.** The connection has several distinct lifecycle phases: idle, opening, connected, retrying after a drop, and a fatal error. Different code paths must run in each phase (the UI enables/disables buttons, the client decides whether to send or queue, reconnection logic decides whether to back off). Sprinkling `if connected and not error and not reconnecting: ...` boolean checks throughout the codebase produces bug-prone, hard-to-trace logic.

**Pattern.** *State* (GoF behavioural pattern). Encapsulate the allowed states and the legal transitions between them in a single object. Calling code asks "what state are we in?" and "is this transition legal?" instead of juggling flags.

**Application.** `domain/state.py` defines:

```python
class ConnectionState(Enum):
    DISCONNECTED
    CONNECTING
    CONNECTED
    RECONNECTING
    ERROR
```

…and `ConnectionStateMachine` which owns the current state plus a transition table mapping each state to its legal successors. Illegal transitions raise `IllegalTransitionError`. The transition diagram is documented in `05-state-machine.md` and rendered as `uml/state_connection.puml`.

`Esp32Client` delegates all state questions to the FSM (`client.state`) and emits `state_changed` whenever a transition succeeds. The control panel and status bar consume the signal as Observers (see pattern 5 below).

**Alternatives considered.**
- *Boolean flags* (`is_connected`, `is_reconnecting`): two flags create four states; five real states need three, with most combinations meaningless. Easy to enter contradictory combinations.
- *Pattern via separate classes per state* (the "classic" GoF rendering): heavier; each transition becomes a polymorphic call. Overkill for five states with no per-state behaviour beyond "is this allowed".
- *Inline string constants* instead of an enum: loses static checking.

**Trade-offs.**
- The FSM lives in `domain/`, framework-free, and is therefore reusable and testable in isolation (see `tests/test_state_machine.py`).
- A pure transition table can't express "auto-progress after N seconds"; reconnection backoff lives in `Esp32Client`, which calls `transition_to(...)` at the right moments. That's by design — the FSM models *which* transitions are legal, not *when* they fire.

---

## 4. Command — `ToggleLedCommand`, `PingCommand`

**Problem.** When the user clicks a button, we need to send a JSON message that names an action and carries a unique correlation id (`cmd_id`) so we can match the ack later. Two distinct UI buttons, two distinct payloads. If each button built its own JSON inline, the wire-protocol shape would leak into the UI.

**Pattern.** *Command* (GoF behavioural pattern). Encapsulate a request as an object so it can be parameterised, queued, logged, and decoupled from its invoker.

**Application.** `application/commands.py` defines an abstract `Command` dataclass with:

```python
@dataclass(frozen=True)
class Command(ABC):
    cmd_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @abstractmethod
    def action(self) -> str: ...

    def serialize(self) -> dict[str, Any]:
        return {"type": "cmd", "cmd_id": self.cmd_id, "action": self.action()}
```

Concrete subclasses are tiny: `ToggleLedCommand` returns `"toggle_led"` from `action()`, `PingCommand` returns `"ping"`. UI code constructs `ToggleLedCommand()` (UUID is generated for free) and hands it to `Esp32Client.send(...)`. The client calls `serialize()` and pipes the dict through the codec.

**Alternatives considered.**
- *Plain function calls* (`client.send_toggle_led()`): works for two actions, scales poorly. Adding a new command means adding a new method on the facade and the UI, instead of one new dataclass.
- *Raw dictionaries in the UI*: leaks the wire shape; renaming a JSON field would touch every widget.
- *Enums* (`Action.TOGGLE_LED`): works for parameterless commands. The Command pattern accommodates future commands that carry payloads (e.g. `SetIntervalCommand(ms=250)`) without changing the call site signature.

**Trade-offs.**
- Adds a small object hierarchy where two `if/elif` branches could have sufficed for now. The hierarchy pays off the moment we add a third command or a command with arguments.
- `cmd_id` is generated client-side via `uuid.uuid4()`; we don't need a coordination service.

---

## 5. Observer — Qt signals on `Esp32Client`

**Problem.** Telemetry arrives asynchronously, possibly at 2 Hz. State changes and errors happen at unpredictable times. The chart widget, the control panel, and the status bar all need to react, but `Esp32Client` shouldn't know which widgets exist.

**Pattern.** *Observer* (GoF behavioural pattern). Subjects notify a list of observers when state changes, with observers registering and unregistering dynamically.

**Application.** `Esp32Client` is a `QObject` that exposes four Qt signals:

```python
telemetry_received = Signal(Telemetry)
ack_received       = Signal(Ack)
state_changed      = Signal(ConnectionState)
error_occurred     = Signal(str)
```

Each widget connects its slot to the signals it cares about:

- `ChartWidget.append_sample` ← `telemetry_received`
- `ControlPanel.on_state_changed` ← `state_changed`
- `ConnectionStatusBar.on_state_changed` ← `state_changed`
- `ConnectionStatusBar.on_error` ← `error_occurred`

This is the idiomatic Qt rendering of the Observer pattern. Connections are made centrally in `MainWindow.__init__`.

**Alternatives considered.**
- *Polling*: widgets ask the client "any new telemetry?" on a timer. Wastes cycles and adds latency. Not how Qt is meant to be used.
- *Hand-rolled callback lists*: PySide6 already provides thread-safe signal/slot infrastructure with queued dispatch across threads. Reinventing it would be strictly worse.

**Trade-offs.**
- Qt signals are typed (each declares its payload types), but the type hints don't propagate to slots — runtime errors at connection time if signatures mismatch. Mitigated by direct testing of each widget's slot in `tests/test_ui.py`.
- Signals are best-effort: a slow slot delays the next emission's processing because they share the event loop. Our slots are O(1) (append to a deque, update one label).

---

## 6. Singleton — `Config.instance()`

**Problem.** The application has a small bundle of user-level settings (the last URL entered, the window geometry to restore) that must be readable from anywhere and persisted to a single JSON file on disk. Letting any code construct a new `Config` would lead to multiple in-memory copies that disagree.

**Pattern.** *Singleton* (GoF creational pattern). Ensure a class has only one instance and provide a global access point.

**Application.** `config.py::Config` is a dataclass with a classmethod accessor:

```python
@classmethod
def instance(cls) -> Self:
    if cls._instance is None:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls._load()
    return cls._instance
```

First access loads `~/.config/esp32-link/config.json` (or returns defaults). `MainWindow` reads `last_url` to pre-fill the URL field on launch and writes back `window_geometry` and `last_url` in `closeEvent` via `Config.instance().save()`.

**Alternatives considered.**
- *Module-level globals* in `config.py`: equivalent in practice but doesn't model the "loaded-from-disk-once" lifecycle as clearly.
- *Dependency injection*: passing a `Config` instance through every constructor adds noise for a clearly application-wide piece of state.
- *Qt's `QSettings`*: would also work and is platform-aware, but ties the persistence layer to Qt, which we've otherwise kept out of `config.py`.

**Trade-offs.**
- Global state is testable but requires care: `Config.reset()` (a test hook) clears the cached instance so tests can monkeypatch `CONFIG_PATH` per test.
- Singletons can hide dependencies. For a two-field config used at startup and shutdown, the readability win of `Config.instance().last_url` outweighs the cost.

---

## Incidental patterns

The following are used freely but not documented as featured patterns:

- **Value Object** — `Telemetry` and `Ack` are immutable, slotted, frozen dataclasses with structural equality.
- **Repository-ish** — `Config` happens to also be the persistence boundary for its own state. We don't formalise it as a separate Repository because the dataset is tiny.
- **Template Method** — `Command.serialize()` is the common skeleton; subclasses fill in `action()`.

These are useful idioms, but the six patterns above are the ones we *document and showcase* because they map cleanly onto the project's structural decisions.
