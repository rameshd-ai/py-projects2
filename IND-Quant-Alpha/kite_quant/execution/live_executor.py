"""
LIVE executor: real orders via Zerodha Kite.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from engine.zerodha_client import place_order as kite_place_order, get_quote
from execution.trade_history_store import append_trade

logger = logging.getLogger(__name__)


def place_live_order(
    session: dict,
    symbol: str,
    side: str,
    qty: int,
    price: float | None = None,
    strategy_name: str = "",
    stop_loss: float | None = None,
    target: float | None = None,
) -> dict[str, Any]:
    """Place real order via Zerodha. Uses session tradingsymbol/exchange for NFO index options."""
    exchange = session.get("exchange") or "NSE"
    tradingsymbol = session.get("tradingsymbol") or symbol
    result = kite_place_order(
        symbol=tradingsymbol,
        side=side,
        quantity=qty,
        order_type="LIMIT" if price is not None else "MARKET",
        price=price,
        exchange=exchange,
        tradingsymbol=tradingsymbol,
    )
    if not result.get("success"):
        logger.warning("LIVE order failed: %s", result.get("error", result))
        return result
    order_id = result.get("order_id")
    quote = get_quote(tradingsymbol, exchange=exchange)
    entry_price = float(quote.get("last", 0) or quote.get("last_price", 0)) or (price if price is not None else 0)
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    trade_id = f"tr_{now.strftime('%Y%m%d%H%M%S')}_{symbol}"
    session["current_trade_id"] = trade_id
    session["current_trade"] = {
        "trade_id": trade_id,
        "order_id": order_id,
        "strategy_id": (session.get("recommendation") or {}).get("strategyId") or "",
        "strategy_name": strategy_name,
        "symbol": tradingsymbol,
        "exchange": exchange,
        "side": side,
        "qty": qty,
        "entry_price": entry_price,
        "entry_time": now.isoformat(),
        "exit_time": None,
        "exit_price": None,
        "pnl": None,
        "mode": "LIVE",
        "stop_loss": stop_loss,
        "target": target,
    }
    logger.info("LIVE ENTRY | %s | %s %s qty=%s @ ~%s", symbol, side, strategy_name, qty, entry_price)
    return result


def exit_live_trade(session: dict, exit_price: float | None = None) -> dict[str, Any]:
    """Square off current trade via Zerodha. Uses session exchange/tradingsymbol for NFO."""
    trade = session.get("current_trade")
    if not trade or not trade.get("symbol"):
        return {"success": False, "error": "No current trade"}
    symbol = trade["symbol"]
    exchange = trade.get("exchange") or session.get("exchange") or "NSE"
    side = trade.get("side", "BUY")
    qty = int(trade.get("qty", 0))
    entry_price = float(trade.get("entry_price", 0))
    close_side = "SELL" if side.upper() == "BUY" else "BUY"
    if exit_price is None:
        quote = get_quote(symbol, exchange=exchange)
        exit_price = float(quote.get("last", 0) or quote.get("last_price", 0))
    result = kite_place_order(symbol=symbol, side=close_side, quantity=qty, exchange=exchange, tradingsymbol=symbol)
    if not result.get("success"):
        logger.warning("LIVE exit failed: %s", result.get("error", result))
        return result
    pnl = (exit_price - entry_price) * qty if side.upper() == "BUY" else (entry_price - exit_price) * qty
    pnl = round(pnl, 2)
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    trade["exit_time"] = now.isoformat()
    trade["exit_price"] = exit_price
    trade["pnl"] = pnl
    session["daily_pnl"] = (session.get("daily_pnl") or 0) + pnl
    record = {
        "session_id": session.get("sessionId"),
        "mode": "LIVE",
        "symbol": symbol,
        "strategy": trade.get("strategy_name"),
        "entry_time": trade.get("entry_time"),
        "exit_time": trade["exit_time"],
        "entry_price": entry_price,
        "exit_price": exit_price,
        "qty": qty,
        "pnl": pnl,
    }
    append_trade(record)
    session["current_trade_id"] = None
    session["current_trade"] = None
    session["trades_taken_today"] = (session.get("trades_taken_today") or 0) + 1
    logger.info("TRADE CLOSED | %s | P&L: %s", symbol, pnl)
    return {**result, "pnl": pnl, "exit_price": exit_price}
