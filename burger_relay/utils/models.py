"""Shared data models used across the application."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

class Platform(Enum):
    BILIBILI = auto()
    DOUYIN = auto()

class EventType(Enum):
    DANMAKU = auto()
    GIFT = auto()

class CommandType(Enum):
    ORDER = "order"
    COMPLAINT = "complaint"
    INTERACT = "interact"
    IGNORE = "ignore"

@dataclass
class DanmakuEvent:
    platform: Platform
    event_type: EventType
    user_name: str
    content: str = ""
    user_id: str = ""
    gift_name: str = ""
    gift_count: int = 0
    gift_price: int = 0  # 金瓜子 (1000 = 1元)
    timestamp: float = 0.0

    @property
    def is_gift(self) -> bool:
        return self.event_type == EventType.GIFT

@dataclass
class CommandResult:
    command_type: CommandType
    command: str
    source: str
    raw_input: str = ""
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.command_type != CommandType.IGNORE

@dataclass
class WhitelistEntry:
    user_name: str
    platform: Platform
    expires_at: float
    gift_name: str = ""

    def is_expired(self, now: float) -> bool:
        return self.expires_at <= now

@dataclass
class UserStats:
    user_name: str
    danmaku_count: int = 0
    order_count: int = 0
    gift_count: int = 0
    last_active: float = 0.0

@dataclass
class AppStats:
    total_danmaku: int = 0
    total_orders: int = 0
    total_complaints: int = 0
    total_interacts: int = 0
    total_gifts: int = 0
    llm_calls: int = 0
    llm_total_time: float = 0.0
    llm_failures: int = 0
    start_time: float = 0.0
    users: dict = field(default_factory=dict)

    def get_or_create_user(self, user_name: str) -> UserStats:
        if user_name not in self.users:
            self.users[user_name] = UserStats(user_name=user_name)
        return self.users[user_name]

    @property
    def online_users(self) -> int:
        return len(self.users)
