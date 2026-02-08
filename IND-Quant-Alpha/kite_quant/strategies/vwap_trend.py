"""
VWAP Trend Ride: price holds above VWAP for multiple candles = institutional trend. SL 0.4%, target 1.2%.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class VWAPTrend(BaseStrategy):
    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5minute", count=10)
        if not candles:
            return False, None

        vwap = self.data.get_vwap(self.instrument)
        ltp = self.data.get_ltp(self.instrument)
        if vwap <= 0 or ltp <= 0:
            return False, None

        # Strong trend if price holds above VWAP for multiple candles
        above_vwap_count = sum(1 for c in candles if (c.get("close") or 0) > vwap)

        if above_vwap_count >= 7 and ltp > vwap:
            return True, ltp

        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        return round(entry_price * 0.996, 2)  # 0.4% SL

    def get_target(self, entry_price: float) -> float:
        return round(entry_price * 1.012, 2)  # 1.2% target

    def check_exit(self, trade: dict) -> str | None:
        ltp = self._get_exit_ltp(trade)
        vwap = self.data.get_vwap(self.instrument)
        if ltp <= 0:
            return None

        if trade.get("stop_loss") is not None and ltp <= trade["stop_loss"]:
            return "STOP_LOSS"
        if trade.get("target") is not None and ltp >= trade["target"]:
            return "TARGET"
        if vwap > 0 and ltp < vwap:
            return "VWAP_BREAK"

        return None
