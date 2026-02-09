"""
Multi-Timeframe Alignment: EMA proxy (fast/mid/slow on same TF).
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class MultiTimeframeAlignment(BaseStrategy):
    """Multi-timeframe alignment via multiple EMA speeds on same timeframe."""

    def _ema(self, candles: list[dict], period: int) -> float:
        if not candles or len(candles) < period:
            return 0.0
        k = 2.0 / (period + 1)
        ema = float(candles[0].get("close", 0))
        for c in candles[1:]:
            ema = float(c.get("close", 0)) * k + ema * (1 - k)
        return ema

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=80)
        if not candles or len(candles) < 60:
            return False, None
        ema_fast = self._ema(candles[-20:], 9)
        ema_mid = self._ema(candles[-40:], 20)
        ema_slow = self._ema(candles[-60:], 50)
        if ema_fast <= 0 or ema_mid <= 0 or ema_slow <= 0:
            return False, None
        ltp = float(candles[-1]["close"])
        if ema_fast > ema_mid > ema_slow and ltp > ema_fast:
            return True, round(ltp, 2)
        if ema_fast < ema_mid < ema_slow and ltp < ema_fast:
            return True, round(ltp, 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=10)
        if not candles:
            return round(entry_price * 0.995, 2)
        last_open = float(candles[-1].get("open", entry_price))
        if entry_price > last_open:
            return round(min(float(c.get("low", entry_price)) for c in candles), 2)
        return round(max(float(c.get("high", entry_price)) for c in candles), 2)

    def get_target(self, entry_price: float) -> float:
        sl = self.get_stop_loss(entry_price)
        risk = abs(entry_price - sl)
        if risk <= 0:
            return round(entry_price * 1.02, 2)
        if entry_price > sl:
            return round(entry_price + risk * 2, 2)
        return round(entry_price - risk * 2, 2)

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
