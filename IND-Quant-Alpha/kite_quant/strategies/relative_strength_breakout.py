"""
Relative Strength Breakout: stock breaking out while holding gains.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class RelativeStrengthBreakout(BaseStrategy):
    """Stock breaking out of recent base with volume."""

    def check_entry(self) -> tuple[bool, float | None]:
        # Relative strength needs 20 candles for comparison
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=20, period="2d")
        if not candles or len(candles) < 15:
            return False, None
        last = candles[-1]
        base_high = max(float(c.get("high", 0)) for c in candles[-10:-2])
        avg_vol = sum(c.get("volume", 0) or 0 for c in candles[-10:]) / 10
        if avg_vol <= 0:
            return False, None
        if last["close"] > base_high and (last.get("volume") or 0) > avg_vol:
            return True, round(float(last["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=5)
        if not candles:
            return round(entry_price * 0.995, 2)
        return round(min(float(c.get("low", entry_price)) for c in candles), 2)

    def get_target(self, entry_price: float) -> float:
        sl = self.get_stop_loss(entry_price)
        risk = entry_price - sl
        if risk <= 0:
            return round(entry_price * 1.02, 2)
        return round(entry_price + risk * 2, 2)

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
