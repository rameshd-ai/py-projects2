"""
Base strategy: entry, exit, stop loss, target. All strategies inherit and implement these.
"""
from __future__ import annotations

from typing import Any

# Preferred return type for check_entry (full observability for Manual Mode)
EntryCheckResult = dict[str, Any]  # can_enter, entry_price, reason, conditions


class BaseStrategy:
    """Base class for all trading strategies. Data provider supplies candles and LTP."""

    def __init__(self, instrument: str, data_provider: Any):
        self.instrument = instrument
        self.data = data_provider

    def check_entry(self) -> tuple[bool, float | None] | dict[str, Any]:
        """
        Check if entry condition is met.
        May return:
          - (bool, float|None): (can_enter, entry_price) for backward compat.
          - dict: {"can_enter": bool, "entry_price": float|None, "reason": str, "conditions": dict}
                  for full observability (reason and conditions shown in UI).
        """
        raise NotImplementedError

    def check_exit(self, trade: dict[str, Any]) -> str | None:
        """
        Check if trade should exit. Returns "STOP_LOSS", "TARGET", "TRAILING", or None.
        trade has entry_price, stop_loss, target, entry_time, etc.
        """
        raise NotImplementedError

    def get_stop_loss(self, entry_price: float) -> float:
        """Return stop loss price for given entry."""
        raise NotImplementedError

    def get_target(self, entry_price: float) -> float:
        """Return target price for given entry."""
        raise NotImplementedError

    def _get_exit_ltp(self, trade: dict[str, Any]) -> float:
        """LTP for exit checks: NFO trades use option premium, else instrument LTP."""
        if trade.get("exchange") == "NFO" and trade.get("symbol"):
            quote = self.data.get_quote(trade["symbol"], exchange="NFO")
            return float(quote.get("last", 0) or quote.get("last_price", 0))
        return self.data.get_ltp(self.instrument)
