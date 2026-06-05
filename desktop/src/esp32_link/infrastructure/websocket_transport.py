"""Concrete ``Transport`` implementation backed by the ``websockets`` library."""

import logging
from collections.abc import AsyncIterator

import websockets
from websockets.asyncio.client import ClientConnection

from esp32_link.infrastructure.transport import Transport

logger = logging.getLogger(__name__)


class WebSocketTransport(Transport):
    """Transport over a single WebSocket connection."""

    def __init__(self) -> None:
        self._ws: ClientConnection | None = None

    async def connect(self, url: str) -> None:
        logger.info("connecting to %s", url)
        self._ws = await websockets.connect(url)
        logger.info("connected to %s", url)

    async def disconnect(self) -> None:
        if self._ws is None:
            return
        ws, self._ws = self._ws, None
        try:
            await ws.close()
        except Exception as exc:
            logger.debug("error closing websocket: %s", exc)
        logger.info("disconnected")

    async def send(self, text: str) -> None:
        if self._ws is None:
            raise RuntimeError("transport not connected")
        logger.debug("send: %s", text.rstrip())
        await self._ws.send(text)

    async def messages(self) -> AsyncIterator[str]:
        if self._ws is None:
            raise RuntimeError("transport not connected")
        async for raw in self._ws:
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
            logger.debug("recv: %s", text.rstrip())
            yield text
