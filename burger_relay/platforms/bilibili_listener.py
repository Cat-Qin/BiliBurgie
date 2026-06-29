"""Bilibili live danmaku listener using blivedm."""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Callable, Awaitable, Optional

import aiohttp
from blivedm import BLiveClient
from blivedm.handlers import BaseHandler
from ..utils.models import DanmakuEvent, Platform, EventType

logger = logging.getLogger("BurgerRelay.bilibili")

# ---------------------------------------------------------------------------
# Monkey-patch blivedm to use updated B站 API endpoints.
# The old endpoints (xlive/web-room/v1/index/getInfoByRoom and getDanmuInfo)
# now require WBI signing and return -352 without it.
# The newer endpoints below still work without WBI signing.
# ---------------------------------------------------------------------------
_NEW_ROOM_INIT_URL = "https://api.live.bilibili.com/room/v1/Room/get_info"
_NEW_DANMAKU_CONF_URL = "https://api.live.bilibili.com/room/v1/Danmu/getConf"


async def _patched_init_room_id_and_owner(self: BLiveClient) -> bool:
    """Use the newer room/v1/Room/get_info endpoint."""
    try:
        async with self._session.get(
            _NEW_ROOM_INIT_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://live.bilibili.com/",
            },
            params={"room_id": self._tmp_room_id},
            ssl=self._ssl,
        ) as res:
            if res.status != 200:
                logger.warning(
                    "room=%d _init_room_id_and_owner() failed, status=%d, reason=%s",
                    self._tmp_room_id, res.status, res.reason,
                )
                return False
            data = await res.json()
            if data["code"] != 0:
                logger.warning(
                    "room=%d _init_room_id_and_owner() failed, message=%s",
                    self._tmp_room_id, data.get("message", data.get("msg", "")),
                )
                return False
            if not _patched_parse_room_init(self, data["data"]):
                return False
    except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
        logger.exception("room=%d _init_room_id_and_owner() failed:", self._tmp_room_id)
        return False
    return True


def _patched_parse_room_init(self: BLiveClient, data: dict) -> bool:
    """Parse response from room/v1/Room/get_info (flat structure)."""
    self._room_id = data["room_id"]
    self._room_short_id = data.get("short_id", 0) or 0
    self._room_owner_uid = data.get("uid", 0)
    return True


async def _patched_init_host_server(self: BLiveClient) -> bool:
    """Use the newer room/v1/Danmu/getConf endpoint."""
    try:
        async with self._session.get(
            _NEW_DANMAKU_CONF_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://live.bilibili.com/",
            },
            params={"room_id": self._room_id, "platform": "web"},
            ssl=self._ssl,
        ) as res:
            if res.status != 200:
                logger.warning(
                    "room=%d _init_host_server() failed, status=%d, reason=%s",
                    self._room_id, res.status, res.reason,
                )
                return False
            data = await res.json()
            if data["code"] != 0:
                logger.warning(
                    "room=%d _init_host_server() failed, message=%s",
                    self._room_id, data.get("message", data.get("msg", "")),
                )
                return False
            if not _patched_parse_danmaku_server_conf(self, data["data"]):
                return False
    except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
        logger.exception("room=%d _init_host_server() failed:", self._room_id)
        return False
    return True


def _patched_parse_danmaku_server_conf(self: BLiveClient, data: dict) -> bool:
    """Parse response from room/v1/Danmu/getConf (host_server_list field)."""
    self._host_server_list = data.get("host_server_list") or data.get("host_list") or []
    self._host_server_token = data.get("token", "")
    if not self._host_server_list:
        logger.warning(
            "room=%d _parse_danmaku_server_conf() failed: host_server_list is empty",
            self._room_id,
        )
        return False
    return True


# Apply monkey-patches to BLiveClient
BLiveClient._init_room_id_and_owner = _patched_init_room_id_and_owner
BLiveClient._parse_room_init = _patched_parse_room_init
BLiveClient._init_host_server = _patched_init_host_server
BLiveClient._parse_danmaku_server_conf = _patched_parse_danmaku_server_conf


# ---------------------------------------------------------------------------
# Register handlers for additional B站 commands so they show readable content
# instead of spamming "unknown cmd" in the console.
# ---------------------------------------------------------------------------

def _liked_callback(self: BaseHandler, client: BLiveClient, command: dict) -> None:
    """Forward LIKE_INFO_V3_CLICK to _on_like handler."""
    data = command.get("data", {})
    return self._on_like(client, data.get("uname", ""), data.get("like_text", ""))


def _watched_callback(self: BaseHandler, client: BLiveClient, command: dict) -> None:
    """Forward WATCHED_CHANGE to _on_watched handler."""
    data = command.get("data", {})
    return self._on_watched(client, data.get("text_large", ""))


def _notice_callback(self: BaseHandler, client: BLiveClient, command: dict) -> None:
    """Forward COMMON_NOTICE_DANMAKU to _on_notice handler."""
    data = command.get("data", {})
    segments = data.get("content_segments", [])
    texts = [s.get("text", "") for s in segments]
    return self._on_notice(client, "".join(texts))


# Register in BaseHandler's dispatch table
BaseHandler._CMD_CALLBACK_DICT["LIKE_INFO_V3_CLICK"] = _liked_callback
BaseHandler._CMD_CALLBACK_DICT["WATCHED_CHANGE"] = _watched_callback
BaseHandler._CMD_CALLBACK_DICT["COMMON_NOTICE_DANMAKU"] = _notice_callback

