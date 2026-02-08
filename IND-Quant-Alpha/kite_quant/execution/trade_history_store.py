"""
Persist closed trades to data/trade_history.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

_BASE = Path(__file__).resolve().parent.parent
_DATA_DIR = _BASE / "data"
_HISTORY_FILE = _DATA_DIR / "trade_history.json"
_lock = Lock()


def _load_all() -> list[dict[str, Any]]:
    if not _HISTORY_FILE.exists():
        return []
    with _lock:
        try:
            with open(_HISTORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("trades") if isinstance(data, dict) else (data if isinstance(data, list) else [])
        except Exception:
            return []


def append_trade(trade: dict[str, Any]) -> None:
    """Append one closed trade to history and persist."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        try:
            data = {"trades": _load_all()}
            if not isinstance(data["trades"], list):
                data["trades"] = []
            data["trades"].append(trade)
            data["updatedAt"] = __import__("datetime").datetime.now().isoformat()
            with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass


def get_trade_history(mode: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
    """Return all trades, optionally filtered by mode and/or session_id."""
    trades = _load_all()
    if mode:
        trades = [t for t in trades if t.get("mode") == mode]
    if session_id:
        trades = [t for t in trades if t.get("session_id") == session_id]
    return trades
