"""
Strategy registry: map strategy names (from algo/recommendation) to strategy classes.
"""
from __future__ import annotations

from typing import Any

from strategies.base_strategy import BaseStrategy
from strategies.momentum_breakout import MomentumBreakout
from strategies.vwap_trend import VWAPTrend
from strategies.rsi_reversal import RSIReversal
from strategies.orb_breakout import OpeningRangeBreakout

STRATEGY_MAP: dict[str, type[BaseStrategy]] = {
    "Momentum Breakout": MomentumBreakout,
    "momentum_breakout": MomentumBreakout,
    "VWAP Trend Ride": VWAPTrend,
    "vwap_trend_ride": VWAPTrend,
    "RSI Reversal Fade": RSIReversal,
    "rsi_reversal_fade": RSIReversal,
    "Opening Range Breakout": OpeningRangeBreakout,
    "orb_opening_range_breakout": OpeningRangeBreakout,
    "orb": OpeningRangeBreakout,
    "Index Momentum": MomentumBreakout,
    "index_lead_stock_lag": MomentumBreakout,
}


def get_strategy_for_session(
    session: dict,
    data_provider: Any,
    strategy_name_override: str | None = None,
) -> BaseStrategy | None:
    """Return strategy instance. Uses strategy_name_override if given (for engine re-scan), else session recommendation."""
    rec = session.get("recommendation") or {}
    name = strategy_name_override or rec.get("strategyName") or rec.get("selectedAlgoName") or rec.get("strategy") or ""
    strategy_id = rec.get("strategyId") or ""
    StrategyClass = STRATEGY_MAP.get(name) or STRATEGY_MAP.get(strategy_id)
    if not StrategyClass:
        StrategyClass = MomentumBreakout
    instrument = session.get("instrument", "")
    return StrategyClass(instrument, data_provider)
