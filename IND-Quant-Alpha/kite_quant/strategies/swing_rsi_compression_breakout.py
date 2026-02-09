"""
Swing RSI Compression Breakout: intraday version — RSI 40–60 then expansion.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class SwingRSICompressionBreakout(BaseStrategy):
    """RSI compression (40–60) then expansion trigger (RSI > 60 or < 40)."""

    def check_entry(self) -> tuple[bool, float | None]:
        # RSI + swing needs 20 candles for RSI-14 + pattern
        rsi = self.data.get_rsi(self.instrument, interval="5m", period=14, count=20)
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=20, period="2d")
        if rsi is None or not candles or len(candles) < 5:
            return False, None
        if rsi > 60 or rsi < 40:
            return True, round(float(candles[-1]["close"]), 2)
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
