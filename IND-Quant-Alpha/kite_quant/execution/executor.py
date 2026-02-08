"""
Execution router: dispatch by session.execution_mode (LIVE / PAPER / BACKTEST).
Strategy logic unchanged; only execution layer differs.
"""
from __future__ import annotations

import logging
from typing import Any

from execution import live_executor, paper_executor, backtest_executor
from engine.zerodha_client import get_balance as get_live_balance

logger = logging.getLogger(__name__)


def execute_entry(
    session: dict,
    symbol: str,
    side: str,
    qty: int,
    price: float | None = None,
    strategy_name: str = "",
    candle: dict | None = None,
    stop_loss: float | None = None,
    target: float | None = None,
) -> dict[str, Any]:
    """Route entry to LIVE, PAPER, or BACKTEST executor. stop_loss/target stored in current_trade for exit logic."""
    mode = (session.get("execution_mode") or "PAPER").upper()
    if mode == "LIVE":
        return live_executor.place_live_order(session, symbol, side, qty, price, strategy_name, stop_loss, target)
    if mode == "PAPER":
        return paper_executor.place_paper_trade(session, symbol, side, qty, price, strategy_name, stop_loss, target)
    if mode == "BACKTEST" and candle:
        return backtest_executor.simulate_entry(session, symbol, side, qty, candle, strategy_name)
    if mode == "BACKTEST":
        return {"success": False, "error": "BACKTEST requires candle"}
    return {"success": False, "error": f"Unknown execution_mode: {mode}"}


def execute_exit(
    session: dict,
    exit_price: float | None = None,
    candle: dict | None = None,
) -> dict[str, Any]:
    """Route exit to LIVE, PAPER, or BACKTEST executor."""
    mode = (session.get("execution_mode") or "PAPER").upper()
    if mode == "LIVE":
        return live_executor.exit_live_trade(session, exit_price)
    if mode == "PAPER":
        return paper_executor.exit_paper_trade(session, exit_price)
    if mode == "BACKTEST":
        return backtest_executor.simulate_exit(session, candle or {}, exit_price)
    return {"success": False, "error": f"Unknown execution_mode: {mode}"}


def get_balance_for_mode(mode: str, sessions: list[dict] | None = None) -> tuple[float, str]:
    """
    Return (balance, mode) for the given mode.
    LIVE: Zerodha live balance.
    PAPER/BACKTEST: aggregate virtual_balance from sessions with that mode, or 0.
    """
    mode = (mode or "LIVE").upper()
    if mode == "LIVE":
        balance, ok = get_live_balance()
        return (balance, "LIVE")
    sessions = sessions or []
    same_mode = [s for s in sessions if (s.get("execution_mode") or "PAPER").upper() == mode]
    total = 0.0
    for s in same_mode:
        vb = s.get("virtual_balance")
        if vb is not None:
            total += float(vb)
    return (total, mode)
