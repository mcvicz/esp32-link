"""JSON encode/decode helpers for the line-delimited wire protocol."""

import json
import logging
from typing import Any

from esp32_link.domain.messages import Ack, Telemetry

logger = logging.getLogger(__name__)

type InboundMessage = Telemetry | Ack


def encode(payload: dict[str, Any]) -> str:
    """Serialize ``payload`` to a compact JSON line terminated by ``\\n``."""
    return json.dumps(payload, separators=(",", ":")) + "\n"


def decode(line: str) -> InboundMessage | None:
    """Parse one inbound JSON line into a Telemetry or Ack, or return None and log if invalid."""
    raw = line.strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("malformed JSON dropped: %s", raw[:60])
        return None
    if not isinstance(obj, dict):
        logger.warning("non-object payload dropped: %s", raw[:60])
        return None
    mtype = obj.get("type")
    if mtype == "telemetry":
        return _decode_telemetry(obj, raw)
    if mtype == "ack":
        return _decode_ack(obj, raw)
    logger.warning("unknown message type %r dropped: %s", mtype, raw[:60])
    return None


def _decode_telemetry(obj: dict[str, Any], raw: str) -> Telemetry | None:
    try:
        return Telemetry(
            ts=int(obj["ts"]),
            temp_c=float(obj["temp_c"]),
            free_heap=int(obj["free_heap"]),
            rssi=int(obj["rssi"]),
        )
    except (KeyError, TypeError, ValueError):
        logger.warning("malformed telemetry dropped: %s", raw[:60])
        return None


def _decode_ack(obj: dict[str, Any], raw: str) -> Ack | None:
    try:
        return Ack(
            cmd_id=str(obj["cmd_id"]),
            ok=bool(obj["ok"]),
            msg=str(obj.get("msg", "")),
        )
    except (KeyError, TypeError):
        logger.warning("malformed ack dropped: %s", raw[:60])
        return None
