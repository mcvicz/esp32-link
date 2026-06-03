"""Dataclasses for wire-protocol messages (telemetry, ack)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Telemetry:
    """Telemetry frame pushed by the ESP32 at 2 Hz."""

    ts: int
    temp_c: float
    free_heap: int
    rssi: int


@dataclass(frozen=True, slots=True)
class Ack:
    """Command acknowledgment returned by the ESP32."""

    cmd_id: str
    ok: bool
    msg: str
