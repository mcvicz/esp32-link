"""Unit tests asserting each Command serializes to the documented JSON shape."""

import json

from esp32_link.application.commands import PingCommand, ToggleLedCommand


def test_toggle_led_serializes_to_documented_shape() -> None:
    cmd = ToggleLedCommand()
    payload = cmd.serialize()
    assert payload["type"] == "cmd"
    assert payload["action"] == "toggle_led"
    assert isinstance(payload["cmd_id"], str) and payload["cmd_id"]


def test_ping_serializes_to_documented_shape() -> None:
    cmd = PingCommand()
    payload = cmd.serialize()
    assert payload["type"] == "cmd"
    assert payload["action"] == "ping"


def test_cmd_id_is_unique_per_instance() -> None:
    a = ToggleLedCommand()
    b = ToggleLedCommand()
    assert a.cmd_id != b.cmd_id


def test_explicit_cmd_id_is_preserved() -> None:
    cmd = PingCommand(cmd_id="fixed-id")
    assert cmd.serialize()["cmd_id"] == "fixed-id"


def test_serialized_payload_is_json_safe() -> None:
    cmd = ToggleLedCommand()
    encoded = json.dumps(cmd.serialize())
    assert json.loads(encoded) == cmd.serialize()
