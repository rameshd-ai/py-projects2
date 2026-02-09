"""
Pullback to 20/50 EMA: intraday approximation of DMA pullback.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class Pullback2050DMA(BaseStrategy):
    """Pullback to 20/50 EMA (intraday EMA approximation)."""

    def _ema(self, candles: list[dict], period: int) -> float:
        if not candles or len(candles) < period:
            return 0.0
        k = 2.0 / (period + 1)
        ema = float(candles[0].get("close", 0))
        for c in candles[1:]:
            ema = float(c.get("close", 0)) * k + ema * (1 - k)
        return ema

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=60)
        if not candles or len(candles) < 50:
            return False, None
        ema20 = self._ema(candles[-30:], 20)
        ema50 = self._ema(candles[-50:], 50)
        if ema20 <= 0 or ema50 <= 0:
            return False, None
        last = candles[-1]
        if ema20 > ema50 and last["low"] <= ema20 and last["close"] > ema20:
            return True, round(float(last["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=20)
        if vwap <= 0:
            return round(entry_price * 0.995, 2)
        return round(vwap, 2)

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
