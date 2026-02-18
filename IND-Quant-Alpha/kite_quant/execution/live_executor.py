"""
LIVE executor: real orders via Zerodha Kite.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from engine.order_state import OrderManager, OrderRequest, OrderState
from engine.risk_engine import evaluate_post_exit
from engine.zerodha_client import cancel_order as kite_cancel_order
from engine.zerodha_client import get_open_orders as kite_get_open_orders
from engine.zerodha_client import get_quote as kite_get_quote
from engine.zerodha_client import get_order_status as kite_get_order_status
from engine.zerodha_client import get_positions as kite_get_positions
from engine.zerodha_client import place_order as kite_place_order
from execution.trade_history_store import append_trade

logger = logging.getLogger(__name__)
MAX_LOSS_PER_TRADE = 300.0
ORDER_FILL_TIMEOUT_SEC = 15.0
ORDER_POLL_INTERVAL_SEC = 0.5
POST_CANCEL_RECONCILE_TIMEOUT_SEC = 12.0
POST_CANCEL_POLL_INTERVAL_SEC = 0.5
ENTRY_PARTIAL_FILL_POLICY = str(os.getenv("LIVE_ENTRY_PARTIAL_FILL_POLICY", "FORCE_EXIT")).strip().upper()
PARTIAL_FLATTEN_MAX_RETRIES = 3
STOP_CANCEL_RETRIES = 3
STOP_CANCEL_CONFIRM_TIMEOUT_SEC = 8.0
STOP_OPEN_ORDERS_POLL_TIMEOUT_SEC = 8.0
STOP_FAILURE_EXIT_RETRIES = 3
STOP_PLACEMENT_RETRIES = 3
STOP_PRICE_TICK_SIZE = 0.05
STOP_PRICE_BUFFER_TICKS = 4


class _ZerodhaBrokerAdapter:
    """Adapter to plug Zerodha helpers into OrderManager broker protocol."""

    def place_order(self, request: OrderRequest) -> dict[str, Any]:
        product = (request.metadata or {}).get("product")
        return kite_place_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price,
            exchange=request.exchange,
            tradingsymbol=request.symbol,
            product=product,
        )

    def get_order_status(self, broker_order_id: str) -> dict[str, Any]:
        data = kite_get_order_status(broker_order_id)
        if not data.get("success"):
            return {"status": "REJECTED", "reject_reason": data.get("error") or "Status lookup failed"}
        return data

    def cancel_order(self, broker_order_id: str) -> dict[str, Any]:
        return kite_cancel_order(broker_order_id)


_order_manager = OrderManager(_ZerodhaBrokerAdapter())


def _wait_for_terminal_fill(client_order_id: str, timeout_sec: float = ORDER_FILL_TIMEOUT_SEC) -> Any:
    """Poll order manager until terminal state or timeout."""
    deadline = time.time() + max(0.1, timeout_sec)
    order = _order_manager.get_order(client_order_id)
    while time.time() < deadline:
        order = _order_manager.poll_status(client_order_id)
        if order.state in (OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED):
            return order
        time.sleep(ORDER_POLL_INTERVAL_SEC)
    return order


def _sanitize_partial_policy() -> str:
    policy = ENTRY_PARTIAL_FILL_POLICY
    return policy if policy in {"ATTACH", "FORCE_EXIT"} else "FORCE_EXIT"


def _set_active_trade(
    session: dict,
    *,
    trade_id: str,
    order_id: str | None,
    strategy_name: str,
    symbol: str,
    exchange: str,
    side: str,
    qty: int,
    entry_price: float,
    stop_loss: float | None,
    target: float | None,
) -> None:
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    session["current_trade_id"] = trade_id
    session["current_trade"] = {
        "trade_id": trade_id,
        "order_id": order_id,
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
        "mode": "LIVE",
        "stop_loss": stop_loss,
        "target": target,
    }


def _force_close_partial_fill(symbol: str, exchange: str, side: str, qty: int) -> dict[str, Any]:
    """Emergency flatten partial exposure via market order and fill reconciliation."""
    if qty <= 0:
        return {"success": True, "closed_qty": 0, "state": "NO_EXPOSURE"}
    close_side = "SELL" if side.upper() == "BUY" else "BUY"
    request = OrderRequest(
        symbol=symbol,
        side=close_side,
        quantity=qty,
        order_type="MARKET",
        price=None,
        exchange=exchange,
    )
    managed = _order_manager.send_order(request)
    if managed.state == OrderState.REJECTED:
        return {"success": False, "error": managed.reject_reason or "Emergency close rejected", "state": managed.state.value}
    managed = _wait_for_terminal_fill(request.client_order_id, timeout_sec=ORDER_FILL_TIMEOUT_SEC)
    if managed.state == OrderState.FILLED and int(managed.filled_quantity or 0) == qty:
        return {"success": True, "closed_qty": qty, "state": managed.state.value, "order_id": managed.broker_order_id}
    try:
        _order_manager.cancel_order(request.client_order_id)
    except Exception:
        pass
    return {
        "success": False,
        "error": f"Emergency close not confirmed (state={managed.state.value})",
        "state": managed.state.value,
        "order_id": managed.broker_order_id,
        "closed_qty": int(managed.filled_quantity or 0),
    }


def _get_open_position_qty(symbol: str) -> int:
    """Best-effort broker position lookup to avoid returning while exposure may exist."""
    try:
        for p in kite_get_positions() or []:
            if str(p.get("symbol") or "").upper() == str(symbol or "").upper():
                return abs(int(p.get("quantity") or 0))
    except Exception:
        pass
    return 0


def _get_broker_position(symbol: str) -> dict[str, Any] | None:
    """Return the exact broker position row for symbol (if any)."""
    sym = str(symbol or "").upper()
    if not sym:
        return None
    try:
        for p in kite_get_positions() or []:
            if str(p.get("symbol") or "").upper() == sym:
                qty = int(p.get("quantity") or 0)
                if qty != 0:
                    return p
    except Exception:
        return None
    return None


def _trigger_emergency_lockdown(session: dict, reason: str, *, symbol: str, details: dict[str, Any] | None = None) -> None:
    """Set hard emergency lockdown flags for engine/session safety."""
    now = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    session["system_state"] = "EMERGENCY"
    session["status"] = "STOPPED"
    session["stop_reason"] = "EMERGENCY_LOCKDOWN"
    session["state"] = "EMERGENCY_LOCKDOWN"
    session["emergency_lockdown"] = True
    session["engine_lockdown_requested"] = True
    session["requires_emergency_remediation"] = True
    session["recovery_attempts"] = int(session.get("recovery_attempts") or 0) + 1
    session["recovery_last_error"] = reason
    session["recovery_last_at"] = now
    if not session.get("stoppedAt"):
        session["stoppedAt"] = now
    if session.get("current_trade"):
        session["current_trade"]["state"] = "EMERGENCY_LOCKDOWN"
        session["current_trade"]["emergency_reason"] = reason
        if details:
            session["current_trade"]["emergency_details"] = details
    logger.critical(
        "EMERGENCY LOCKDOWN | symbol=%s | reason=%s | details=%s",
        symbol,
        reason,
        details or {},
    )


def _set_system_normal(session: dict) -> None:
    """Normalize emergency/session flags when exposure is safely managed."""
    session["system_state"] = "NORMAL"
    session.pop("emergency_lockdown", None)
    session.pop("engine_lockdown_requested", None)
    session.pop("requires_emergency_remediation", None)


def _place_stop_with_retries(session: dict, qty: int, stop_loss: float | None, retries: int = STOP_PLACEMENT_RETRIES) -> dict[str, Any]:
    """Retry protective stop placement a fixed number of times."""
    last = {"success": False, "error": "unknown"}
    for attempt in range(1, max(1, retries) + 1):
        last = _place_protective_stop_order(session, qty, stop_loss)
        if last.get("success"):
            return last
        logger.error(
            "LIVE STOP PLACE retry failed | attempt=%s/%s | error=%s",
            attempt,
            retries,
            last.get("error"),
        )
        time.sleep(POST_CANCEL_POLL_INTERVAL_SEC)
    return last


def _resolve_entry_avg_fill_price(
    broker_order_id: str | None,
    symbol: str,
    exchange: str,
    managed_avg_fill: float | None,
) -> float:
    """
    Resolve entry avg fill price deterministically for partial/timeout paths.
    Priority:
      1) managed avg_fill_price
      2) broker order-history status average price
      3) LTP fallback (critical warning)
    """
    avg_fill = float(managed_avg_fill or 0.0)
    if avg_fill > 0:
        return avg_fill

    if broker_order_id:
        try:
            status = kite_get_order_status(str(broker_order_id))
            if status.get("success"):
                avg_fill = float(status.get("avg_fill_price") or 0.0)
                if avg_fill > 0:
                    return avg_fill
        except Exception:
            pass

    # Last fallback: LTP (should be very rare; keep critical log).
    ltp = 0.0
    try:
        q = kite_get_quote(symbol, exchange=exchange)
        ltp = float(q.get("last", 0) or q.get("last_price", 0) or 0.0)
    except Exception:
        ltp = 0.0
    if ltp > 0:
        logger.critical(
            "LIVE ENTRY RECON | avg fill unavailable after order history; using LTP fallback | symbol=%s | exchange=%s | ltp=%.2f | order_id=%s",
            symbol,
            exchange,
            ltp,
            broker_order_id,
        )
        return ltp
    logger.critical(
        "LIVE ENTRY RECON | avg fill unavailable and LTP fetch failed | symbol=%s | exchange=%s | order_id=%s",
        symbol,
        exchange,
        broker_order_id,
    )
    return 0.0


def _flatten_with_retries(symbol: str, exchange: str, side: str, qty: int, retries: int = PARTIAL_FLATTEN_MAX_RETRIES) -> dict[str, Any]:
    """Try emergency market flatten multiple times; confirm zero broker position."""
    last_error: str | None = None
    target_qty = max(0, int(qty))
    for attempt in range(1, max(1, retries) + 1):
        open_qty = _get_open_position_qty(symbol)
        close_qty = open_qty if open_qty > 0 else target_qty
        if close_qty <= 0:
            return {"success": True, "state": "ZERO_POSITION_CONFIRMED", "attempts": attempt - 1}
        res = _force_close_partial_fill(symbol, exchange, side, close_qty)
        if res.get("success"):
            if _get_open_position_qty(symbol) <= 0:
                return {"success": True, "state": "FLATTENED", "attempts": attempt, "details": res}
        last_error = str(res.get("error") or "Flatten attempt failed")
        time.sleep(POST_CANCEL_POLL_INTERVAL_SEC)

    # Final confirmation after retries.
    if _get_open_position_qty(symbol) <= 0:
        return {"success": True, "state": "ZERO_POSITION_CONFIRMED_AFTER_RETRIES", "attempts": retries, "error": last_error}
    return {"success": False, "state": "POSITION_STILL_OPEN", "attempts": retries, "error": last_error}


def _is_stop_order_cleared(status: str) -> bool:
    s = str(status or "").upper()
    return s in {"CANCELLED", "CANCELED", "REJECTED"}


def _is_stop_order_open(stop_order_id: str) -> tuple[bool, str | None]:
    """Check if stop order is still present in broker open-orders list."""
    try:
        open_orders = kite_get_open_orders() or []
    except Exception:
        open_orders = []
    stop_id = str(stop_order_id or "").strip()
    if not stop_id:
        return False, None
    for o in open_orders:
        oid = str(o.get("order_id") or "").strip()
        if oid == stop_id:
            return True, str(o.get("status") or "").upper()
    return False, None


def _cancel_and_confirm_stop_order(session: dict, trade: dict) -> dict[str, Any]:
    """
    Cancel protective stop order and confirm terminal cancel state.

    Returns:
      {"success": bool, "cancelled": bool, "status": str|None, "error": str|None}
    """
    stop_order_id = str(trade.get("stop_order_id") or session.get("stop_order_id") or "").strip()
    if not stop_order_id:
        return {"success": True, "cancelled": True, "status": None}

    last_error: str | None = None
    for attempt in range(1, STOP_CANCEL_RETRIES + 1):
        cancel_res = kite_cancel_order(stop_order_id)
        if not cancel_res.get("success"):
            last_error = str(cancel_res.get("error") or "Stop cancel request failed")
            logger.warning(
                "LIVE EXIT | stop cancel attempt failed | stop_order_id=%s | attempt=%s/%s | err=%s",
                stop_order_id,
                attempt,
                STOP_CANCEL_RETRIES,
                last_error,
            )
        deadline = time.time() + STOP_OPEN_ORDERS_POLL_TIMEOUT_SEC
        while time.time() < deadline:
            is_open, open_status = _is_stop_order_open(stop_order_id)
            if not is_open:
                # Optional terminal status fetch for audit logging.
                status_res = kite_get_order_status(stop_order_id)
                final_status = str(status_res.get("status") or "").upper() if status_res.get("success") else "NOT_PRESENT_IN_OPEN_ORDERS"
                trade["stop_order_status"] = final_status
                session["stop_order_status"] = final_status
                return {"success": True, "cancelled": True, "status": final_status}
            if _is_stop_order_cleared(str(open_status or "")):
                trade["stop_order_status"] = str(open_status or "").upper()
                session["stop_order_status"] = str(open_status or "").upper()
                return {"success": True, "cancelled": True, "status": str(open_status or "").upper()}
            time.sleep(POST_CANCEL_POLL_INTERVAL_SEC)

    return {
        "success": False,
        "cancelled": False,
        "status": str(trade.get("stop_order_status") or session.get("stop_order_status") or ""),
        "error": last_error or "Stop cancellation not confirmed",
    }


def _finalize_live_exit(
    session: dict,
    trade: dict,
    actual_exit_price: float,
    filled_qty: int,
    exit_reason: str,
) -> dict[str, Any]:
    """Finalize in-memory/session state and persist trade history for a closed LIVE trade."""
    symbol = trade.get("symbol") or session.get("tradingsymbol") or session.get("instrument")
    side = (trade.get("side") or "BUY").upper()
    entry_price = float(trade.get("entry_price", 0) or 0)
    # PnL must always be calculated from broker actual fill.
    actual_pnl = (actual_exit_price - entry_price) * filled_qty if side == "BUY" else (entry_price - actual_exit_price) * filled_qty
    actual_pnl = round(actual_pnl, 2)
    risk_decision = evaluate_post_exit(session, trade_pnl=actual_pnl, trade_time=datetime.now(ZoneInfo("Asia/Kolkata")))
    session.update(risk_decision.updated_session_state)
    risk_adjusted_pnl = actual_pnl
    hist = session.get("trade_history") or []
    if hist and isinstance(hist[-1], dict):
        try:
            risk_adjusted_pnl = float(hist[-1].get("pnl", actual_pnl))
        except Exception:
            risk_adjusted_pnl = actual_pnl
    risk_adjusted_exit_price = actual_exit_price
    if filled_qty > 0 and abs(risk_adjusted_pnl - actual_pnl) > 1e-9:
        if side == "BUY":
            risk_adjusted_exit_price = round(entry_price + (risk_adjusted_pnl / filled_qty), 2)
        else:
            risk_adjusted_exit_price = round(entry_price - (risk_adjusted_pnl / filled_qty), 2)
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    trade["exit_time"] = now.isoformat()
    trade["actual_exit_price"] = actual_exit_price
    trade["risk_adjusted_exit_price"] = risk_adjusted_exit_price
    trade["exit_price"] = actual_exit_price  # Backward compatible key
    trade["pnl"] = actual_pnl
    trade["actual_pnl"] = actual_pnl
    trade["risk_adjusted_pnl"] = risk_adjusted_pnl
    trade["exit_reason"] = exit_reason
    record = {
        "session_id": session.get("sessionId"),
        "mode": "LIVE",
        "symbol": symbol,
        "strategy": trade.get("strategy_name"),
        "entry_time": trade.get("entry_time"),
        "exit_time": trade["exit_time"],
        "entry_price": entry_price,
        "exit_price": actual_exit_price,
        "actual_exit_price": actual_exit_price,
        "risk_adjusted_exit_price": risk_adjusted_exit_price,
        "qty": filled_qty,
        "pnl": actual_pnl,
        "actual_pnl": actual_pnl,
        "risk_adjusted_pnl": risk_adjusted_pnl,
        "exit_reason": exit_reason,
    }
    append_trade(record)
    session["current_trade_id"] = None
    session["current_trade"] = None
    if session.get("last_closed_trade_id") != trade.get("trade_id"):
        session["last_closed_trade_id"] = trade.get("trade_id")
    # Stop order is no longer relevant once trade is closed.
    session.pop("stop_order_id", None)
    session.pop("stop_order_status", None)
    if session.get("status") == "STOPPED" and not session.get("stoppedAt"):
        session["stoppedAt"] = now.isoformat()
    logger.info(
        "TRADE CLOSED | %s | qty=%s | actual_pnl=%s | risk_adjusted_pnl=%s | reason=%s",
        symbol,
        filled_qty,
        actual_pnl,
        risk_adjusted_pnl,
        exit_reason,
    )
    return {
        "success": True,
        "pnl": actual_pnl,
        "actual_pnl": actual_pnl,
        "risk_adjusted_pnl": risk_adjusted_pnl,
        "exit_price": actual_exit_price,
        "actual_exit_price": actual_exit_price,
        "risk_adjusted_exit_price": risk_adjusted_exit_price,
        "filled_qty": filled_qty,
        "state": "FILLED",
    }


def _place_protective_stop_order(session: dict, qty: int, stop_loss: float | None) -> dict[str, Any]:
    """Place broker-native protective stop order using SL (F&O-safe)."""
    trade = session.get("current_trade") or {}
    symbol = trade.get("symbol") or session.get("tradingsymbol") or session.get("instrument")
    exchange = trade.get("exchange") or session.get("exchange") or "NSE"
    side = (trade.get("side") or "BUY").upper()
    if not symbol or qty <= 0:
        return {"success": False, "error": "Invalid symbol/qty for protective stop"}
    if stop_loss is None or float(stop_loss) <= 0:
        return {"success": False, "error": "Invalid stop_loss for protective stop"}
    close_side = "SELL" if side == "BUY" else "BUY"
    raw_trigger = float(stop_loss)
    tick = float(STOP_PRICE_TICK_SIZE)
    buffer_amt = float(STOP_PRICE_BUFFER_TICKS) * tick

    # Zerodha F&O no longer accepts SL-M for many contracts.
    # Use SL with a small protective limit buffer around trigger.
    trigger_price = round(round(raw_trigger / tick) * tick, 2)
    if close_side == "SELL":
        limit_price = round(max(tick, trigger_price - buffer_amt), 2)
    else:
        limit_price = round(trigger_price + buffer_amt, 2)

    result = kite_place_order(
        symbol=symbol,
        side=close_side,
        quantity=qty,
        order_type="SL",
        price=limit_price,
        trigger_price=trigger_price,
        exchange=exchange,
        tradingsymbol=symbol,
    )
    if result.get("success"):
        stop_order_id = result.get("order_id")
        session["stop_order_id"] = stop_order_id
        session["stop_order_status"] = "OPEN"
        if session.get("current_trade"):
            session["current_trade"]["stop_order_id"] = stop_order_id
            session["current_trade"]["stop_order_status"] = "OPEN"
        logger.info(
            "LIVE PROTECTIVE STOP | placed | symbol=%s | qty=%s | trigger=%.2f | limit=%.2f | stop_order_id=%s",
            symbol,
            qty,
            trigger_price,
            limit_price,
            stop_order_id,
        )
    else:
        logger.error("LIVE PROTECTIVE STOP | placement failed | symbol=%s | error=%s", symbol, result.get("error"))
    return result


def monitor_protective_stop(session: dict) -> dict[str, Any]:
    """Monitor broker-native stop order status and finalize trade when stop is triggered.

    Returns:
      {"handled": bool, "closed": bool, "error": str|None}
    """
    trade = session.get("current_trade")
    if not trade:
        return {"handled": False, "closed": False}
    stop_order_id = trade.get("stop_order_id") or session.get("stop_order_id")
    if not stop_order_id:
        return {"handled": False, "closed": False}
    status_data = kite_get_order_status(str(stop_order_id))
    if not status_data.get("success"):
        logger.warning("LIVE STOP MONITOR | failed to fetch stop status | stop_order_id=%s", stop_order_id)
        return {"handled": False, "closed": False, "error": status_data.get("error")}
    status = str(status_data.get("status") or "").upper()
    session["stop_order_status"] = status
    trade["stop_order_status"] = status
    logger.info("LIVE STOP MONITOR | stop_order_id=%s | status=%s", stop_order_id, status)
    if status in ("COMPLETE", "FILLED"):
        filled_qty = int(status_data.get("filled_quantity") or trade.get("qty") or 0)
        exit_fill_price = float(status_data.get("avg_fill_price") or trade.get("stop_loss") or 0.0)
        if filled_qty > 0 and exit_fill_price > 0:
            _finalize_live_exit(session, trade, exit_fill_price, filled_qty, "STOP_LOSS")
            return {"handled": True, "closed": True}
    if status in ("REJECTED", "CANCELLED", "CANCELED"):
        # Protective stop invalidated while trade is still open; emergency close.
        logger.error("LIVE STOP MONITOR | stop invalidated (%s), forcing market exit", status)
        forced = exit_live_trade(session, exit_reason_override="STOP_ORDER_INVALIDATED")
        return {"handled": True, "closed": bool(forced.get("success")), "error": forced.get("error")}
    return {"handled": True, "closed": False}


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
    """Place real order via Zerodha and reconcile real fills (no quote-assumed entry)."""
    exchange = session.get("exchange") or "NSE"
    tradingsymbol = session.get("tradingsymbol") or symbol
    request = OrderRequest(
        symbol=tradingsymbol,
        side=side,
        quantity=qty,
        order_type="LIMIT" if price is not None else "MARKET",
        price=price,
        exchange=exchange,
    )
    managed = _order_manager.send_order(request)
    logger.info(
        "LIVE ENTRY FSM | client_order_id=%s | state=%s | broker_order_id=%s",
        request.client_order_id,
        managed.state.value,
        managed.broker_order_id,
    )
    if managed.state == OrderState.REJECTED:
        err = managed.reject_reason or "Entry order rejected"
        logger.warning("LIVE order failed: %s", err)
        return {"success": False, "error": err, "state": managed.state.value}

    managed = _wait_for_terminal_fill(request.client_order_id)
    logger.info(
        "LIVE ENTRY FSM | client_order_id=%s | terminal_state=%s | filled_qty=%s | avg_fill=%.2f",
        request.client_order_id,
        managed.state.value,
        managed.filled_quantity,
        float(managed.avg_fill_price or 0.0),
    )

    if managed.state == OrderState.FILLED:
        _set_system_normal(session)
        entry_price = _resolve_entry_avg_fill_price(
            managed.broker_order_id,
            tradingsymbol,
            exchange,
            float(managed.avg_fill_price or 0.0),
        )
        if entry_price <= 0:
            # Hard rule: FILLED qty implies no failure path; use safe placeholder to keep deterministic tracking.
            entry_price = float(price or 1.0)
            logger.critical(
                "LIVE ENTRY | FILLED but avg fill unresolved; using placeholder entry_price=%.2f | symbol=%s | order_id=%s",
                entry_price,
                tradingsymbol,
                managed.broker_order_id,
            )
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        trade_id = f"tr_{now.strftime('%Y%m%d%H%M%S')}_{symbol}"
        _set_active_trade(
            session,
            trade_id=trade_id,
            order_id=managed.broker_order_id,
            strategy_name=strategy_name,
            symbol=tradingsymbol,
            exchange=exchange,
            side=side,
            qty=int(managed.filled_quantity or 0),
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
        )
        stop_result = _place_stop_with_retries(session, int(managed.filled_quantity or 0), stop_loss, retries=STOP_PLACEMENT_RETRIES)
        if stop_result.get("success"):
            _set_system_normal(session)
            logger.info(
                "LIVE ENTRY | %s | %s %s qty=%s @ %.2f | order_id=%s | state=FILLED_PROTECTED",
                symbol,
                side,
                strategy_name,
                managed.filled_quantity,
                entry_price,
                managed.broker_order_id,
            )
            return {
                "success": True,
                "order_id": managed.broker_order_id,
                "filled_qty": managed.filled_quantity,
                "avg_fill_price": entry_price,
                "state": "FILLED_PROTECTED",
            }

        logger.error("LIVE ENTRY | Protective stop placement failed, forcing immediate flatten loop")
        flatten = _flatten_with_retries(
            tradingsymbol,
            exchange,
            side,
            int(managed.filled_quantity or 0),
            retries=STOP_FAILURE_EXIT_RETRIES,
        )
        if flatten.get("success"):
            _set_system_normal(session)
            return {
                "success": True,
                "warning": "Protective stop placement failed; filled exposure flattened immediately",
                "order_id": managed.broker_order_id,
                "filled_qty": int(managed.filled_quantity or 0),
                "avg_fill_price": entry_price,
                "state": "FILLED_FLATTENED_AFTER_STOP_FAILURE",
            }

        _trigger_emergency_lockdown(
            session,
            "Stop placement failed and flatten retries exhausted",
            symbol=tradingsymbol,
            details={"flatten_error": flatten.get("error"), "filled_qty": int(managed.filled_quantity or 0)},
        )
        return {
            "success": False,
            "error": "EMERGENCY_LOCKDOWN: could not protect or flatten filled exposure",
            "order_id": managed.broker_order_id,
            "filled_qty": int(managed.filled_quantity or 0),
            "avg_fill_price": entry_price,
            "state": "EMERGENCY_LOCKDOWN",
            "requires_emergency_remediation": True,
        }

    if managed.state in (OrderState.REJECTED, OrderState.CANCELLED) and int(managed.filled_quantity or 0) <= 0:
        err = managed.reject_reason or f"Entry aborted ({managed.state.value})"
        logger.warning("LIVE entry not confirmed: %s", err)
        return {"success": False, "error": err, "state": managed.state.value, "order_id": managed.broker_order_id}

    # Non-terminal timeout path:
    # Never return failure while broker may still hold exposure.
    logger.warning(
        "LIVE ENTRY timeout/non-terminal | client_order_id=%s state=%s -> cancel + reconcile",
        request.client_order_id,
        managed.state.value,
    )
    try:
        _order_manager.cancel_order(request.client_order_id)
    except Exception as e:
        logger.warning("LIVE ENTRY cancel request failed | client_order_id=%s | err=%s", request.client_order_id, str(e))

    deadline = time.time() + POST_CANCEL_RECONCILE_TIMEOUT_SEC
    latest = managed
    while time.time() < deadline:
        latest = _order_manager.poll_status(request.client_order_id)
        if latest.state in (OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED):
            break
        time.sleep(POST_CANCEL_POLL_INTERVAL_SEC)

    filled_qty = int(latest.filled_quantity or 0)
    avg_fill = float(latest.avg_fill_price or 0.0)
    if latest.state in (OrderState.ACKNOWLEDGED, OrderState.SENT, OrderState.PARTIAL_FILLED):
        broker_open_qty = _get_open_position_qty(tradingsymbol)
        if broker_open_qty > filled_qty:
            filled_qty = broker_open_qty
        if filled_qty > 0 and avg_fill <= 0:
            status = kite_get_order_status(str(latest.broker_order_id or ""))
            if status.get("success"):
                avg_fill = float(status.get("avg_fill_price") or 0.0)

    if filled_qty <= 0:
        # No exposure confirmed; safe deterministic failure.
        return {
            "success": False,
            "error": f"Entry not filled; final state={latest.state.value}",
            "state": latest.state.value,
            "order_id": latest.broker_order_id,
            "filled_qty": 0,
        }

    # Hard rule: if filled_qty > 0, never return failure.
    avg_fill = _resolve_entry_avg_fill_price(
        latest.broker_order_id,
        tradingsymbol,
        exchange,
        avg_fill,
    )
    if avg_fill <= 0:
        # Last guardrail to keep flow deterministic: use requested/observed price hints.
        avg_fill = float(price or 0.0)
        if avg_fill <= 0:
            avg_fill = 1.0
        logger.critical(
            "LIVE ENTRY RECON | forced placeholder avg_fill used to avoid unmanaged exposure | symbol=%s | avg_fill=%.2f",
            tradingsymbol,
            avg_fill,
        )

    partial_policy = _sanitize_partial_policy()
    if partial_policy == "FORCE_EXIT":
        flatten = _flatten_with_retries(tradingsymbol, exchange, side, filled_qty, retries=PARTIAL_FLATTEN_MAX_RETRIES)
        if flatten.get("success"):
            _set_system_normal(session)
            return {
                "success": True,
                "warning": "Entry timed out; partial exposure closed immediately",
                "state": "PARTIAL_FILLED_FLATTENED",
                "order_id": latest.broker_order_id,
                "filled_qty": filled_qty,
                "avg_fill_price": avg_fill,
            }
        logger.error(
            "LIVE ENTRY partial flatten failed after retries; attaching exposure to session | err=%s",
            flatten.get("error"),
        )

    # ATTACH policy, or FORCE_EXIT fallback when flatten fails.
    attach_ok = False
    attach_err: str | None = None
    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        trade_id = f"tr_{now.strftime('%Y%m%d%H%M%S')}_{symbol}"
        _set_active_trade(
            session,
            trade_id=trade_id,
            order_id=latest.broker_order_id,
            strategy_name=strategy_name,
            symbol=tradingsymbol,
            exchange=exchange,
            side=side,
            qty=filled_qty,
            entry_price=avg_fill,
            stop_loss=stop_loss,
            target=target,
        )
        session["current_trade"]["entry_reconciliation"] = {
            "source_state": latest.state.value,
            "policy": partial_policy,
            "filled_qty": filled_qty,
        }
        attach_ok = True
    except Exception as e:
        attach_err = str(e)
        logger.exception("LIVE ENTRY attach failed; trying flatten fallback: %s", attach_err)

    if not attach_ok:
        flatten = _flatten_with_retries(tradingsymbol, exchange, side, filled_qty, retries=PARTIAL_FLATTEN_MAX_RETRIES)
        if flatten.get("success"):
            _set_system_normal(session)
            # Hard rule requires no failure when exposure existed.
            return {
                "success": True,
                "warning": "Attach failed; exposure flattened after retries",
                "state": "PARTIAL_FILLED_FLATTENED_AFTER_ATTACH_FAIL",
                "order_id": latest.broker_order_id,
                "filled_qty": filled_qty,
                "avg_fill_price": avg_fill,
                "attach_error": attach_err,
            }
        _trigger_emergency_lockdown(
            session,
            "Partial-fill attach failed and flatten retries exhausted",
            symbol=tradingsymbol,
            details={"flatten_error": flatten.get("error"), "filled_qty": filled_qty},
        )
        return {
            "success": False,
            "error": "EMERGENCY_LOCKDOWN: could not attach or flatten partial exposure",
            "order_id": latest.broker_order_id,
            "filled_qty": filled_qty,
            "avg_fill_price": avg_fill,
            "state": "EMERGENCY_LOCKDOWN",
            "requires_emergency_remediation": True,
        }

    stop_result = _place_stop_with_retries(session, filled_qty, stop_loss, retries=STOP_PLACEMENT_RETRIES)
    if not stop_result.get("success"):
        flatten = _flatten_with_retries(
            tradingsymbol,
            exchange,
            side,
            filled_qty,
            retries=STOP_FAILURE_EXIT_RETRIES,
        )
        if flatten.get("success"):
            _set_system_normal(session)
            return {
                "success": True,
                "warning": "Partial fill attached but protective stop failed; position closed immediately",
                "state": "PARTIAL_FILLED_CLOSED",
                "order_id": latest.broker_order_id,
                "filled_qty": filled_qty,
                "avg_fill_price": avg_fill,
            }
        _trigger_emergency_lockdown(
            session,
            "Partial-fill stop placement failed and flatten retries exhausted",
            symbol=tradingsymbol,
            details={"filled_qty": filled_qty, "state": latest.state.value},
        )
        return {
            "success": False,
            "error": "EMERGENCY_LOCKDOWN: could not protect or flatten partial exposure",
            "order_id": latest.broker_order_id,
            "filled_qty": filled_qty,
            "avg_fill_price": avg_fill,
            "state": "EMERGENCY_LOCKDOWN",
            "requires_emergency_remediation": True,
        }
    return {
        "success": True,
        "order_id": latest.broker_order_id,
        "filled_qty": filled_qty,
        "avg_fill_price": avg_fill,
        "state": "PARTIAL_FILLED_ATTACHED",
    }


def exit_live_trade(
    session: dict,
    exit_price: float | None = None,
    exit_reason_override: str | None = None,
) -> dict[str, Any]:
    """Square off current trade via Zerodha using real fill reconciliation."""
    trade = session.get("current_trade")
    if not trade or not trade.get("symbol"):
        return {"success": False, "error": "No current trade"}
    symbol = trade["symbol"]
    exchange = trade.get("exchange") or session.get("exchange") or "NSE"
    side = trade.get("side", "BUY")
    qty = int(trade.get("qty", 0))
    broker_pos = _get_broker_position(symbol)
    broker_qty = int((broker_pos or {}).get("quantity") or 0)
    if broker_qty != 0:
        close_side = "SELL" if broker_qty > 0 else "BUY"
        qty = abs(broker_qty)
    else:
        close_side = "SELL" if side.upper() == "BUY" else "BUY"
    if qty <= 0:
        return {"success": False, "error": "Invalid exit quantity", "state": "INVALID_QTY"}
    preferred_product = str((broker_pos or {}).get("product") or "MIS").upper()
    if preferred_product not in {"MIS", "NRML", "CNC"}:
        preferred_product = "MIS"
    final_reason = exit_reason_override or trade.get("exit_reason") or "MANUAL_EXIT"

    # Safety order: cancel protective stop first. Broker can reject manual close
    # while a pending SL protective order is still active for the same position.
    pre_stop_res = _cancel_and_confirm_stop_order(session, trade)
    if not pre_stop_res.get("success"):
        session["state"] = "EXIT_PENDING_RECOVERY"
        session["recovery_attempts"] = int(session.get("recovery_attempts") or 0) + 1
        session["recovery_last_error"] = "Pre-exit stop cancellation confirmation failed"
        session["recovery_last_at"] = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
        return {
            "success": False,
            "error": "Stop cancellation confirmation failed before exit",
            "state": "PRE_EXIT_STOP_CANCEL_UNSAFE",
            "stop_order_id": trade.get("stop_order_id") or session.get("stop_order_id"),
            "stop_status": pre_stop_res.get("status"),
        }

    # If protective stop already flattened the position, finalize immediately.
    open_qty_after_stop_cancel = _get_open_position_qty(symbol)
    if open_qty_after_stop_cancel <= 0:
        stop_order_id = str(trade.get("stop_order_id") or session.get("stop_order_id") or "").strip()
        status_data = kite_get_order_status(stop_order_id) if stop_order_id else {"success": False}
        stop_status = str(status_data.get("status") or pre_stop_res.get("status") or "").upper()
        if stop_status in {"COMPLETE", "FILLED"}:
            stop_fill_qty = int(status_data.get("filled_quantity") or trade.get("qty") or 0)
            stop_fill_price = float(status_data.get("avg_fill_price") or trade.get("stop_loss") or trade.get("entry_price") or 0.0)
            if stop_fill_qty > 0 and stop_fill_price > 0:
                return {
                    **_finalize_live_exit(session, trade, stop_fill_price, stop_fill_qty, "STOP_LOSS"),
                    "state": "ALREADY_FLAT_BY_STOP",
                    "order_id": stop_order_id or None,
                }

    def _send_exit_order(product: str) -> tuple[OrderRequest, Any]:
        req = OrderRequest(
            symbol=symbol,
            side=close_side,
            quantity=qty,
            order_type="MARKET",
            price=None,
            exchange=exchange,
            metadata={"product": product},
        )
        return req, _order_manager.send_order(req)

    request, managed = _send_exit_order(preferred_product)
    logger.info(
        "LIVE EXIT FSM | client_order_id=%s | state=%s | broker_order_id=%s | side=%s | product=%s | broker_qty=%s",
        request.client_order_id,
        managed.state.value,
        managed.broker_order_id,
        close_side,
        preferred_product,
        broker_qty,
    )
    if managed.state == OrderState.REJECTED:
        err = managed.reject_reason or "Exit order rejected"
        # Product mismatch can cause "insufficient funds" on square-off.
        # Retry once with alternate product before failing.
        err_u = str(err).upper()
        retried = False
        if "INSUFFICIENT FUNDS" in err_u:
            fallback_product = "NRML" if preferred_product == "MIS" else "MIS"
            request, managed = _send_exit_order(fallback_product)
            retried = True
            logger.warning(
                "LIVE EXIT retrying with fallback product | client_order_id=%s | product=%s | side=%s",
                request.client_order_id,
                fallback_product,
                close_side,
            )
            if managed.state != OrderState.REJECTED:
                preferred_product = fallback_product
            else:
                err = managed.reject_reason or err
        if managed.state == OrderState.REJECTED:
            logger.warning("LIVE exit failed: %s", err)
            return {
                "success": False,
                "error": err,
                "state": managed.state.value,
                "side": close_side,
                "product": preferred_product,
                "retried": retried,
            }

    managed = _wait_for_terminal_fill(request.client_order_id)
    logger.info(
        "LIVE EXIT FSM | client_order_id=%s | terminal_state=%s | filled_qty=%s | avg_fill=%.2f",
        request.client_order_id,
        managed.state.value,
        managed.filled_quantity,
        float(managed.avg_fill_price or 0.0),
    )
    if managed.state != OrderState.FILLED:
        err = managed.reject_reason or f"Exit not fully filled (state={managed.state.value})"
        logger.warning("LIVE exit not confirmed: %s", err)
        return {"success": False, "error": err, "state": managed.state.value, "order_id": managed.broker_order_id}

    filled_qty = int(managed.filled_quantity or 0)
    if filled_qty <= 0:
        return {"success": False, "error": "Exit fill quantity is zero", "state": managed.state.value}
    exit_fill_price = float(managed.avg_fill_price or 0.0)
    if exit_fill_price <= 0:
        return {"success": False, "error": "Invalid exit fill price", "state": managed.state.value}

    # Finalization invariant: no open position AND no open stop order.
    open_qty = _get_open_position_qty(symbol)
    stop_order_id = str(trade.get("stop_order_id") or session.get("stop_order_id") or "").strip()
    stop_open, stop_open_status = _is_stop_order_open(stop_order_id) if stop_order_id else (False, None)
    if open_qty > 0 or stop_open:
        session["state"] = "EXIT_PENDING_RECOVERY"
        session["recovery_attempts"] = int(session.get("recovery_attempts") or 0) + 1
        session["recovery_last_error"] = "Post-close invariant failed (position/stop still open)"
        session["recovery_last_at"] = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
        logger.critical(
            "LIVE EXIT | CRITICAL finalization blocked; post-close invariants failed | open_qty=%s | stop_open=%s | stop_status=%s",
            open_qty,
            stop_open,
            stop_open_status,
        )
        return {
            "success": False,
            "error": "Post-close safety invariant failed (position/stop still open); finalization blocked",
            "state": "FILLED_POST_CLOSE_INVARIANT_FAILED",
            "order_id": managed.broker_order_id,
            "open_qty": open_qty,
            "stop_order_id": stop_order_id or None,
            "stop_status": stop_open_status,
        }

    return {
        **_finalize_live_exit(
            session,
            trade,
            exit_fill_price,
            filled_qty,
            final_reason,
        ),
        "order_id": managed.broker_order_id,
        "state": managed.state.value,
    }
