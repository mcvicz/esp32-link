"""Top-level QMainWindow wiring the chart, control panel, and status bar to ``Esp32Client``."""

import logging

from PySide6.QtCore import QByteArray, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from esp32_link.application.client import Esp32Client
from esp32_link.application.commands import PingCommand, ToggleLedCommand
from esp32_link.config import Config
from esp32_link.domain.state import ConnectionState
from esp32_link.ui.chart_widget import ChartWidget
from esp32_link.ui.control_panel import ControlPanel
from esp32_link.ui.status_bar import ConnectionStatusBar

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Application window. Owns the Esp32Client and connects its signals to widgets."""

    def __init__(self, client: Esp32Client | None = None) -> None:
        super().__init__()
        self.setWindowTitle("esp32-link")
        self.resize(900, 700)

        self._config = Config.instance()
        self._client = client if client is not None else Esp32Client(parent=self)

        self._chart = ChartWidget()
        self._control_panel = ControlPanel(initial_url=self._config.last_url)
        self._status_bar = ConnectionStatusBar()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self._chart, 1)
        layout.addWidget(self._control_panel)
        self.setCentralWidget(central)
        self.setStatusBar(self._status_bar)

        self._client.telemetry_received.connect(self._chart.append_sample)
        self._client.state_changed.connect(self._control_panel.on_state_changed)
        self._client.state_changed.connect(self._status_bar.on_state_changed)
        self._client.error_occurred.connect(self._status_bar.on_error)

        self._control_panel.connect_requested.connect(self._on_connect_requested)
        self._control_panel.disconnect_requested.connect(self._client.disconnect)
        self._control_panel.toggle_led_requested.connect(self._on_toggle_led)
        self._control_panel.ping_requested.connect(self._on_ping)

        self._restore_geometry()

    @Slot(str)
    def _on_connect_requested(self, url: str) -> None:
        logger.info("user requested connect to %s", url)
        self._status_bar.on_error("")
        self._chart.clear_samples()
        self._config.last_url = url
        self._client.connect(url)

    @Slot()
    def _on_toggle_led(self) -> None:
        self._client.send(ToggleLedCommand())

    @Slot()
    def _on_ping(self) -> None:
        self._client.send(PingCommand())

    def _restore_geometry(self) -> None:
        geom = self._config.window_geometry
        if not geom:
            return
        try:
            self.restoreGeometry(QByteArray.fromBase64(geom.encode("ascii")))
        except Exception as exc:
            logger.debug("could not restore window geometry: %s", exc)

    def _persist_state(self) -> None:
        self._config.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self._config.last_url = self._control_panel.url()
        try:
            self._config.save()
        except OSError as exc:
            logger.warning("could not write config: %s", exc)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._persist_state()
        if self._client.state != ConnectionState.DISCONNECTED:
            self._client.disconnect()
        super().closeEvent(event)
