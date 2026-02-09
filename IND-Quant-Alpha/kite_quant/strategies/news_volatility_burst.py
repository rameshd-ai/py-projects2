"""
News Volatility Burst: trade market reaction to news via impulse + volume surge.
No news feed — we trade the reaction (impulse + volume).
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class NewsVolatilityBurst(BaseStrategy):
    """Trades sudden impulse + volume surge (market reaction to news)."""

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=10)
        if not candles or len(candles) < 5:
            return False, None
        last = candles[-1]
        avg_range = sum(abs(float(c.get("close", 0)) - float(c.get("open", 0))) for c in candles[-5:]) / 5
        avg_vol = sum(c.get("volume", 0) or 0 for c in candles[-5:]) / 5
        if avg_vol <= 0 or avg_range <= 0:
            return False, None
        impulse = abs(last["close"] - last["open"])
        last_vol = last.get("volume") or 0
        if impulse > avg_range * 2 and last_vol > avg_vol * 2:
            return True, round(float(last["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=3)
        if not candles:
            return round(entry_price * 0.995, 2)
        c = candles[-1]
        if entry_price > float(c.get("open", entry_price)):
            return round(float(c.get("low", entry_price)), 2)
        return round(float(c.get("high", entry_price)), 2)

    def get_target(self, entry_price: float) -> float:
        sl = self.get_stop_loss(entry_price)
        risk = abs(entry_price - sl)
        if risk <= 0:
            return round(entry_price * 1.01, 2)
        return round(entry_price + risk, 2) if entry_price > sl else round(entry_price - risk, 2)

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
