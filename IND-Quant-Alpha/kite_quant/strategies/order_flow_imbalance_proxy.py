"""
Order Flow Imbalance Proxy: volume + large body candle.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class OrderFlowImbalanceProxy(BaseStrategy):
    """Volume and body size above average as order flow proxy."""

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=10)
        if not candles or len(candles) < 5:
            return False, None
        last = candles[-1]
        avg_vol = sum(c.get("volume", 0) or 0 for c in candles[-5:]) / 5
        avg_body = sum(abs(c["close"] - c["open"]) for c in candles[-5:]) / 5
        if avg_vol <= 0 or avg_body <= 0:
            return False, None
        body = abs(last["close"] - last["open"])
        if body > avg_body * 2 and (last.get("volume") or 0) > avg_vol * 2:
            return True, round(float(last["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=3)
        if not candles:
            return round(entry_price * 0.995, 2)
        c = candles[-1]
        if entry_price > c.get("open", entry_price):
            return round(float(c.get("low", entry_price)), 2)
        return round(float(c.get("high", entry_price)), 2)

    def get_target(self, entry_price: float) -> float:
        sl = self.get_stop_loss(entry_price)
        risk = abs(entry_price - sl)
        if risk <= 0:
            return round(entry_price * 1.01, 2)
        if entry_price > sl:
            return round(entry_price + risk, 2)
        return round(entry_price - risk, 2)

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
