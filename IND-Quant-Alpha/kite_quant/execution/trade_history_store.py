"""
Persist closed trades to data/trade_history.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from threading import RLock
from typing import Any

_BASE = Path(__file__).resolve().parent.parent
_DATA_DIR = _BASE / "data"
_HISTORY_FILE = _DATA_DIR / "trade_history.json"
_lock = RLock()


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _to_int(v: Any) -> int | None:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _infer_option_fields(symbol: Any) -> tuple[str | None, int | None]:
    s = str(symbol or "").upper()
    option_type = "CE" if s.endswith("CE") else ("PE" if s.endswith("PE") else None)
    m = re.search(r"(\d{4,6})(?:CE|PE)$", s)
    strike = int(m.group(1)) if m else None
    return option_type, strike


def _normalize_trade_record(trade: dict[str, Any]) -> dict[str, Any]:
    symbol = trade.get("symbol")
    entry_price = _to_float(trade.get("entry_price"))
    exit_price = _to_float(trade.get("exit_price"))
    qty = _to_int(trade.get("qty")) or 0
    lot_size = _to_int(trade.get("lot_size"))
    option_type = trade.get("option_type")
    strike = _to_int(trade.get("strike"))
    inferred_opt, inferred_strike = _infer_option_fields(symbol)
    if option_type is None:
        option_type = inferred_opt
    if strike is None:
        strike = inferred_strike
    if lot_size is None and qty > 0:
        lot_size = 25 if qty % 25 == 0 else (15 if qty % 15 == 0 else None)

    pnl = _to_float(trade.get("pnl"))
    charges = _to_float(trade.get("charges"))
    if charges is None:
        charges = 0.0
    net_pnl = _to_float(trade.get("net_pnl"))
    gross_pnl = _to_float(trade.get("gross_pnl"))

    # Normalize P&L fields:
    # - pnl is treated as net P&L in current executors.
    # - gross_pnl may be absent in older records.
    if net_pnl is None:
        net_pnl = pnl
    if gross_pnl is None and net_pnl is not None:
        gross_pnl = net_pnl + charges

    price_per_lot = _to_float(trade.get("price_per_lot"))
    if price_per_lot is None and entry_price is not None and lot_size:
        price_per_lot = round(entry_price * lot_size, 2)
    capital_used = _to_float(trade.get("capital_used"))
    if capital_used is None and entry_price is not None and qty:
        capital_used = round(entry_price * qty, 2)

    learning_label = "FLAT"
    if net_pnl is not None:
        if net_pnl > 0:
            learning_label = "WIN"
        elif net_pnl < 0:
            learning_label = "LOSS"

    setup_features = trade.get("setup_features")
    if not isinstance(setup_features, dict):
        setup_features = {}

    return {
        "session_id": trade.get("session_id"),
        "mode": trade.get("mode"),
        "symbol": symbol,
        "strategy": trade.get("strategy"),
        "option_type": option_type,
        "strike": strike,
        "entry_time": trade.get("entry_time"),
        "exit_time": trade.get("exit_time"),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "qty": qty,
        "lot_size": lot_size,
        "price_per_lot": price_per_lot,
        "capital_used": capital_used,
        "balance_left": _to_float(trade.get("balance_left")),
        "gross_pnl": gross_pnl,
        "charges": charges,
        "net_pnl": net_pnl,
        "pnl": net_pnl,
        "exit_reason": trade.get("exit_reason"),
        "setup_features": setup_features,
        "learning": {
            "label": learning_label,
            "net_after_charges": net_pnl,
        },
    }


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
            data["trades"].append(_normalize_trade_record(trade))
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
