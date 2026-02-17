"""
PAPER executor: live market data, simulated balance. No broker calls.
"""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from engine.risk_engine import evaluate_post_exit
from engine.zerodha_client import get_quote
from execution.trade_history_store import append_trade

logger = logging.getLogger(__name__)
MAX_LOSS_PER_TRADE = 300.0
MAX_SIM_LATENCY_SEC = 1.0
BASE_SLIPPAGE_BPS = 3.0
PARTIAL_FILL_PROB_LIMIT = 0.35


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
    """Simulate entry with latency, slippage, and partial fills for limit orders.

    Interface matches live executor signature.
    """
    if (session.get("exchange") or "").upper() == "NFO" and session.get("tradingsymbol"):
        symbol = session["tradingsymbol"]
        exchange = "NFO"
    else:
        symbol = session.get("instrument") or symbol
        exchange = "NSE"

    _simulate_latency()
    quote = get_quote(symbol, exchange=exchange)
    ltp = float(quote.get("last", 0) or quote.get("last_price", 0))
    if ltp <= 0 and price is not None:
        ltp = float(price)
    if ltp <= 0:
        return {"success": False, "error": "No LTP for paper entry"}

    volatility_pct = _estimate_volatility_pct(quote)
    spread_pct = _estimate_spread_pct(quote)
    limit_order = price is not None
    limit_price = float(price) if price is not None else None
    requested_qty = int(qty)
    if requested_qty <= 0:
        return {"success": False, "error": "Invalid quantity"}

    lot_size = int(
        session.get("lot_size")
        or (session.get("recommendation") or {}).get("lot_size")
        or (session.get("recommendation") or {}).get("lotSize")
        or 1
    )
    if lot_size <= 0:
        lot_size = 1
    if exchange == "NFO" and (requested_qty % lot_size != 0):
        return {
            "success": False,
            "error": f"Invalid quantity {requested_qty}: must be multiple of lot size {lot_size}",
            "state": "REJECTED",
        }
    fill_qty = requested_qty

    # Limit order simulator: may be partial fill or no fill.
    if limit_order and limit_price is not None:
        market_buy_price = _apply_slippage(ltp, side="BUY", spread_pct=spread_pct, volatility_pct=volatility_pct)
        if market_buy_price > limit_price:
            return {
                "success": False,
                "error": f"Limit not fillable at this tick (market={market_buy_price:.2f} > limit={limit_price:.2f})",
                "state": "CANCELLED",
            }
        requested_lots = max(1, requested_qty // lot_size) if exchange == "NFO" else requested_qty
        # For NFO paper mode, avoid random partial fills so deployed capital matches sizing
        # (closer to live behavior expected by this project).
        allow_partial_fill = exchange != "NFO"
        if allow_partial_fill and random.random() < PARTIAL_FILL_PROB_LIMIT and requested_lots > 1:
            fill_ratio = random.uniform(0.4, 0.9)
            if exchange == "NFO":
                partial_lots = max(1, int(requested_lots * fill_ratio))
                partial_lots = min(partial_lots, requested_lots - 1)
                fill_qty = partial_lots * lot_size
            else:
                fill_qty = max(1, int(requested_qty * fill_ratio))
            logger.info(
                "PAPER ENTRY | Partial fill simulated | requested=%s filled=%s ratio=%.2f",
                requested_qty,
                fill_qty,
                fill_ratio,
            )
        entry_price = min(limit_price, market_buy_price)
        order_type = "LIMIT"
    else:
        entry_price = _apply_slippage(ltp, side="BUY", spread_pct=spread_pct, volatility_pct=volatility_pct)
        order_type = "MARKET"

    if entry_price <= 0:
        return {"success": False, "error": "Invalid simulated entry price"}

    entry_turnover = entry_price * fill_qty
    entry_charges = _estimate_charges(turnover=entry_turnover, side="BUY")

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    order_id = f"paper_ord_{now.strftime('%Y%m%d%H%M%S')}_{symbol}"
    trade_id = f"tr_{now.strftime('%Y%m%d%H%M%S')}_{symbol}"
    session["current_trade_id"] = trade_id
    session["current_trade"] = {
        "trade_id": trade_id,
        "order_id": order_id,
        "strategy_id": (session.get("recommendation") or {}).get("strategyId") or "",
        "strategy_name": strategy_name,
        "symbol": symbol,
        "exchange": exchange,
        "side": side,
        "qty": fill_qty,
        "requested_qty": requested_qty,
        "order_type": order_type,
        "entry_price": entry_price,
        "entry_time": now.isoformat(),
        "exit_time": None,
        "exit_price": None,
        "pnl": None,
        "mode": "PAPER",
        "stop_loss": stop_loss,
        "target": target,
        "entry_charges": entry_charges,
        "entry_slippage_bps": round(((entry_price - ltp) / ltp) * 10000, 2) if ltp else 0.0,
    }
    # Deduct capital used so Balance Left reflects available amount
    vb = session.get("virtual_balance")
    if vb is not None:
        capital_used = round(entry_price * fill_qty, 2)
        session["virtual_balance"] = round(float(vb) - capital_used - entry_charges, 2)
    logger.info(
        "PAPER ENTRY | %s | %s %s qty=%s/%s @ %.2f | ltp=%.2f | slip=%.2fbps | charges=%.2f",
        symbol,
        side,
        order_type,
        fill_qty,
        requested_qty,
        entry_price,
        ltp,
        session["current_trade"]["entry_slippage_bps"],
        entry_charges,
    )
    return {
        "success": True,
        "order_id": order_id,
        "trade_id": trade_id,
        "entry_price": entry_price,
        "avg_fill_price": entry_price,
        "filled_qty": fill_qty,
        "state": "FILLED" if fill_qty == requested_qty else "PARTIAL_FILLED",
    }


def exit_paper_trade(session: dict, exit_price: float | None = None) -> dict[str, Any]:
    """Simulate exit: compute P&L, update session['virtual_balance'], append to trade_history.
    For NFO trades uses trade['exchange'] so exit price = NFO option premium."""
    trade = session.get("current_trade")
    if not trade or not trade.get("symbol"):
        return {"success": False, "error": "No current trade"}
    trade_id = trade.get("trade_id")
    # If a previous exit partially completed, finalize session state idempotently.
    if trade.get("exit_time") and trade.get("exit_price") is not None and trade.get("pnl") is not None:
        session["current_trade_id"] = None
        session["current_trade"] = None
        return {"success": True, "pnl": trade.get("pnl"), "exit_price": trade.get("exit_price")}
    symbol = trade["symbol"]
    exchange = trade.get("exchange") or "NSE"
    _simulate_latency()
    quote = get_quote(symbol, exchange=exchange)
    ltp = float(quote.get("last", 0) or quote.get("last_price", 0))
    if exit_price is None:
        exit_price = ltp
    entry_price = float(trade.get("entry_price", 0))
    qty = int(trade.get("qty", 0))
    side = (trade.get("side") or "BUY").upper()
    volatility_pct = _estimate_volatility_pct(quote)
    spread_pct = _estimate_spread_pct(quote)
    fill_side = "SELL" if side == "BUY" else "BUY"
    # Simulate market exit fill with slippage around latest price.
    exit_fill = _apply_slippage(float(exit_price), side=fill_side, spread_pct=spread_pct, volatility_pct=volatility_pct)
    pnl = (exit_fill - entry_price) * qty if side == "BUY" else (entry_price - exit_fill) * qty
    gross_pnl = round(pnl, 2)

    # Hard cap simulated gross loss per trade to configured risk amount (max ₹300).
    # This keeps paper behavior aligned with your strict per-trade loss model.
    max_gross_loss = float(session.get("max_loss_per_trade") or session.get("risk_amount_per_trade") or MAX_LOSS_PER_TRADE)
    max_gross_loss = min(max(1.0, max_gross_loss), MAX_LOSS_PER_TRADE)
    if qty > 0 and gross_pnl < -max_gross_loss:
        capped_gross = -round(max_gross_loss, 2)
        if side == "BUY":
            exit_fill = round(entry_price + (capped_gross / qty), 2)
            gross_pnl = round((exit_fill - entry_price) * qty, 2)
        else:
            exit_fill = round(entry_price - (capped_gross / qty), 2)
            gross_pnl = round((entry_price - exit_fill) * qty, 2)
        logger.warning(
            "PAPER EXIT | Gross loss capped | symbol=%s requested_gross=%.2f capped_gross=%.2f qty=%s",
            symbol,
            pnl,
            gross_pnl,
            qty,
        )

    exit_turnover = exit_fill * qty
    exit_charges = _estimate_charges(turnover=exit_turnover, side="SELL")
    entry_charges = float(trade.get("entry_charges") or 0.0)
    total_charges = round(entry_charges + exit_charges, 2)
    raw_net_pnl = round(gross_pnl - total_charges, 2)

    risk_decision = evaluate_post_exit(session, trade_pnl=raw_net_pnl, trade_time=datetime.now(ZoneInfo("Asia/Kolkata")))
    session.update(risk_decision.updated_session_state)
    # Keep trade-level P&L as actual executed result.
    # Risk engine may keep a capped stream for policy accounting separately.
    net_pnl = raw_net_pnl
    risk_capped_pnl = raw_net_pnl
    hist = session.get("trade_history") or []
    if hist and isinstance(hist[-1], dict):
        try:
            risk_capped_pnl = float(
                hist[-1].get("capped_pnl", hist[-1].get("pnl", raw_net_pnl))
            )
        except Exception:
            risk_capped_pnl = raw_net_pnl
    if session.get("status") == "STOPPED" and not session.get("stoppedAt"):
        session["stoppedAt"] = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    trade["exit_time"] = now.isoformat()
    trade["exit_price"] = exit_fill
    trade["pnl"] = net_pnl
    trade["risk_capped_pnl"] = risk_capped_pnl
    trade["gross_pnl"] = gross_pnl
    trade["charges"] = total_charges
    # Add back exit proceeds (capital released + P&L = entry*qty + pnl, so vb + exit*qty gives initial + pnl)
    vb = session.get("virtual_balance")
    if vb is not None:
        session["virtual_balance"] = round(float(vb) + exit_fill * qty - exit_charges, 2)
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
        "exit_price": exit_fill,
        "qty": qty,
        "lot_size": int(session.get("lot_size") or 0) or None,
        "price_per_lot": round(entry_price * float(session.get("lot_size") or 0), 2) if (session.get("lot_size") or 0) else None,
        "capital_used": round(entry_price * qty, 2),
        "balance_left": session.get("virtual_balance"),
        "charges": total_charges,
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "pnl": net_pnl,
        "risk_capped_pnl": risk_capped_pnl,
        "exit_reason": trade.get("exit_reason"),
    }
    # Finalize in-memory state before history write to avoid duplicate exits on retries.
    session["current_trade_id"] = None
    session["current_trade"] = None
    if session.get("last_closed_trade_id") != trade_id:
        session["last_closed_trade_id"] = trade_id
    try:
        append_trade(record)
    except Exception:
        # Keep engine running even if history persistence fails.
        pass
    logger.info(
        "TRADE CLOSED | %s | gross=%.2f net=%.2f charges=%.2f exit=%.2f",
        symbol,
        gross_pnl,
        net_pnl,
        total_charges,
        exit_fill,
    )
    return {
        "success": True,
        "pnl": net_pnl,
        "gross_pnl": gross_pnl,
        "charges": total_charges,
        "exit_price": exit_fill,
        "state": "FILLED",
    }


