"""Status bar widget reflecting connection state and last error."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

from esp32_link.domain.state import ConnectionState

_STATE_COLOR: dict[ConnectionState, str] = {
    ConnectionState.DISCONNECTED: "#888888",
    ConnectionState.CONNECTING: "#b58900",
    ConnectionState.CONNECTED: "#859900",
    ConnectionState.RECONNECTING: "#b58900",
    ConnectionState.ERROR: "#dc322f",
}


class ConnectionStatusBar(QStatusBar):
    """QStatusBar showing a colored connection-state badge and the last error message."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state_label = QLabel()
        self._error_label = QLabel()
        self.addWidget(self._state_label)
        self.addPermanentWidget(self._error_label)
        self.on_state_changed(ConnectionState.DISCONNECTED)

    @Slot(ConnectionState)
    def on_state_changed(self, state: ConnectionState) -> None:
        color = _STATE_COLOR[state]
        self._state_label.setText(
            f'<span style="color:{color};">●</span> {state.name.capitalize()}'
        )

    @Slot(str)
    def on_error(self, message: str) -> None:
        if message:
            self._error_label.setText(f'<span style="color:#dc322f;">{message}</span>')
        else:
            self._error_label.setText("")
