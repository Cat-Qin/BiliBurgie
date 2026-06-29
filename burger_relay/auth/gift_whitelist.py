"""Gift whitelist / permission management."""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from typing import Optional
from ..utils.models import WhitelistEntry, Platform

logger = logging.getLogger("BurgerRelay.whitelist")

class GiftWhitelist:
    """Manages gift-based user whitelist."""

    def __init__(self, expire_minutes: int = 60) -> None:
        self._entries: dict[tuple[str, Platform], WhitelistEntry] = {}
        self._expire_seconds = expire_minutes * 60

    def set_expire_minutes(self, minutes: int) -> None:
        self._expire_seconds = minutes * 60

    def add_user(self, user_name: str, platform: Platform, gift_name: str = "") -> None:
        key = (user_name.lower(), platform)
        expires = time.time() + self._expire_seconds
        self._entries[key] = WhitelistEntry(
            user_name=user_name,
            platform=platform,
            expires_at=expires,
            gift_name=gift_name,
        )
        logger.info(f"Whitelist added: {user_name} ({platform.name}) expires in {self._expire_seconds // 60}m")

    def remove_user(self, user_name: str, platform: Optional[Platform] = None) -> None:
        if platform:
            self._entries.pop((user_name.lower(), platform), None)
        else:
            for p in Platform:
                self._entries.pop((user_name.lower(), p), None)

    def is_whitelisted(self, user_name: str) -> bool:
        now = time.time()
        for p in Platform:
            entry = self._entries.get((user_name.lower(), p))
            if entry and not entry.is_expired(now):
                return True
        return False

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [k for k, e in self._entries.items() if e.is_expired(now)]
        for k in expired:
            e = self._entries.pop(k)
            logger.debug(f"Whitelist expired: {e.user_name}")
        return len(expired)

    def get_active_entries(self) -> list[dict]:
        now = time.time()
        result = []
        for entry in self._entries.values():
            if not entry.is_expired(now):
                remaining = max(0, int((entry.expires_at - now) / 60))
                result.append({
                    "user_name": entry.user_name,
                    "platform": entry.platform.name,
                    "remaining_minutes": remaining,
                    "gift_name": entry.gift_name,
                })
        return result

    def get_user_count(self) -> int:
        now = time.time()
        return sum(1 for e in self._entries.values() if not e.is_expired(now))
