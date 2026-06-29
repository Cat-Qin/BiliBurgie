"""IRC server simulator for the game client on 127.0.0.1:6667."""
from __future__ import annotations
import asyncio
import logging
from typing import Optional, Callable, Awaitable
from ..utils.constants import IRC_CHANNEL

logger = logging.getLogger("BurgerRelay.irc")

class IRCServer:
    """Minimal IRC server that the game client connects to."""

    def __init__(self, host: str = "127.0.0.1", port: int = 6667) -> None:
        self._host = host
        self._port = port
        self._server: Optional[asyncio.AbstractServer] = None
        self._clients: dict[asyncio.StreamWriter, str] = {}
        self._running = False
        self._on_client_change: Optional[Callable[[bool], Awaitable[None]]] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def set_client_change_callback(self, cb: Callable[[bool], Awaitable[None]]) -> None:
        self._on_client_change = cb

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self._host, self._port
        )
        self._running = True
        logger.info(f"IRC server started on {self._host}:{self._port}")

    async def stop(self) -> None:
        self._running = False
        for writer in list(self._clients.keys()):
            try:
                writer.close()
            except Exception:
                pass
        self._clients.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("IRC server stopped")

    async def send_message(self, nickname: str, message: str) -> None:
        """Send a PRIVMSG to all connected clients."""
        irc_msg = f":{nickname}!user@BurgerRelay PRIVMSG {IRC_CHANNEL} :CHAT|{nickname}|{message}|\r\n"
        disconnected = []
        for writer in list(self._clients.keys()):
            try:
                writer.write(irc_msg.encode("utf-8"))
                await writer.drain()
            except Exception:
                disconnected.append(writer)
        for w in disconnected:
            await self._remove_client(w)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername", ("?", 0))
        logger.info(f"Game client connected: {addr}")
        self._clients[writer] = str(addr)
        await self._notify_client_change()
        await self._send_handshake(writer)
        try:
            while self._running:
                data = await asyncio.wait_for(reader.readline(), timeout=300)
                if not data:
                    break
                line = data.decode("utf-8", errors="replace").strip()
                await self._handle_line(writer, line)
        except (asyncio.TimeoutError, ConnectionError, OSError):
            pass
        finally:
            await self._remove_client(writer)

    async def _send_handshake(self, writer: asyncio.StreamWriter) -> None:
        def w(msg: str) -> None:
            writer.write(f"{msg}\r\n".encode("utf-8"))
        w(":BurgerRelay 001 BurgerRelay :Welcome to Burger Relay IRC")
        w(":BurgerRelay 002 BurgerRelay :Your host is BurgerRelay")
        w(":BurgerRelay 003 BurgerRelay :This server was created by Burger Relay")
        w(":BurgerRelay 004 BurgerRelay :BurgerRelay 1.0")
        w(":BurgerRelay 375 BurgerRelay :- Message of the Day -")
        w(":BurgerRelay 372 BurgerRelay :- Welcome to Burger Relay IRC Server!")
        w(":BurgerRelay 376 BurgerRelay :End of /MOTD command")
        await writer.drain()

    async def _handle_line(self, writer: asyncio.StreamWriter, line: str) -> None:
        if line.upper().startswith("PING"):
            pong = line.replace("PING", "PONG", 1)
            writer.write(f"{pong}\r\n".encode("utf-8"))
            await writer.drain()

    async def _remove_client(self, writer: asyncio.StreamWriter) -> None:
        if writer in self._clients:
            addr = self._clients.pop(writer)
            logger.info(f"Game client disconnected: {addr}")
            await self._notify_client_change()
        try:
            writer.close()
        except Exception:
            pass

    async def _notify_client_change(self) -> None:
        if self._on_client_change:
            try:
                await self._on_client_change(len(self._clients) > 0)
            except Exception:
                pass
