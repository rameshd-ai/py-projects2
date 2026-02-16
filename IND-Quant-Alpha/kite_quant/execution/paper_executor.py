"""
PAPER executor: live market data, simulated balance. No broker calls.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from engine.zerodha_client import get_quote
from execution.trade_history_store import append_trade

logger = logging.getLogger(__name__)


def place_paper_trade(
    session: dict,
    symbol: str,
    side: str,
    qty: int,
    price: float | None = None,
    strategy_name: str = "",
    stop_loss: float | None = None,
    target: float | None = None,
) -> dict[str, Any]:
    """Simulate entry: use LTP as entry_price, store in session['current_trade']. No broker call.
    For NFO index options uses session tradingsymbol and exchange=NFO (same price source as LIVE)."""
    if (session.get("exchange") or "").upper() == "NFO" and session.get("tradingsymbol"):
        symbol = session["tradingsymbol"]
        exchange = "NFO"
    else:
        symbol = session.get("instrument") or symbol
        exchange = "NSE"
    quote = get_quote(symbol, exchange=exchange)
    entry_price = float(quote.get("last", 0)) or (price if price is not None else 0)
    if entry_price <= 0:
        return {"success": False, "error": "No LTP for paper entry"}
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    trade_id = f"tr_{now.strftime('%Y%m%d%H%M%S')}_{symbol}"
    session["current_trade_id"] = trade_id
    session["current_trade"] = {
        "trade_id": trade_id,
        "strategy_id": (session.get("recommendation") or {}).get("strategyId") or "",
        "strategy_name": strategy_name,
        "symbol": symbol,
        "exchange": exchange,
        "side": side,
        "qty": qty,
        "entry_price": entry_price,
        "entry_time": now.isoformat(),
        "exit_time": None,
        "exit_price": None,
        "pnl": None,
        "mode": "PAPER",
        "stop_loss": stop_loss,
        "target": target,
    }
    # Deduct capital used so Balance Left reflects available amount
    vb = session.get("virtual_balance")
    if vb is not None:
        capital_used = round(entry_price * qty, 2)
        session["virtual_balance"] = round(float(vb) - capital_used, 2)
    logger.info("PAPER ENTRY | %s | %s qty=%s @ %s", symbol, side, qty, entry_price)
    return {"success": True, "trade_id": trade_id, "entry_price": entry_price}


def exit_paper_trade(session: dict, exit_price: float | None = None) -> dict[str, Any]:
    """Simulate exit: compute P&L, update session['virtual_balance'], append to trade_history.
    For NFO trades uses trade['exchange'] so exit price = NFO option premium."""
    trade = session.get("current_trade")
    if not trade or not trade.get("symbol"):
        return {"success": False, "error": "No current trade"}
    trade_id = trade.get("trade_id")
    # If a previous exit partially completed, finalize session state idempotently.
    if trade.get("exit_time") and trade.get("exit_price") is not None and trade.get("pnl") is not None:
        if session.get("last_closed_trade_id") != trade_id:
            session["trades_taken_today"] = (session.get("trades_taken_today") or 0) + 1
            session["last_closed_trade_id"] = trade_id
        session["current_trade_id"] = None
        session["current_trade"] = None
        return {"success": True, "pnl": trade.get("pnl"), "exit_price": trade.get("exit_price")}
    symbol = trade["symbol"]
    exchange = trade.get("exchange") or "NSE"
    if exit_price is None:
        quote = get_quote(symbol, exchange=exchange)
        exit_price = float(quote.get("last", 0))
    entry_price = float(trade.get("entry_price", 0))
    qty = int(trade.get("qty", 0))
    side = (trade.get("side") or "BUY").upper()
    pnl = (exit_price - entry_price) * qty if side == "BUY" else (entry_price - exit_price) * qty
    pnl = round(pnl, 2)
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    trade["exit_time"] = now.isoformat()
    trade["exit_price"] = exit_price
    trade["pnl"] = pnl
    session["daily_pnl"] = (session.get("daily_pnl") or 0) + pnl
    # Add back exit proceeds (capital released + P&L = entry*qty + pnl, so vb + exit*qty gives initial + pnl)
    vb = session.get("virtual_balance")
    if vb is not None:
        session["virtual_balance"] = round(float(vb) + exit_price * qty, 2)
    record = {
        "session_id": session.get("sessionId"),
        "mode": "PAPER",
        "symbol": symbol,
        "strategy": trade.get("strategy_name"),
        "option_type": ((session.get("recommendation") or {}).get("optionType") or ("CE" if str(symbol).endswith("CE") else ("PE" if str(symbol).endswith("PE") else None))),
        "strike": (session.get("recommendation") or {}).get("strike"),
        "entry_time": trade.get("entry_time"),
        "exit_time": trade.get("exit_time"),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "qty": qty,
        "lot_size": int(session.get("lot_size") or 0) or None,
        "price_per_lot": round(entry_price * float(session.get("lot_size") or 0), 2) if (session.get("lot_size") or 0) else None,
        "capital_used": round(entry_price * qty, 2),
        "balance_left": session.get("virtual_balance"),
        "charges": 0.0,
        "pnl": pnl,
    }
    # Finalize in-memory state before history write to avoid duplicate exits on retries.
    session["current_trade_id"] = None
    session["current_trade"] = None
    if session.get("last_closed_trade_id") != trade_id:
        session["trades_taken_today"] = (session.get("trades_taken_today") or 0) + 1
        session["last_closed_trade_id"] = trade_id
    try:
        append_trade(record)
    except Exception:
        # Keep engine running even if history persistence fails.
        pass
    logger.info("TRADE CLOSED | %s | P&L: %s", symbol, pnl)
    return {"success": True, "pnl": pnl, "exit_price": exit_price}