# Silently ignore noisy protobuf/statistical commands (no more "unknown cmd" spam)
_NOISY_CMDS = (
    "ONLINE_RANK_V3",
    "INTERACT_WORD_V2",
    "DM_INTERACTION",
    "LOG_IN_NOTICE",
    "LIKE_INFO_V3_UPDATE",
    "RANK_REM",
)
for _cmd_name in _NOISY_CMDS:
    BaseHandler._CMD_CALLBACK_DICT[_cmd_name] = None


class _BiliHandler(BaseHandler):
    """Internal handler for B站 danmaku and gift events."""

    def __init__(self, on_event: Callable[[DanmakuEvent], Awaitable[None]]) -> None:
        super().__init__()
        self._on_event = on_event

    async def _on_danmaku(self, client: BLiveClient, message) -> None:
        await self._on_event(DanmakuEvent(
            platform=Platform.BILIBILI,
            event_type=EventType.DANMAKU,
            user_name=message.uname or "unknown",
            content=message.msg or "",
            timestamp=time.time(),
        ))

    async def _on_gift(self, client: BLiveClient, message) -> None:
        # Only count paid gifts (gold coins), ignore free silver gifts
        is_paid = getattr(message, "coin_type", "gold") != "silver"
        price = message.price or 0
        if not is_paid:
            price = 0
        await self._on_event(DanmakuEvent(
            platform=Platform.BILIBILI,
            event_type=EventType.GIFT,
            user_name=message.uname or "unknown",
            gift_name=message.gift_name or "",
            gift_count=message.num or 1,
            gift_price=price * (message.num or 1),
            timestamp=time.time(),
        ))

    # -- Additional event handlers (registered via monkey-patches above) ----

    async def _on_like(self, _client: BLiveClient, uname: str, like_text: str) -> None:
        if uname:
            logger.info(f"❤ [{uname}] {like_text}")

    async def _on_watched(self, _client: BLiveClient, text: str) -> None:
        if text:
            logger.debug(f"👁 {text}")

    async def _on_notice(self, _client: BLiveClient, text: str) -> None:
        if text:
            logger.info(f"📢 系统: {text}")


class BilibiliListener:
    """Listens to B站 live danmaku and gift events."""

    def __init__(
        self,
        room_id: int,
        on_event: Callable[[DanmakuEvent], Awaitable[None]],
        sessdata: str = "",
        bili_jct: str = "",
        buvid3: str = "",
    ) -> None:
        self._room_id = room_id
        self._on_event = on_event
        self._sessdata = sessdata
        self._bili_jct = bili_jct
        self._buvid3 = buvid3
        self._client: Optional[BLiveClient] = None
        self._own_session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._connected = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def start(self) -> None:
        self._running = True

        # URL-decode cookies (user may paste URL-encoded values from browser)
        from urllib.parse import unquote
        sessdata = unquote(self._sessdata) if self._sessdata else ""
        bili_jct = unquote(self._bili_jct) if self._bili_jct else ""
        buvid3 = unquote(self._buvid3) if self._buvid3 else ""

        cookies: dict[str, str] = {}
        uid = 0
        if sessdata:
            cookies["SESSDATA"] = sessdata
        if bili_jct:
            cookies["bili_jct"] = bili_jct
        if buvid3:
            cookies["buvid3"] = buvid3

        if cookies:
            # aiohttp's "cookies=" param re-encodes values and breaks B站 auth.
            # Use raw Cookie header instead — same as what the browser sends.
            cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())

            self._own_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Cookie": cookie_header},
            )
            # Also inject the cookie header into the monkey-patched API calls
            # by storing it for the patched functions to use.
            self._cookie_header = cookie_header

            # Fetch real UID from B站 nav API
            try:
                async with self._own_session.get(
                    "https://api.bilibili.com/x/web-interface/nav",
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Referer": "https://www.bilibili.com/",
                    },
                    ssl=True,
                ) as nav_res:
                    if nav_res.status == 200:
                        nav_data = await nav_res.json()
                        if nav_data.get("code") == 0 and nav_data["data"].get("isLogin"):
                            uid = nav_data["data"].get("mid", 0)
                        else:
                            logger.warning(
                                "B站 nav API: isLogin=%s, code=%s",
                                nav_data.get("data", {}).get("isLogin"),
                                nav_data.get("code"),
                            )
            except Exception as e:
                logger.warning(f"B站 nav API call failed: {e}")

            self._client = BLiveClient(self._room_id, uid=uid, session=self._own_session)
            logger.info(f"B站 connecting with login (uid={uid})")
        else:
            self._client = BLiveClient(self._room_id)
            self._cookie_header = ""
            logger.info("B站 connecting as guest (no cookies, usernames will be masked)")
        handler = _BiliHandler(self._on_event)
        self._client.add_handler(handler)

        # Wrap original methods instead of replacing, so auth/heartbeat still work
        _orig_ws_connect = self._client._on_ws_connect
        _orig_ws_close = self._client._on_ws_close

        async def on_open():
            await _orig_ws_connect()
            self._connected = True
            logger.info(f"B站 connected to room {self._room_id}")

        async def on_close():
            await _orig_ws_close()
            self._connected = False
            logger.warning("B站 disconnected")

        self._client._on_ws_connect = on_open
        self._client._on_ws_close = on_close

        try:
            # BLiveClient.start() is synchronous, not async — do NOT await it
            self._client.start()
        except Exception as e:
            logger.error(f"B站 connection failed: {e}")
            self._connected = False

    async def stop(self) -> None:
        self._running = False
        if self._client:
            try:
                await self._client.stop_and_close()
            except Exception:
                pass
        if self._own_session:
            await self._own_session.close()
            self._own_session = None
        self._connected = False
        logger.info("B站 listener stopped")
