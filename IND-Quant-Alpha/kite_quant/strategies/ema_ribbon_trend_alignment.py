"""
EMA Ribbon Trend Alignment: 9/20/50 EMA stacked trend.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class EMARibbonTrendAlignment(BaseStrategy):
    """Entry when price is near EMA9 in a stacked 9/20/50 EMA trend."""

    def _ema(self, candles: list[dict], period: int) -> float:
        if not candles or len(candles) < period:
            return 0.0
        k = 2.0 / (period + 1)
        ema = float(candles[0].get("close", 0))
        for c in candles[1:]:
            ema = float(c.get("close", 0)) * k + ema * (1 - k)
        return ema

    def check_entry(self) -> tuple[bool, float | None]:
        # EMA ribbon needs 50+ for multiple EMAs (9,21,50)
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=60, period="5d")
        if not candles or len(candles) < 50:
            return False, None
        ema9 = self._ema(candles[-15:], 9)
        ema20 = self._ema(candles[-30:], 20)
        ema50 = self._ema(candles[-50:], 50)
        if ema9 <= 0:
            return False, None
        ltp = float(candles[-1].get("close", 0))
        if ema9 > ema20 > ema50 and abs(ltp - ema9) / ema9 < 0.002:
            return True, round(ltp, 2)
        if ema9 < ema20 < ema50 and abs(ltp - ema9) / ema9 < 0.002:
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
