"""
Constants and symbol mapping for NIFTY / BANKNIFTY only.
Used by backtest, strategies, and live/paper so stock logic never touches this.
"""
from __future__ import annotations

# Index identifiers (session/API names)
NIFTY = "NIFTY"
BANKNIFTY = "BANKNIFTY"

# NSE display symbols (Zerodha/Kite)
NSE_NIFTY_50 = "NIFTY 50"
NSE_NIFTY_BANK = "NIFTY BANK"

# Valid index names for checks
INDEX_NAMES = frozenset({"NIFTY", "BANKNIFTY", "NIFTY50", "BANKNIFTY50"})

# Default spot when quote unavailable (for option candidates)
DEFAULT_SPOT_NIFTY = 24500.0
DEFAULT_SPOT_BANKNIFTY = 52000.0

# F&O: strike step and lot size per index
STRIKE_STEP_NIFTY = 50
STRIKE_STEP_BANKNIFTY = 100
LOT_SIZE_NIFTY = 25
LOT_SIZE_BANKNIFTY = 15


def nse_symbol(instrument: str) -> str:
    """
    Map session/API instrument to NSE symbol for OHLC/quote.
    Only handles NIFTY and BANKNIFTY; other symbols returned as-is (for future stock use elsewhere).
    """
    instrument = (instrument or "").strip().upper()
    if instrument == "NIFTY":
        return NSE_NIFTY_50
    if instrument == "BANKNIFTY":
        return NSE_NIFTY_BANK
    # Aliases
    if instrument in ("NIFTY50", "NIFTY 50"):
        return NSE_NIFTY_50
    if instrument in ("BANKNIFTY50", "NIFTY BANK", "BANK NIFTY"):
        return NSE_NIFTY_BANK
    return instrument


def normalize_index_name(instrument: str) -> str:
    """Return either NIFTY or BANKNIFTY. Use for option/backtest logic."""
    instrument = (instrument or "").strip().upper().replace(" ", "")
    if instrument not in INDEX_NAMES:
        return BANKNIFTY if "BANK" in instrument else NIFTY
    return BANKNIFTY if "BANK" in instrument else NIFTY


def is_index_instrument(instrument: str) -> bool:
    """True if instrument is NIFTY or BANKNIFTY (or common aliases)."""
    u = (instrument or "").upper()
    return u in ("NIFTY", "NIFTY 50", "NIFTY50", "BANKNIFTY", "BANK NIFTY", "NIFTY BANK")


def get_strike_step_and_lot_size(index_name: str) -> tuple[int, int]:
    """Return (strike_step, lot_size) for the index. index_name must be NIFTY or BANKNIFTY."""
    if index_name == BANKNIFTY:
        return STRIKE_STEP_BANKNIFTY, LOT_SIZE_BANKNIFTY
    return STRIKE_STEP_NIFTY, LOT_SIZE_NIFTY


def default_spot(index_name: str) -> float:
    """Default spot when quote unavailable."""
    return DEFAULT_SPOT_BANKNIFTY if index_name == BANKNIFTY else DEFAULT_SPOT_NIFTY
