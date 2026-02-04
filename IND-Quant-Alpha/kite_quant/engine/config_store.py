"""
Load/save API keys and app config from dashboard. Persists to config.json; applied to os.environ.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_KEYS = [
    "ZERODHA_API_KEY",
    "ZERODHA_API_SECRET",
    "ZERODHA_ACCESS_TOKEN",
    "NEWS_API_KEY",
    "FLASK_ENV",
    "FLASK_SECRET_KEY",
    "TZ",
    "AUTO_CLOSE_TIME",
    "MAX_TRADES_PER_DAY",
]

DEFAULTS = {
    "FLASK_ENV": "development",
    "TZ": "Asia/Kolkata",
    "AUTO_CLOSE_TIME": "14:30",
    "MAX_TRADES_PER_DAY": "3",
}


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config.json"


def load_config() -> dict[str, str]:
    """Read config.json; return dict of key -> value (no secrets in response for GET)."""
    path = _config_path()
    if not path.exists():
        return {k: os.getenv(k) or DEFAULTS.get(k, "") or "" for k in CONFIG_KEYS}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: (data.get(k) or os.getenv(k) or DEFAULTS.get(k, "") or "") for k in CONFIG_KEYS}
    except Exception:
        return {k: os.getenv(k) or DEFAULTS.get(k, "") or "" for k in CONFIG_KEYS}


def save_config(values: dict[str, str]) -> None:
    """Write config.json and apply to os.environ. Empty or masked values do not overwrite."""
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_config()
    for k in CONFIG_KEYS:
        if k not in values or values[k] is None:
            continue
        v = str(values[k]).strip()
        if not v or v.startswith("****") or v.startswith("••••"):
            continue
        data[k] = v
        os.environ[k] = v
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def apply_config_to_env() -> None:
    """Apply config.json to os.environ (call after load_dotenv)."""
    path = _config_path()
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if v is not None and str(v).strip():
                os.environ[k] = str(v).strip()
    except Exception:
        pass
