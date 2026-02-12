"""
NIFTY / BANKNIFTY engine: all index-specific logic lives here.
Use this package for backtest, paper, and live index flows only.
Stock logic should not import from here; keep stocks in a separate path later.
"""
from __future__ import annotations

from .constants import (
    NIFTY,
    BANKNIFTY,
    NSE_NIFTY_50,
    NSE_NIFTY_BANK,
    INDEX_NAMES,
    nse_symbol,
    normalize_index_name,
    is_index_instrument,
    get_strike_step_and_lot_size,
    default_spot,
)
from .live_data import fetch_nifty50_live, fetch_bank_nifty_live
from .bias import get_index_market_bias
from .options import (
    get_index_option_candidates,
    pick_best_index_option,
    get_affordable_index_options,
)
from .ai_recommendation import build_ai_trade_recommendation_index
from .backtest import run_index_backtest

__all__ = [
    "NIFTY",
    "BANKNIFTY",
    "NSE_NIFTY_50",
    "NSE_NIFTY_BANK",
    "INDEX_NAMES",
    "nse_symbol",
    "normalize_index_name",
    "is_index_instrument",
    "get_strike_step_and_lot_size",
    "default_spot",
    "fetch_nifty50_live",
    "fetch_bank_nifty_live",
    "get_index_market_bias",
    "get_index_option_candidates",
    "pick_best_index_option",
    "get_affordable_index_options",
    "build_ai_trade_recommendation_index",
    "run_index_backtest",
]
