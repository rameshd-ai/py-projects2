"""
Failed Breakdown / Trap Reversal: stops hunted then price reclaims.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class FailedBreakdownTrap(BaseStrategy):
    """Break below support then reclaim above with volume."""

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=15)
        if not candles or len(candles) < 10:
            return False, None
        support = min(c["low"] for c in candles[-10:-2])
        breakdown, reclaim = candles[-2], candles[-1]
        avg_vol = sum(c.get("volume", 0) or 0 for c in candles[-10:]) / 10
        if avg_vol <= 0:
            return False, None
        if (
            breakdown["low"] < support
            and reclaim["close"] > support
            and reclaim["close"] > reclaim["open"]
            and (reclaim.get("volume") or 0) > avg_vol
        ):
            return True, round(float(reclaim["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=3)
        if not candles:
            return round(entry_price * 0.995, 2)
        return round(min(c["low"] for c in candles), 2)

    def get_target(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=10)
        if not candles:
            return round(entry_price * 1.02, 2)
        return round(sum(c["high"] for c in candles) / len(candles), 2)

    def check_exit(self, trade: dict) -> str | None:
        ltp = self._get_exit_ltp(trade)
        if ltp <= 0:
            return None
        stop_loss = trade.get("stop_loss")
        target = trade.get("target")
        side = (trade.get("side") or "BUY").upper()
        if side == "BUY":
            if stop_loss is not None and ltp <= stop_loss:
                return "STOP_LOSS"
            if target is not None and ltp >= target:
                return "TARGET"
        else:
            if stop_loss is not None and ltp >= stop_loss:
                return "STOP_LOSS"
            if target is not None and ltp <= target:
                return "TARGET"
        return None
