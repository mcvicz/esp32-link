"""Integration tests exercising ``Esp32Client`` against the ``fake_ws_server`` fixture."""

import json

from conftest import FakeWsServer

from esp32_link.application.client import Esp32Client
from esp32_link.application.commands import PingCommand, ToggleLedCommand
from esp32_link.domain.messages import Ack, Telemetry
from esp32_link.domain.state import ConnectionState


def test_client_receives_telemetry(qtbot, fake_ws_server: FakeWsServer) -> None:
    frame = '{"type":"telemetry","ts":100,"temp_c":42.5,"free_heap":12345,"rssi":-40}\n'

    async def push(ws: object) -> None:
        await ws.send(frame)  # type: ignore[attr-defined]

    fake_ws_server.on_connect_handler = push

    client = Esp32Client()
    try:
        with qtbot.waitSignal(client.telemetry_received, timeout=5000) as blocker:
            client.connect(fake_ws_server.url)
        telemetry = blocker.args[0]
        assert isinstance(telemetry, Telemetry)
        assert telemetry == Telemetry(ts=100, temp_c=42.5, free_heap=12345, rssi=-40)
    finally:
        client.disconnect()


def test_client_receives_ack(qtbot, fake_ws_server: FakeWsServer) -> None:
    frame = '{"type":"ack","cmd_id":"abc","ok":true,"msg":"pong"}\n'

    async def push(ws: object) -> None:
        await ws.send(frame)  # type: ignore[attr-defined]

    fake_ws_server.on_connect_handler = push

    client = Esp32Client()
    try:
        with qtbot.waitSignal(client.ack_received, timeout=5000) as blocker:
            client.connect(fake_ws_server.url)
        ack = blocker.args[0]
        assert isinstance(ack, Ack)
        assert ack == Ack(cmd_id="abc", ok=True, msg="pong")
    finally:
        client.disconnect()


def test_client_sends_command(qtbot, fake_ws_server: FakeWsServer) -> None:
    client = Esp32Client()
    try:
        with qtbot.waitSignal(client.state_changed, timeout=5000):
            client.connect(fake_ws_server.url)
        qtbot.waitUntil(lambda: client.state == ConnectionState.CONNECTED, timeout=5000)
        client.send(PingCommand(cmd_id="t1"))
        qtbot.waitUntil(lambda: len(fake_ws_server.received_from_clients) >= 1, timeout=5000)
        payload = json.loads(fake_ws_server.received_from_clients[0])
        assert payload == {"type": "cmd", "cmd_id": "t1", "action": "ping"}
    finally:
        client.disconnect()


def test_client_emits_state_changes(qtbot, fake_ws_server: FakeWsServer) -> None:
    client = Esp32Client()
    try:
        with qtbot.waitSignal(
            client.state_changed,
            timeout=5000,
            check_params_cb=lambda s: s == ConnectionState.CONNECTED,
        ):
            client.connect(fake_ws_server.url)
        assert client.state == ConnectionState.CONNECTED
    finally:
        with qtbot.waitSignal(
            client.state_changed,
            timeout=5000,
            check_params_cb=lambda s: s == ConnectionState.DISCONNECTED,
        ):
            client.disconnect()
        assert client.state == ConnectionState.DISCONNECTED


def test_client_serializes_toggle_led_command(qtbot, fake_ws_server: FakeWsServer) -> None:
    client = Esp32Client()
    try:
        client.connect(fake_ws_server.url)
        qtbot.waitUntil(lambda: client.state == ConnectionState.CONNECTED, timeout=5000)
        client.send(ToggleLedCommand(cmd_id="led-1"))
        qtbot.waitUntil(lambda: len(fake_ws_server.received_from_clients) >= 1, timeout=5000)
        payload = json.loads(fake_ws_server.received_from_clients[0])
        assert payload == {"type": "cmd", "cmd_id": "led-1", "action": "toggle_led"}
    finally:
        client.disconnect()
