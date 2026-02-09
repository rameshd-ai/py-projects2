"""
Liquidity Sweep Reversal: trade reversal after price sweeps prior high/low then rejects.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class LiquiditySweepReversal(BaseStrategy):
    """
    Liquidity Sweep Reversal Strategy.
    Enters when price sweeps prior high/low and reverses with strong opposite candle + volume.
    """

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=20)
        if not candles or len(candles) < 6:
            return False, None

        last = candles[-1]
        prev = candles[-2]
        prev_high = max(float(c.get("high", 0)) for c in candles[-6:-1])
        prev_low = min((float(c.get("low", 0)) or 0) for c in candles[-6:-1])
        vol_slice = candles[-10:] if len(candles) >= 10 else candles
        avg_vol = sum(c.get("volume", 0) or 0 for c in vol_slice) / len(vol_slice)
        if avg_vol <= 0:
            return False, None
        last_vol = last.get("volume") or 0

        if prev["high"] > prev_high and last["close"] < last["open"] and last_vol > avg_vol:
            return True, round(float(last["close"]), 2)
        if prev["low"] < prev_low and last["close"] > last["open"] and last_vol > avg_vol:
            return True, round(float(last["close"]), 2)

        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=5)
        if not candles:
            return round(entry_price * 0.995, 2)
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=5)
        if vwap <= 0:
            return round(entry_price * 0.995, 2)
        if entry_price < vwap:
            return round(min(float(c.get("low", entry_price)) for c in candles), 2)
        return round(max(float(c.get("high", entry_price)) for c in candles), 2)

    def get_target(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=10)
        if not candles:
            return round(entry_price * 1.01, 2) if entry_price > 0 else round(entry_price * 0.99, 2)
        avg_close = sum(float(c.get("close", 0)) for c in candles) / len(candles)
        return round(avg_close, 2)

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
