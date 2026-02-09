"""
Time-Based Volatility Play: trade momentum during known volatility windows.
"""
from __future__ import annotations

from datetime import datetime, time

from .base_strategy import BaseStrategy

VOL_WINDOWS = [
    (time(9, 15), time(9, 45)),
    (time(13, 45), time(14, 30)),
    (time(14, 45), time(15, 15)),
]


class TimeBasedVolatilityPlay(BaseStrategy):
    """Trades momentum during known volatility windows."""

    def _in_vol_window(self, now: time) -> bool:
        return any(start <= now <= end for start, end in VOL_WINDOWS)

    def check_entry(self) -> tuple[bool, float | None]:
        now = datetime.now().time()
        if not self._in_vol_window(now):
            return False, None
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=10)
        if not candles or len(candles) < 5:
            return False, None
        last, prev = candles[-1], candles[-2]
        if last["close"] > prev["high"]:
            return True, round(float(last["close"]), 2)
        if last["close"] < prev["low"]:
            return True, round(float(last["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=5)
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
            return round(entry_price * 1.015, 2)
        if entry_price > sl:
            return round(entry_price + risk * 1.5, 2)
        return round(entry_price - risk * 1.5, 2)

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
