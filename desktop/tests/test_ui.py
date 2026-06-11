"""Smoke tests for UI widgets: construction and state propagation."""

from esp32_link.domain.messages import Telemetry
from esp32_link.domain.state import ConnectionState
from esp32_link.ui.chart_widget import ChartWidget
from esp32_link.ui.control_panel import DEFAULT_URL, ControlPanel
from esp32_link.ui.status_bar import ConnectionStatusBar


def test_chart_widget_appends_samples(qtbot) -> None:
    chart = ChartWidget()
    qtbot.addWidget(chart)

    chart.append_sample(Telemetry(ts=0, temp_c=25.0, free_heap=200_000, rssi=-50))
    chart.append_sample(Telemetry(ts=500, temp_c=25.5, free_heap=199_500, rssi=-51))
    chart.append_sample(Telemetry(ts=1000, temp_c=26.0, free_heap=199_000, rssi=-52))

    assert chart.sample_count == 3


def test_chart_widget_clear_resets(qtbot) -> None:
    chart = ChartWidget()
    qtbot.addWidget(chart)

    chart.append_sample(Telemetry(ts=0, temp_c=25.0, free_heap=200_000, rssi=-50))
    chart.clear_samples()

    assert chart.sample_count == 0


def test_chart_window_trims_old_samples(qtbot) -> None:
    chart = ChartWidget()
    qtbot.addWidget(chart)

    for i in range(200):
        chart.append_sample(Telemetry(ts=i * 500, temp_c=25.0, free_heap=200_000, rssi=-50))

    # 60s window @ 2 Hz = ~120 samples retained
    assert chart.sample_count <= 121


def test_control_panel_emits_connect_with_url(qtbot) -> None:
    panel = ControlPanel(initial_url="ws://test.local:81/ws")
    qtbot.addWidget(panel)

    with qtbot.waitSignal(panel.connect_requested) as blocker:
        panel._connect_btn.click()

    assert blocker.args == ["ws://test.local:81/ws"]


def test_control_panel_emits_disconnect_when_active(qtbot) -> None:
    panel = ControlPanel()
    qtbot.addWidget(panel)
    panel.on_state_changed(ConnectionState.CONNECTED)

    with qtbot.waitSignal(panel.disconnect_requested):
        panel._connect_btn.click()


def test_control_panel_command_buttons_disabled_until_connected(qtbot) -> None:
    panel = ControlPanel()
    qtbot.addWidget(panel)

    assert not panel._toggle_led_btn.isEnabled()
    assert not panel._ping_btn.isEnabled()

    panel.on_state_changed(ConnectionState.CONNECTED)

    assert panel._toggle_led_btn.isEnabled()
    assert panel._ping_btn.isEnabled()


def test_control_panel_command_buttons_disabled_when_reconnecting(qtbot) -> None:
    panel = ControlPanel()
    qtbot.addWidget(panel)
    panel.on_state_changed(ConnectionState.CONNECTED)
    panel.on_state_changed(ConnectionState.RECONNECTING)

    assert not panel._toggle_led_btn.isEnabled()
    assert panel._connect_btn.text() == "Disconnect"


def test_control_panel_emits_command_signals(qtbot) -> None:
    panel = ControlPanel()
    qtbot.addWidget(panel)
    panel.on_state_changed(ConnectionState.CONNECTED)

    with qtbot.waitSignal(panel.toggle_led_requested):
        panel._toggle_led_btn.click()
    with qtbot.waitSignal(panel.ping_requested):
        panel._ping_btn.click()


def test_status_bar_constructs_and_updates(qtbot) -> None:
    bar = ConnectionStatusBar()
    qtbot.addWidget(bar)

    for state in ConnectionState:
        bar.on_state_changed(state)

    bar.on_error("connect failed")
    bar.on_error("")


def test_default_url_matches_protocol_constants() -> None:
    assert DEFAULT_URL == "ws://192.168.4.1:81/ws"


def test_main_window_constructs(qtbot, tmp_path, monkeypatch) -> None:
    from esp32_link import config
    from esp32_link.ui.main_window import MainWindow

    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    config.Config.reset()

    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "esp32-link"
    assert window.statusBar() is not None
    assert window.centralWidget() is not None