def _simulate_latency() -> None:
    """Simulate execution latency (50ms to 1000ms)."""
    time.sleep(random.uniform(0.05, MAX_SIM_LATENCY_SEC))


def _estimate_volatility_pct(quote: dict[str, Any]) -> float:
    """Estimate short-term volatility from quote OHLC range."""
    high = float(quote.get("high", 0) or 0)
    low = float(quote.get("low", 0) or 0)
    last = float(quote.get("last", 0) or quote.get("last_price", 0) or 0)
    if last <= 0 or high <= 0 or low <= 0 or high < low:
        return 0.2
    return max(0.01, min(5.0, ((high - low) / last) * 100))


def _estimate_spread_pct(quote: dict[str, Any]) -> float:
    """Approximate spread % using liquidity imbalance and range proxy."""
    last = float(quote.get("last", 0) or quote.get("last_price", 0) or 0)
    if last <= 0:
        return 0.05
    high = float(quote.get("high", 0) or 0)
    low = float(quote.get("low", 0) or 0)
    base = ((high - low) / last) * 100 * 0.15 if high > 0 and low > 0 else 0.05
    bq = float(quote.get("buy_quantity", 0) or 0)
    sq = float(quote.get("sell_quantity", 0) or 0)
    liq = bq + sq
    imbalance_penalty = 0.0
    if liq > 0:
        imbalance = abs(bq - sq) / liq
        imbalance_penalty = imbalance * 0.08
    return max(0.02, min(0.6, base + imbalance_penalty))


