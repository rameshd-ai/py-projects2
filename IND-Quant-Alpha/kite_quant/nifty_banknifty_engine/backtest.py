"""
Thin wrapper for running backtest on NIFTY/BANKNIFTY only.
Delegates to backtest.backtest_engine with index symbol resolution from this engine.
"""
from __future__ import annotations

from typing import Any

from .constants import nse_symbol


def run_index_backtest(
    instrument: str,
    strategy_name: str,
    from_date: str,
    to_date: str,
    timeframe: str = "5minute",
    initial_capital: float = 100000.0,
    risk_percent_per_trade: float = 1.0,
    max_daily_loss_percent: float = 3.0,
    max_trades: int = 20,
) -> dict[str, Any]:
    """
    Run backtest for NIFTY or BANKNIFTY. Normalizes instrument to NSE symbol and
    calls the shared backtest engine. Do not use for stocks; use a separate stock backtest path.
    """
    from backtest.backtest_engine import run_backtest_engine
    # Normalize so backtest_engine gets NIFTY or BANKNIFTY (it will call nse_symbol internally if needed)
    instrument = (instrument or "").strip().upper()
    if instrument in ("NIFTY 50", "NIFTY50"):
        instrument = "NIFTY"
    elif instrument in ("NIFTY BANK", "BANK NIFTY"):
        instrument = "BANKNIFTY"
    return run_backtest_engine(
        instrument=instrument,
        strategy_name=strategy_name,
        from_date=from_date,
        to_date=to_date,
        timeframe=timeframe,
        initial_capital=initial_capital,
        risk_percent_per_trade=risk_percent_per_trade,
        max_daily_loss_percent=max_daily_loss_percent,
        max_trades=max_trades,
    )
