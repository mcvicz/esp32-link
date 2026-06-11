"""Control panel widget exposing connect/disconnect and command buttons to the user."""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from esp32_link.domain.state import ConnectionState

DEFAULT_URL: str = "ws://192.168.4.1:81/ws"


class ControlPanel(QWidget):
    """User-input panel. Emits high-level intent signals; never builds raw JSON."""

    connect_requested = Signal(str)
    disconnect_requested = Signal()
    toggle_led_requested = Signal()
    ping_requested = Signal()

    def __init__(self, initial_url: str = DEFAULT_URL, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._url_edit = QLineEdit(initial_url)
        self._url_edit.setPlaceholderText("ws://host:port/path")

        self._connect_btn = QPushButton("Connect")
        self._toggle_led_btn = QPushButton("Toggle LED")
        self._ping_btn = QPushButton("Ping")

        url_row = QHBoxLayout()
        url_row.addWidget(self._url_edit, 1)
        url_row.addWidget(self._connect_btn)

        action_row = QHBoxLayout()
        action_row.addWidget(self._toggle_led_btn)
        action_row.addWidget(self._ping_btn)
        action_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(url_row)
        layout.addLayout(action_row)

        self._connect_btn.clicked.connect(self._on_connect_clicked)
        self._toggle_led_btn.clicked.connect(self.toggle_led_requested)
        self._ping_btn.clicked.connect(self.ping_requested)

        self._is_session_active: bool = False
        self.on_state_changed(ConnectionState.DISCONNECTED)

    def url(self) -> str:
        return self._url_edit.text().strip()

    @Slot(ConnectionState)
    def on_state_changed(self, state: ConnectionState) -> None:
        is_connected = state == ConnectionState.CONNECTED
        is_busy = state in (ConnectionState.CONNECTING, ConnectionState.RECONNECTING)
        self._is_session_active = is_connected or is_busy

        self._connect_btn.setText("Disconnect" if self._is_session_active else "Connect")
        self._url_edit.setEnabled(not self._is_session_active)
        self._toggle_led_btn.setEnabled(is_connected)
        self._ping_btn.setEnabled(is_connected)

    def _on_connect_clicked(self) -> None:
        if self._is_session_active:
            self.disconnect_requested.emit()
        else:
            self.connect_requested.emit(self.url())
