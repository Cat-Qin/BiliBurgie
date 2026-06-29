"""Central event processor: connects listeners -> parser -> IRC."""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal

from .irc_server import IRCServer
from .command_parser import CommandParser
from ..utils.models import DanmakuEvent, AppStats, EventType, Platform
from ..auth.gift_whitelist import GiftWhitelist
from ..utils.config_loader import get_config

logger = logging.getLogger("BurgerRelay.processor")

class EventProcessor(QObject):
    """Central hub connecting listeners, parser, and IRC server."""
    stats_updated = pyqtSignal(object)
    whitelist_updated = pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()
        config = get_config()
        self.irc = IRCServer(config["server"]["host"], config["server"]["port"])
        self.whitelist = GiftWhitelist(config["auth"]["gift_expire_minutes"])
        self.parser = CommandParser(self.whitelist)
        self.stats = AppStats(start_time=time.time())
        self._require_gift = config["auth"]["require_gift"]
        self._cleanup_task: Optional[asyncio.Task] = None

    def configure(self) -> None:
        config = get_config()
        self._require_gift = config["auth"]["require_gift"]
        self._min_gift_price = config["auth"].get("min_gift_price", 0)
        self._allowed_gifts = [g.strip().lower() for g in
                               config["auth"].get("allowed_gift_names", "").split(",")
                               if g.strip()]
        self.whitelist.set_expire_minutes(config["auth"]["gift_expire_minutes"])
        llm = config["llm"]
        if llm.get("enabled", False):
            from ..llm.llm_factory import create_llm_client
            client = create_llm_client(
                llm["provider"], llm["model"], llm["api_base"],
                llm.get("api_key", ""), llm.get("temperature", 0.1),
                llm.get("timeout", 5.0), llm.get("max_tokens", 300),
            )
            self.parser.set_llm(client)
        else:
            self.parser.set_llm(None)

    async def start(self) -> None:
        self.configure()
        await self.irc.start()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
        await self.irc.stop()

    async def handle_event(self, event: DanmakuEvent) -> None:
        if event.is_gift:
            self.stats.total_gifts += 1
            # Filter: check minimum price
            if self._min_gift_price > 0 and event.gift_price < self._min_gift_price:
                logger.info(
                    f"GIFT (跳过-金额不足): [{event.user_name}] "
                    f"{event.gift_count}x {event.gift_name} ({event.gift_price}瓜子 < {self._min_gift_price})"
                )
                return
            # Filter: check allowed gift names (if list is non-empty)
            if self._allowed_gifts and event.gift_name.lower() not in self._allowed_gifts:
                logger.info(
                    f"GIFT (跳过-未在列表): [{event.user_name}] "
                    f"{event.gift_count}x {event.gift_name}"
                )
                return
            self.whitelist.add_user(event.user_name, event.platform, event.gift_name)
            user = self.stats.get_or_create_user(event.user_name)
            user.gift_count += 1
            user.last_active = time.time()
            self.whitelist_updated.emit(self.whitelist.get_active_entries())
            logger.info(
                f"GIFT ✅: [{event.user_name}] {event.gift_count}x "
                f"{event.gift_name} ({event.gift_price}瓜子) → 已加入白名单"
            )
            return

        self.stats.total_danmaku += 1
        user = self.stats.get_or_create_user(event.user_name)
        user.danmaku_count += 1
        user.last_active = time.time()
        logger.info(f"DANMAKU: [{event.user_name}] {event.content}")

        result = await self.parser.parse(event.content, event.user_name, self._require_gift)
        if result.is_valid:
            await self.irc.send_message(event.user_name, result.command)
            if result.command_type.value == "order":
                self.stats.total_orders += 1
                user.order_count += 1
                logger.info(f"ORDER: [{event.user_name}] -> {result.command}")
            elif result.command_type.value == "complaint":
                self.stats.total_complaints += 1
                logger.info(f"COMPLAINT: [{event.user_name}] -> {result.command}")
            elif result.command_type.value == "interact":
                self.stats.total_interacts += 1
                logger.info(f"INTERACT: [{event.user_name}] -> {result.command}")

        if result.source == "llm":
            self.stats.llm_calls += 1
            if result.error:
                self.stats.llm_failures += 1

        self.stats_updated.emit(self.stats)

    async def _cleanup_loop(self) -> None:
        from ..utils.constants import WHITELIST_CLEANUP_INTERVAL
        while True:
            await asyncio.sleep(WHITELIST_CLEANUP_INTERVAL)
            count = self.whitelist.cleanup_expired()
            if count > 0:
                logger.debug(f"Cleaned {count} expired whitelist entries")
                self.whitelist_updated.emit(self.whitelist.get_active_entries())
