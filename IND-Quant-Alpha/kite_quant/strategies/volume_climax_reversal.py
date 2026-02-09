"""
Volume Climax Reversal: exhaustion after extreme volume spike.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class VolumeClimaxReversal(BaseStrategy):
    """Reversal after climax candle with confirmation."""

    def check_entry(self) -> tuple[bool, float | None]:
        # Volume climax needs 15 candles for volume comparison
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=15, period="2d")
        if not candles or len(candles) < 10:
            return False, None
        climax, confirm = candles[-2], candles[-1]
        avg_vol = sum(c.get("volume", 0) or 0 for c in candles[-10:]) / 10
        avg_range = sum(abs(c["close"] - c["open"]) for c in candles[-10:]) / 10
        if avg_vol <= 0 or avg_range <= 0:
            return False, None
        if (climax.get("volume") or 0) <= avg_vol * 3:
            return False, None
        if abs(climax["close"] - climax["open"]) <= avg_range * 2:
            return False, None
        if confirm["close"] > confirm["open"] and climax["close"] < climax["open"]:
            return True, round(float(confirm["close"]), 2)
        if confirm["close"] < confirm["open"] and climax["close"] > climax["open"]:
            return True, round(float(confirm["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=3)
        if not candles or len(candles) < 2:
            return round(entry_price * 0.995, 2)
        c = candles[-2]
        if entry_price < c.get("open", entry_price):
            return round(float(c.get("high", entry_price)), 2)
        return round(float(c.get("low", entry_price)), 2)

    def get_target(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=10)
        if not candles:
            return round(entry_price * 1.01, 2)
        return round(sum(c["close"] for c in candles) / len(candles), 2)

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
