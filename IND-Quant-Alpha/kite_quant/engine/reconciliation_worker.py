"""
Broker reconciliation worker.

Polls broker open orders and positions every 5-10 seconds, reconciles against
in-memory session state, and repairs drift:
- Attach untracked broker positions to LIVE sessions.
- Clear stale session current_trade when broker shows no position.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime
from typing import Any, Callable

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)

# ALL SESSION MUTATIONS REQUIRE LOCK


class BrokerReconciliationWorker:
    """Background worker that reconciles broker state with local session state."""

    def __init__(
        self,
        *,
        get_open_orders_fn: Callable[[], list[dict[str, Any]]],
        get_positions_fn: Callable[[], list[dict[str, Any]]],
        get_sessions_fn: Callable[[], list[dict[str, Any]]],
        save_sessions_fn: Callable[[], None],
        sessions_lock: Any,
        poll_min_seconds: float = 5.0,
        poll_max_seconds: float = 10.0,
    ) -> None:
        self._get_open_orders = get_open_orders_fn
        self._get_positions = get_positions_fn
        self._get_sessions = get_sessions_fn
        self._save_sessions = save_sessions_fn
        self._sessions_lock = sessions_lock
        self._poll_min = max(1.0, poll_min_seconds)
        self._poll_max = max(self._poll_min, poll_max_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="broker_reconciliation_worker",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "[RECON] Worker started (poll every %.1f-%.1fs)",
            self._poll_min,
            self._poll_max,
        )

    def stop(self, timeout: float = 3.0) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.exception("[RECON] Worker loop error: %s", str(e))
            sleep_for = random.uniform(self._poll_min, self._poll_max)
            self._stop_event.wait(sleep_for)

    def run_once(self) -> None:
        """Run one reconciliation cycle."""
        open_orders = self._get_open_orders() or []
        broker_positions = self._get_positions() or []
        open_order_ids = {str(o.get("order_id")) for o in open_orders if o.get("order_id")}
        pos_by_symbol: dict[str, dict[str, Any]] = {}
        for p in broker_positions:
            sym = str(p.get("symbol") or "").upper()
            if not sym:
                continue
            qty = int(p.get("quantity") or 0)
            if qty != 0:
                pos_by_symbol[sym] = p

        updated = False
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        with self._sessions_lock:
            sessions = self._get_sessions() or []
            live_active = [s for s in sessions if (s.get("execution_mode") or "").upper() == "LIVE" and s.get("status") == "ACTIVE"]

            matched_symbols: set[str] = set()

            # 1) Reconcile sessions that already track a trade.
            for s in live_active:
                trade = s.get("current_trade")
                if not trade:
                    continue
                symbol = str(
                    trade.get("symbol") or s.get("tradingsymbol") or s.get("instrument") or ""
                ).upper()
                if not symbol:
                    continue
                stop_order_id = str((trade.get("stop_order_id") or s.get("stop_order_id") or "")).strip()
                stop_is_open = False
                if stop_order_id:
                    if stop_order_id in open_order_ids:
                        stop_is_open = True
                        trade["stop_order_status"] = "OPEN"
                        s["stop_order_status"] = "OPEN"
                    else:
                        trade["stop_order_status"] = "UNKNOWN_OR_TRIGGERED"
                        s["stop_order_status"] = "UNKNOWN_OR_TRIGGERED"
                    updated = True

                broker_pos = pos_by_symbol.get(symbol)
                if broker_pos:
                    matched_symbols.add(symbol)
                    bqty = abs(int(broker_pos.get("quantity") or 0))
                    bavg = float(broker_pos.get("average_price") or 0.0)
                    if bqty > 0 and int(trade.get("qty") or 0) != bqty:
                        trade["qty"] = bqty
                        updated = True
                    if bavg > 0 and (float(trade.get("entry_price") or 0.0) <= 0):
                        trade["entry_price"] = bavg
                        updated = True
                else:
                    in_exit_recovery = str(s.get("state") or "").upper() == "EXIT_PENDING_RECOVERY"
                    if in_exit_recovery and stop_is_open:
                        s["last_reconciliation_note"] = (
                            "EXIT_PENDING_RECOVERY: waiting for stop order to clear before session cleanup"
                        )
                        s["last_reconciliation_at"] = now.isoformat()
                        updated = True
                        continue

                    # Broker has no open position and (if recovery mode) no open stop: clear local state.
                    logger.warning(
                        "[RECON] Clearing stale current_trade | session=%s | symbol=%s",
                        s.get("sessionId"),
                        symbol,
                    )
                    s["current_trade_id"] = None
                    s["current_trade"] = None
                    s.pop("stop_order_id", None)
                    s.pop("stop_order_status", None)
                    if in_exit_recovery:
                        s["state"] = "ACTIVE"
                        s["recovery_resolved_at"] = now.isoformat()
                    s["last_reconciliation_note"] = (
                        "Cleared stale current_trade; no broker position and no open stop order"
                    )
                    s["last_reconciliation_at"] = now.isoformat()
                    updated = True

            # 2) Attach broker positions not tracked by sessions.
            unmatched = [(sym, p) for sym, p in pos_by_symbol.items() if sym not in matched_symbols]
            for sym, p in unmatched:
                target = next(
                    (
                        s
                        for s in live_active
                        if not s.get("current_trade")
                        and str(s.get("tradingsymbol") or s.get("instrument") or "").upper() in (sym, "")
                    ),
                    None,
                )
                if target is None:
                    target = next((s for s in live_active if not s.get("current_trade")), None)
                if target is None:
                    target = self._create_recovery_session(sessions, sym, now)
                    live_active.append(target)
                    updated = True

                qty = abs(int(p.get("quantity") or 0))
                avg = float(p.get("average_price") or 0.0)
                if qty <= 0:
                    continue
                trade_id = f"recon_{now.strftime('%Y%m%d%H%M%S')}_{sym}"
                target["current_trade_id"] = trade_id
                target["current_trade"] = {
                    "trade_id": trade_id,
                    "order_id": None,
                    "strategy_id": "",
                    "strategy_name": "Recovered Position",
                    "symbol": sym,
                    "exchange": target.get("exchange") or "NFO",
                    "side": "BUY" if int(p.get("quantity") or 0) > 0 else "SELL",
                    "qty": qty,
                    "entry_price": avg if avg > 0 else 0.0,
                    "entry_time": now.isoformat(),
                    "exit_time": None,
                    "exit_price": None,
                    "pnl": None,
                    "mode": "LIVE",
                    "recovered_by_reconciliation": True,
                }
                target["tradingsymbol"] = sym
                target["last_reconciliation_note"] = "Attached untracked broker open position"
                target["last_reconciliation_at"] = now.isoformat()
                logger.warning(
                    "[RECON] Attached untracked position | session=%s | symbol=%s | qty=%s",
                    target.get("sessionId"),
                    sym,
                    qty,
                )
                updated = True

            if updated:
                self._save_sessions()

    @staticmethod
    def _infer_instrument(symbol: str) -> str:
        s = (symbol or "").upper()
        if "BANKNIFTY" in s:
            return "BANKNIFTY"
        if "NIFTY" in s:
            return "NIFTY"
        return s

    def _create_recovery_session(
        self,
        sessions: list[dict[str, Any]],
        symbol: str,
        now: datetime,
    ) -> dict[str, Any]:
        session_id = f"recon_live_{now.strftime('%Y%m%d%H%M%S')}_{len(sessions)}"
        instrument = self._infer_instrument(symbol)
        lot_size = 15 if instrument == "BANKNIFTY" else 25
        session = {
            "sessionId": session_id,
            "instrument": instrument,
            "mode": "INTRADAY",
            "system_state": "NORMAL",
            "status": "ACTIVE",
            "execution_mode": "LIVE",
            "virtual_balance": None,
            "daily_trade_count": 0,
            "daily_pnl": 0.0,
            "daily_loss_limit": 3000.0,
            "risk_amount_per_trade": 300.0,
            "daily_trade_cap": 20,
            "consecutive_losses": 0,
            "cutoff_time": "15:15",
            "current_trade_id": None,
            "current_trade": None,
            "recommendation": {},
            "tradingsymbol": symbol,
            "exchange": "NFO",
            "lot_size": lot_size,
            "createdAt": now.isoformat(),
            "current_hour_block": now.hour,
            "hourly_trade_count": 0,
            "frequency_mode": "NORMAL",
            "ai_auto_switching_enabled": True,
            "ai_check_interval_minutes": 1,
            "last_ai_strategy_check": None,
            "last_ai_recommendation": None,
            "last_reconciliation_note": "Recovery session created by reconciliation worker",
            "last_reconciliation_at": now.isoformat(),
        }
        sessions.append(session)
        logger.warning("[RECON] Created recovery LIVE session | session=%s | symbol=%s", session_id, symbol)
        return session
