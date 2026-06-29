"""Config persistence — encrypted storage in the user's data directory."""
from __future__ import annotations
import base64
import copy
import hashlib
import os
import uuid
import yaml

from .constants import DEFAULT_CONFIG, USER_DATA_DIR, APP_NAME

# ---------------------------------------------------------------------------
# Encryption — simple XOR cipher keyed to this machine + user.
# Prevents casual viewing of cookies / API keys in the config file.
# ---------------------------------------------------------------------------

def _machine_key() -> bytes:
    """Derive a machine-specific key for config encryption."""
    seed = f"{uuid.getnode()}:{os.environ.get('USERNAME', '')}:{APP_NAME}"
    return hashlib.sha256(seed.encode()).digest()


def _encrypt(plaintext: str) -> str:
    key = _machine_key()
    data = plaintext.encode("utf-8")
    xored = bytes(d ^ key[i % len(key)] for i, d in enumerate(data))
    return base64.urlsafe_b64encode(xored).decode("ascii")


def _decrypt(ciphertext: str) -> str:
    key = _machine_key()
    data = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    xored = bytes(d ^ key[i % len(key)] for i, d in enumerate(data))
    return xored.decode("utf-8")


# ---------------------------------------------------------------------------
# Config path
# ---------------------------------------------------------------------------

# Old data dir (project was formerly named "Burger Relay")
_OLD_DATA_DIR = os.path.join(os.path.dirname(USER_DATA_DIR), "Burger Relay")

_CONFIG_PATH = os.path.join(USER_DATA_DIR, "config.dat")
_LEGACY_PATH = os.path.join(USER_DATA_DIR, "config.yaml")
_OLD_LEGACY_PATH = os.path.join(_OLD_DATA_DIR, "config.yaml")
_OLD_CONFIG_PATH = os.path.join(_OLD_DATA_DIR, "config.dat")
_OLD_CWD_PATH = "config.yaml"

_config_cache: dict | None = None


def _ensure_user_dir() -> None:
    os.makedirs(USER_DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------

def _migrate_old_data_dir() -> None:
    """Copy config from old 'Burger Relay' data dir if it exists."""
    if not os.path.exists(_CONFIG_PATH) and not os.path.exists(_LEGACY_PATH):
        for old in (_OLD_CONFIG_PATH, _OLD_LEGACY_PATH):
            if os.path.exists(old):
                try:
                    import shutil
                    os.makedirs(USER_DATA_DIR, exist_ok=True)
                    shutil.copy2(old, _CONFIG_PATH if old.endswith(".dat") else _LEGACY_PATH)
                except Exception:
                    pass


def _migrate_legacy_configs() -> str | None:
    """Check for config files and return their content if found."""
    _migrate_old_data_dir()
    # Priority: encrypted dat > legacy yaml > old CWD yaml
    for path in (_CONFIG_PATH, _LEGACY_PATH, _OLD_LEGACY_PATH, _OLD_CONFIG_PATH, _OLD_CWD_PATH):
        if os.path.exists(path):
            try:
                if path.endswith(".dat"):
                    with open(path, "r", encoding="utf-8") as f:
                        return _decrypt(f.read())
                else:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
            except Exception:
                continue
    return None


def load_config(path: str | None = None) -> dict:
    """Load config from encrypted user storage. Falls back to legacy YAML."""
    global _config_cache

    _ensure_user_dir()

    config = copy.deepcopy(DEFAULT_CONFIG)
    raw = _migrate_legacy_configs()

    if raw:
        try:
            loaded = yaml.safe_load(raw)
            if loaded:
                for k, v in loaded.items():
                    if k in config and isinstance(config[k], dict) and isinstance(v, dict):
                        config[k].update(v)
                    else:
                        config[k] = v
        except Exception:
            pass

    _config_cache = config
    return config


def save_config(config: dict | None = None, path: str | None = None) -> None:
    """Encrypt and save config to user data directory."""
    global _config_cache

    if config is not None:
        _config_cache = copy.deepcopy(config)

    if _config_cache is None:
        return

    _ensure_user_dir()

    raw = yaml.safe_dump(_config_cache, allow_unicode=True, default_flow_style=False)
    encrypted = _encrypt(raw)

    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(encrypted)

    # Remove legacy unencrypted file if it exists
    if os.path.exists(_LEGACY_PATH):
        try:
            os.remove(_LEGACY_PATH)
        except Exception:
            pass


def get_config() -> dict:
    """Return a deep copy of the cached config."""
    global _config_cache
    if _config_cache is None:
        return load_config()
    return copy.deepcopy(_config_cache)