def _apply_slippage(mid_price: float, side: str, spread_pct: float, volatility_pct: float) -> float:
    """Apply side-aware slippage from spread and volatility."""
    if mid_price <= 0:
        return mid_price
    slip_bps = BASE_SLIPPAGE_BPS
    slip_bps += spread_pct * 35.0
    slip_bps += volatility_pct * 10.0
    slip_bps *= random.uniform(0.8, 1.25)
    slip_pct = max(0.0, min(0.8, slip_bps / 10000.0 * 100.0))
    if side.upper() == "BUY":
        return round(mid_price * (1 + slip_pct / 100.0), 2)
    return round(mid_price * (1 - slip_pct / 100.0), 2)


def _estimate_charges(turnover: float, side: str) -> float:
    """Estimate brokerage and statutory charges for one leg.

    Approximation for options intraday:
    - Brokerage: 0.03% capped at ₹20/leg
    - Transaction charges, GST, SEBI
    - Stamp duty on BUY leg
    - STT on SELL leg
    """
    turnover = max(0.0, float(turnover))
    brokerage = min(20.0, turnover * 0.0003)
    txn = turnover * 0.00053
    sebi = turnover * 0.000001
    gst = 0.18 * (brokerage + txn)
    stamp = turnover * 0.00003 if side.upper() == "BUY" else 0.0
    stt = turnover * 0.0005 if side.upper() == "SELL" else 0.0
    return round(brokerage + txn + sebi + gst + stamp + stt, 2)
