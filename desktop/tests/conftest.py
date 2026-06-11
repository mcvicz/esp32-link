"""Shared pytest fixtures, including the ``fake_ws_server`` integration-test fixture."""

import os

# Force Qt's offscreen platform plugin before pytest-qt initialises so tests
# run without a display (CI, headless WSL).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import asyncio  # noqa: E402
import socket  # noqa: E402
import threading  # noqa: E402
from collections.abc import Awaitable, Callable, Iterator  # noqa: E402
from contextlib import closing  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

import pytest  # noqa: E402
import websockets

WsConnectHandler = Callable[[object], Awaitable[None]]


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class FakeWsServer:
    """Fake WebSocket server running in a background asyncio thread.

    Tests can install ``on_connect_handler`` to push canned frames at handshake
    time and read ``received_from_clients`` to assert what the client sent.
    """

    host: str
    port: int
    received_from_clients: list[str] = field(default_factory=list)
    on_connect_handler: WsConnectHandler | None = None

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"


@pytest.fixture
def fake_ws_server() -> Iterator[FakeWsServer]:
    host = "127.0.0.1"
    port = _free_port()
    fake = FakeWsServer(host=host, port=port)

    server_ready = threading.Event()
    stop_event = threading.Event()
    startup_error: list[BaseException] = []

    async def handler(ws: object) -> None:
        if fake.on_connect_handler is not None:
            await fake.on_connect_handler(ws)
        try:
            async for msg in ws:  # type: ignore[attr-defined]
                if isinstance(msg, bytes):
                    msg = msg.decode("utf-8", errors="replace")
                fake.received_from_clients.append(msg)
        except websockets.ConnectionClosed:
            pass

    async def main() -> None:
        async with websockets.serve(handler, host, port):
            server_ready.set()
            while not stop_event.is_set():
                await asyncio.sleep(0.05)

    def thread_target() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(main())
        except BaseException as exc:
            startup_error.append(exc)
            server_ready.set()
        finally:
            loop.close()

    t = threading.Thread(target=thread_target, daemon=True, name="fake-ws-server")
    t.start()
    if not server_ready.wait(timeout=5):
        raise RuntimeError("fake WebSocket server failed to start within 5s")
    if startup_error:
        raise startup_error[0]

    try:
        yield fake
    finally:
        stop_event.set()
        t.join(timeout=2)
