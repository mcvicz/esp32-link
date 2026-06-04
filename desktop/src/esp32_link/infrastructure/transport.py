"""Abstract ``Transport`` base class defining the Strategy contract for byte transports."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class Transport(ABC):
    """Strategy interface for a bidirectional text transport.

    The current concrete implementation is :class:`WebSocketTransport`. The
    abstraction exists so a future ``SerialTransport`` can be plugged in without
    touching ``Esp32Client`` or the UI.
    """

    @abstractmethod
    async def connect(self, url: str) -> None:
        """Open the transport. ``url`` is implementation-specific."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the transport. Must be idempotent."""

    @abstractmethod
    async def send(self, text: str) -> None:
        """Send one text frame."""

    @abstractmethod
    def messages(self) -> AsyncIterator[str]:
        """Asynchronously yield incoming text frames until the transport closes."""
