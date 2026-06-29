"""Project-wide constants and default configuration."""

DEFAULT_CONFIG = {
    "app": {"theme": "dark", "language": "zh-CN", "auto_start": False, "minimize_to_tray": True},
    "server": {"host": "127.0.0.1", "port": 6667},
    "bilibili": {"room_id": 0, "sessdata": "", "bili_jct": "", "buvid3": ""},
    "llm": {"enabled": True, "provider": "custom", "model": "",
            "api_base": "", "api_key": "",
            "timeout": 5.0, "temperature": 0.1, "max_tokens": 300},
    "system_prompt": "",
    "auth": {"require_gift": True, "gift_expire_minutes": 60,
             "min_gift_price": 0, "allowed_gift_names": "",
             "enable_whitelist_persist": False},
    "game": {"trigger_prefix": "!", "enable_complaints": True, "enable_skin": True,
             "enable_leave": True, "custom_mappings": []},
    "logging": {"level": "INFO", "file": "", "max_size_mb": 10, "backup_count": 3},
    "stats": {"enabled": True, "save_interval_seconds": 60},
}

import os as _os

APP_NAME = "Biliurgie"
APP_VERSION = "1.0.0"


def _get_user_data_dir() -> str:
    """Platform-specific user data directory for persistent config/data."""
    if _os.name == "nt":
        base = _os.environ.get("APPDATA", _os.path.expanduser("~"))
        return _os.path.join(base, APP_NAME)
    elif _os.sys.platform == "darwin":
        return _os.path.join(_os.path.expanduser("~"), "Library", "Application Support", APP_NAME)
    else:
        xdg = _os.environ.get("XDG_CONFIG_HOME", _os.path.join(_os.path.expanduser("~"), ".config"))
        return _os.path.join(xdg, APP_NAME)


USER_DATA_DIR = _get_user_data_dir()
"""Persistent user data directory (e.g. %APPDATA%/Burger Relay)"""

USER_CONFIG_PATH = _os.path.join(USER_DATA_DIR, "config.yaml")
"""Path to the user's config file within USER_DATA_DIR"""
RECONNECT_BASE_DELAY = 1.0
RECONNECT_MAX_DELAY = 60.0
IRC_MOTD = "Welcome to Biliurgie IRC Server!"
IRC_NICKNAME = "Biliurgie"
IRC_USERNAME = "Biliurgie"
IRC_REALNAME = "Biliurgie Bridge"
IRC_CHANNEL = "#burger"
WHITELIST_CLEANUP_INTERVAL = 60.0
STATS_SAVE_INTERVAL = 60.0
