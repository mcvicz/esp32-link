"""ConnectionState enum and finite-state machine that owns transport state transitions."""

from enum import Enum, auto


class ConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    ERROR = auto()


class IllegalTransitionError(RuntimeError):
    """Raised when an illegal ConnectionState transition is attempted."""


_TRANSITIONS: dict[ConnectionState, frozenset[ConnectionState]] = {
    ConnectionState.DISCONNECTED: frozenset({ConnectionState.CONNECTING}),
    ConnectionState.CONNECTING: frozenset(
        {ConnectionState.CONNECTED, ConnectionState.ERROR, ConnectionState.DISCONNECTED}
    ),
    ConnectionState.CONNECTED: frozenset(
        {ConnectionState.DISCONNECTED, ConnectionState.RECONNECTING, ConnectionState.ERROR}
    ),
    ConnectionState.RECONNECTING: frozenset(
        {ConnectionState.CONNECTED, ConnectionState.ERROR, ConnectionState.DISCONNECTED}
    ),
    ConnectionState.ERROR: frozenset(
        {
            ConnectionState.DISCONNECTED,
            ConnectionState.CONNECTING,
            ConnectionState.RECONNECTING,
        }
    ),
}


class ConnectionStateMachine:
    """FSM that owns the ConnectionState and validates transitions."""

    def __init__(self) -> None:
        self._state: ConnectionState = ConnectionState.DISCONNECTED

    @property
    def state(self) -> ConnectionState:
        return self._state

    def can_transition_to(self, target: ConnectionState) -> bool:
        return target in _TRANSITIONS[self._state]

    def transition_to(self, target: ConnectionState) -> None:
        if target not in _TRANSITIONS[self._state]:
            raise IllegalTransitionError(f"illegal transition: {self._state.name} -> {target.name}")
        self._state = target
