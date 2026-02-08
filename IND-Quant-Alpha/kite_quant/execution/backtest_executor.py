"""
BACKTEST executor: historical candle simulation. Engine feeds candles; entries/exits use candle OHLC.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from execution.trade_history_store import append_trade

logger = logging.getLogger(__name__)


def simulate_entry(
    session: dict,
    symbol: str,
    side: str,
    qty: int,
    candle: dict[str, Any],
    strategy_name: str = "",
) -> dict[str, Any]:
    """Simulate entry on a candle (e.g. open or close). Uses candle['open'] or candle['close'] as entry_price."""
    entry_price = float(candle.get("close", 0) or candle.get("open", 0))
    if entry_price <= 0:
        return {"success": False, "error": "Invalid candle for entry"}
    ts = candle.get("date") or candle.get("timestamp") or datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    if isinstance(ts, (int, float)):
        try:
            ts = datetime.fromtimestamp(ts, tz=ZoneInfo("Asia/Kolkata")).isoformat()
        except Exception:
            ts = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    trade_id = f"bt_{ts[:19].replace(':', '').replace('-', '').replace('T', '')}_{symbol}"
    session["current_trade_id"] = trade_id
    session["current_trade"] = {
        "trade_id": trade_id,
        "strategy_id": (session.get("recommendation") or {}).get("strategyId") or "",
        "strategy_name": strategy_name,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "entry_price": entry_price,
        "entry_time": ts,
        "exit_time": None,
        "exit_price": None,
        "pnl": None,
        "mode": "BACKTEST",
        "entry_candle": candle,
    }
    logger.info("BACKTEST ENTRY | %s | %s qty=%s @ %s", symbol, side, qty, entry_price)
    return {"success": True, "trade_id": trade_id, "entry_price": entry_price}


def simulate_exit(session: dict, candle: dict[str, Any], exit_price: float | None = None) -> dict[str, Any]:
    """Simulate exit on a candle. Updates virtual_balance, appends to trade_history."""
    trade = session.get("current_trade")
    if not trade or not trade.get("symbol"):
        return {"success": False, "error": "No current trade"}
    symbol = trade["symbol"]
    entry_price = float(trade.get("entry_price", 0))
    qty = int(trade.get("qty", 0))
    side = (trade.get("side") or "BUY").upper()
    if exit_price is None:
        exit_price = float(candle.get("close", 0) or candle.get("open", 0))
    pnl = (exit_price - entry_price) * qty if side == "BUY" else (entry_price - exit_price) * qty
    pnl = round(pnl, 2)
    ts = candle.get("date") or candle.get("timestamp") or datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    if isinstance(ts, (int, float)):
        try:
            ts = datetime.fromtimestamp(ts, tz=ZoneInfo("Asia/Kolkata")).isoformat()
        except Exception:
            ts = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    trade["exit_time"] = ts
    trade["exit_price"] = exit_price
    trade["pnl"] = pnl
    session["daily_pnl"] = (session.get("daily_pnl") or 0) + pnl
    vb = session.get("virtual_balance")
    if vb is not None:
        session["virtual_balance"] = round(float(vb) + pnl, 2)
    record = {
        "session_id": session.get("sessionId"),
        "mode": "BACKTEST",
        "symbol": symbol,
        "strategy": trade.get("strategy_name"),
        "entry_time": trade.get("entry_time"),
        "exit_time": ts,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "qty": qty,
        "pnl": pnl,
    }
    append_trade(record)
    session["current_trade_id"] = None
    session["current_trade"] = None
    session["trades_taken_today"] = (session.get("trades_taken_today") or 0) + 1
    logger.info("TRADE CLOSED | %s | P&L: %s (backtest)", symbol, pnl)
    return {"success": True, "pnl": pnl, "exit_price": exit_price}
