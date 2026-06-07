"""``Esp32Client`` Facade hiding transport, codec, FSM, and reconnection from the UI."""

import asyncio
import logging
import threading
from collections.abc import Sequence
from typing import Final

from PySide6.QtCore import QObject, Signal

from esp32_link.application.commands import Command
from esp32_link.domain.messages import Ack, Telemetry
from esp32_link.domain.state import ConnectionState, ConnectionStateMachine
from esp32_link.infrastructure.codec import decode, encode
from esp32_link.infrastructure.transport import Transport
from esp32_link.infrastructure.websocket_transport import WebSocketTransport

logger = logging.getLogger(__name__)

RECONNECT_BACKOFF_SEC: Final[Sequence[float]] = (1.0, 2.0, 4.0, 8.0)


class Esp32Client(QObject):
    """Facade over transport, codec, FSM, and reconnection.

    Observer pattern: emits Qt signals consumed by UI widgets. The asyncio
    transport loop runs in a background thread; signals cross threads via Qt's
    default queued connection, so slots execute on the GUI thread.
    """

    telemetry_received = Signal(Telemetry)
    ack_received = Signal(Ack)
    state_changed = Signal(ConnectionState)
    error_occurred = Signal(str)

    def __init__(
        self,
        transport: Transport | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._transport: Transport = transport if transport is not None else WebSocketTransport()
        self._fsm = ConnectionStateMachine()
        self._url: str = ""
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._loop_ready = threading.Event()

    @property
    def state(self) -> ConnectionState:
        return self._fsm.state

    def connect(self, url: str) -> None:
        """Begin the asyncio loop in a background thread and connect to ``url``."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("connect ignored — client already running")
            return
        self._url = url
        self._loop_ready.clear()
        self._thread = threading.Thread(target=self._run_thread, daemon=True, name="esp32-client")
        self._thread.start()

    def disconnect(self) -> None:
        """Request shutdown of the asyncio loop and wait for the thread to exit."""
        if self._loop is None or self._stop_event is None:
            return
        loop = self._loop
        stop = self._stop_event
        loop.call_soon_threadsafe(stop.set)
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def send(self, command: Command) -> None:
        """Serialize ``command`` and send it over the transport."""
        if self._loop is None:
            self._emit_error("send before connect")
            return
        text = encode(command.serialize())
        asyncio.run_coroutine_threadsafe(self._transport.send(text), self._loop)

    # internal

    def _run_thread(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._stop_event = asyncio.Event()
        self._loop_ready.set()
        try:
            loop.run_until_complete(self._main())
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            self._loop = None
            self._stop_event = None

    async def _main(self) -> None:
        assert self._stop_event is not None
        attempt = 0
        try:
            while not self._stop_event.is_set():
                target = (
                    ConnectionState.CONNECTING if attempt == 0 else ConnectionState.RECONNECTING
                )
                self._set_state(target)
                try:
                    await self._transport.connect(self._url)
                except Exception as exc:
                    self._emit_error(f"connect failed: {exc}")
                    self._set_state(ConnectionState.ERROR)
                    if await self._wait_with_stop(self._backoff(attempt)):
                        break
                    attempt += 1
                    continue

                self._set_state(ConnectionState.CONNECTED)
                attempt = 0
                await self._run_receive_until_stop_or_close()
                try:
                    await self._transport.disconnect()
                except Exception:
                    pass
                if self._stop_event.is_set():
                    break
                attempt = 1
        finally:
            try:
                await self._transport.disconnect()
            except Exception:
                pass
            self._set_state(ConnectionState.DISCONNECTED)

    async def _run_receive_until_stop_or_close(self) -> None:
        assert self._stop_event is not None
        recv_task = asyncio.create_task(self._receive_loop(), name="esp32-recv")
        stop_task = asyncio.create_task(self._stop_event.wait(), name="esp32-stop")
        try:
            done, pending = await asyncio.wait(
                {recv_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for task in (recv_task, stop_task):
                if not task.done():
                    task.cancel()
            for task in (recv_task, stop_task):
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        if recv_task in done:
            exc = recv_task.exception()
            if exc is not None and not isinstance(exc, asyncio.CancelledError):
                self._emit_error(f"connection lost: {exc}")

    async def _receive_loop(self) -> None:
        async for chunk in self._transport.messages():
            for line in chunk.splitlines():
                msg = decode(line)
                if isinstance(msg, Telemetry):
                    self.telemetry_received.emit(msg)
                elif isinstance(msg, Ack):
                    self.ack_received.emit(msg)

    async def _wait_with_stop(self, delay: float) -> bool:
        """Wait up to ``delay`` seconds or until stop is set. Return True if stop was set."""
        assert self._stop_event is not None
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            return True
        except TimeoutError:
            return False

    @staticmethod
    def _backoff(attempt: int) -> float:
        if attempt < len(RECONNECT_BACKOFF_SEC):
            return RECONNECT_BACKOFF_SEC[attempt]
        return RECONNECT_BACKOFF_SEC[-1]

    def _set_state(self, target: ConnectionState) -> None:
        if self._fsm.state == target:
            return
        if not self._fsm.can_transition_to(target):
            logger.debug("skipping illegal transition %s -> %s", self._fsm.state.name, target.name)
            return
        self._fsm.transition_to(target)
        logger.info("state -> %s", target.name)
        self.state_changed.emit(target)

    def _emit_error(self, msg: str) -> None:
        logger.error(msg)
        self.error_occurred.emit(msg)
