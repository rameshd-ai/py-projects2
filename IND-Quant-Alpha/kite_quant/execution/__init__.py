"""
Execution layer: LIVE (Zerodha), PAPER (simulated), BACKTEST (historical).
Strategies stay the same; only execution changes by session.execution_mode.
"""
from execution.executor import execute_entry, execute_exit, get_balance_for_mode

__all__ = ["execute_entry", "execute_exit", "get_balance_for_mode"]
