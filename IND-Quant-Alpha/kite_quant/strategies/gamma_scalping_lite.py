"""
Gamma Scalping Lite: fast momentum scalps with tight stops.
Approximates gamma scalping as price-driven scalping (no IV/greeks).
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class GammaScalpingLite(BaseStrategy):
    """
    Gamma Scalping Lite Strategy.
    Fast momentum scalps with tight stops; honest approximation without IV.
    """

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=5)
        if not candles or len(candles) < 3:
            return False, None

        last = candles[-1]
        prev = candles[-2]
        prev_range = prev["high"] - prev["low"]
        if prev_range <= 0:
            return False, None

        impulse = abs(last["close"] - prev["close"])
        if impulse > prev_range * 1.5:
            return True, round(float(last["close"]), 2)

        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=5)
        if vwap <= 0:
            return round(entry_price * 0.997, 2)
        if entry_price > vwap:
            return round(entry_price * 0.997, 2)
        return round(entry_price * 1.003, 2)

    def get_target(self, entry_price: float) -> float:
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=5)
        if vwap <= 0:
            return round(entry_price * 1.003, 2)
        if entry_price > vwap:
            return round(entry_price * 1.003, 2)
        return round(entry_price * 0.997, 2)

    def check_exit(self, trade: dict) -> str | None:
        ltp = self._get_exit_ltp(trade)
        if ltp <= 0:
            return None
        entry = trade.get("entry_price") or trade.get("entry") or 0
        if entry <= 0:
            return None
        if abs(ltp - entry) < entry * 0.001:
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
