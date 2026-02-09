"""
Inside Bar Breakout: trade breakout from volatility coil (inside bar) with volume.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class InsideBarBreakout(BaseStrategy):
    """
    Inside Bar Breakout Strategy.
    Inside bar = candle fully inside previous range; enter on breakout with volume.
    """

    def check_entry(self) -> tuple[bool, float | None]:
        # Inside bar needs 10 candles to identify pattern
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=10, period="1d")
        if not candles or len(candles) < 3:
            return False, None

        mother = candles[-3]
        inside = candles[-2]
        last = candles[-1]
        vol_slice = candles[-5:] if len(candles) >= 5 else candles
        avg_vol = sum(c.get("volume", 0) or 0 for c in vol_slice) / len(vol_slice)
        if avg_vol <= 0:
            return False, None
        last_vol = last.get("volume") or 0

        if inside["high"] >= mother["high"] or inside["low"] <= mother["low"]:
            return False, None

        if last["close"] > inside["high"] and last_vol > avg_vol:
            return True, round(float(last["close"]), 2)
        if last["close"] < inside["low"] and last_vol > avg_vol:
            return True, round(float(last["close"]), 2)

        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=3)
        if not candles or len(candles) < 2:
            return round(entry_price * 0.995, 2)
        inside = candles[-2]
        inside_high = float(inside.get("high", entry_price))
        inside_low = float(inside.get("low", entry_price))
        if entry_price > inside_high:
            return round(inside_low, 2)
        return round(inside_high, 2)

    def get_target(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=3)
        if not candles or len(candles) < 2:
            return round(entry_price * 1.01, 2) if entry_price > 0 else round(entry_price * 0.99, 2)
        inside = candles[-2]
        inside_high = float(inside.get("high", entry_price))
        inside_low = float(inside.get("low", entry_price))
        range_size = inside_high - inside_low
        if range_size <= 0:
            return round(entry_price * 1.01, 2)
        if entry_price > inside_high:
            return round(entry_price + range_size, 2)
        return round(entry_price - range_size, 2)

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
