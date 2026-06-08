"""Unit tests for the JSON codec: serialize/parse round-trips and malformed input."""

import json

from esp32_link.domain.messages import Ack, Telemetry
from esp32_link.infrastructure.codec import decode, encode


def test_encode_terminates_with_newline_and_no_whitespace() -> None:
    out = encode({"type": "cmd", "cmd_id": "x", "action": "ping"})
    assert out.endswith("\n")
    assert " " not in out
    assert json.loads(out) == {"type": "cmd", "cmd_id": "x", "action": "ping"}


def test_decode_telemetry() -> None:
    raw = '{"type":"telemetry","ts":42,"temp_c":47.2,"free_heap":12345,"rssi":-50}'
    assert decode(raw) == Telemetry(ts=42, temp_c=47.2, free_heap=12345, rssi=-50)


def test_decode_ack() -> None:
    raw = '{"type":"ack","cmd_id":"abc","ok":true,"msg":"pong"}'
    assert decode(raw) == Ack(cmd_id="abc", ok=True, msg="pong")


def test_decode_strips_trailing_newline() -> None:
    raw = '{"type":"ack","cmd_id":"x","ok":true,"msg":""}\n'
    assert decode(raw) == Ack(cmd_id="x", ok=True, msg="")


def test_decode_malformed_json_returns_none() -> None:
    assert decode("not json {{") is None


def test_decode_unknown_type_returns_none() -> None:
    assert decode('{"type":"weird","x":1}') is None


def test_decode_missing_field_returns_none() -> None:
    assert decode('{"type":"telemetry","ts":1}') is None


def test_decode_empty_line_returns_none() -> None:
    assert decode("") is None
    assert decode("   \n") is None


def test_decode_non_object_returns_none() -> None:
    assert decode("[]") is None
    assert decode("42") is None


def test_encode_decode_roundtrip_via_serialize_shape() -> None:
    payload = {"type": "cmd", "cmd_id": "u", "action": "toggle_led"}
    line = encode(payload).rstrip("\n")
    assert json.loads(line) == payload
