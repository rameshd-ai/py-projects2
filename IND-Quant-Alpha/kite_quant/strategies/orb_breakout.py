"""
Opening Range Breakout (ORB): trade first 45 min range break. Valid only before 10:15. SL 0.5%, target 1.5%.
"""
from __future__ import annotations

from datetime import datetime, time

from .base_strategy import BaseStrategy

# Indian market: consider 9:15 open; first 45 min = until 10:00. User specified 10:15.
ORB_CUTOFF_TIME = time(10, 15)


class OpeningRangeBreakout(BaseStrategy):
    def check_entry(self) -> tuple[bool, float | None]:
        now = datetime.now().time()

        # Only valid in first 45 minutes
        if now > ORB_CUTOFF_TIME:
            return False, None

        candles = self.data.get_recent_candles(self.instrument, interval="5minute", count=3)
        if not candles:
            return False, None

        opening_high = max((c.get("high") or 0) for c in candles)
        ltp = self.data.get_ltp(self.instrument)
        if opening_high <= 0 or ltp <= 0:
            return False, None

        if ltp > opening_high:
            return True, ltp

        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        return round(entry_price * 0.995, 2)

    def get_target(self, entry_price: float) -> float:
        return round(entry_price * 1.015, 2)

    def check_exit(self, trade: dict) -> str | None:
        ltp = self._get_exit_ltp(trade)
        if ltp <= 0:
            return None

        if trade.get("stop_loss") is not None and ltp <= trade["stop_loss"]:
            return "STOP_LOSS"
        if trade.get("target") is not None and ltp >= trade["target"]:
            return "TARGET"

        return None
