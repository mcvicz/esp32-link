"""Command pattern: abstract ``Command`` plus concrete user-action commands."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


def _new_cmd_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class Command(ABC):
    """Abstract user-action command. UI builds these and passes them to ``Esp32Client.send``."""

    cmd_id: str = field(default_factory=_new_cmd_id)

    @abstractmethod
    def action(self) -> str:
        """Wire-protocol ``action`` identifier."""

    def serialize(self) -> dict[str, Any]:
        """Render as the JSON-object payload defined in CLAUDE.md's wire protocol."""
        return {"type": "cmd", "cmd_id": self.cmd_id, "action": self.action()}


@dataclass(frozen=True)
class ToggleLedCommand(Command):
    """Toggle the onboard LED on the ESP32."""

    def action(self) -> str:
        return "toggle_led"


@dataclass(frozen=True)
class PingCommand(Command):
    """No-op ping; ESP32 replies with ``pong``."""

    def action(self) -> str:
        return "ping"
