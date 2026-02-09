"""
Swing Volume Accumulation: intraday version — flat price + rising volume.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class SwingVolumeAccumulation(BaseStrategy):
    """Rising volume with flat price → breakout anticipation (intraday)."""

    def check_entry(self) -> tuple[bool, float | None]:
        # Volume accumulation needs 15 candles
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=15, period="2d")
        if not candles or len(candles) < 10:
            return False, None
        closes = [float(c.get("close", 0)) for c in candles[-10:]]
        vols = [c.get("volume", 0) or 0 for c in candles[-10:]]
        if not closes or closes[-1] <= 0:
            return False, None
        price_range = max(closes) - min(closes)
        vol_trend = vols[-1] > sum(vols[:5]) / 5 if len(vols) >= 5 else False
        if price_range / closes[-1] < 0.003 and vol_trend:
            return True, round(closes[-1], 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=5)
        if not candles:
            return round(entry_price * 0.995, 2)
        return round(min(float(c.get("low", entry_price)) for c in candles), 2)

    def get_target(self, entry_price: float) -> float:
        return round(entry_price * 1.02, 2)

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
