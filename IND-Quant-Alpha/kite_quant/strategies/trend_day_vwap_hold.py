"""
Trend Day VWAP Hold: buy dips above VWAP, exit only on VWAP break.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class TrendDayVWAPHold(BaseStrategy):
    """Sustained above VWAP, buy dip to VWAP, exit on VWAP break."""

    def check_entry(self) -> tuple[bool, float | None]:
        # Trend + VWAP needs 30 candles for accurate VWAP
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=30, period="3d")
        if not candles or len(candles) < 20:
            return False, None
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=30, period="3d")
        if vwap <= 0:
            return False, None
        above = [c for c in candles[-15:] if c["close"] > vwap]
        if len(above) < 12:
            return False, None
        last = candles[-1]
        if last["low"] <= vwap * 1.002 and last["close"] > vwap:
            return True, round(float(last["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=20)
        if vwap <= 0:
            return round(entry_price * 0.995, 2)
        return round(vwap, 2)

    def get_target(self, entry_price: float) -> float:
        return round(entry_price * 1.03, 2)

    def check_exit(self, trade: dict) -> str | None:
        ltp = self._get_exit_ltp(trade)
        if ltp <= 0:
            return None
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=10)
        if vwap > 0 and ltp < vwap:
            return "VWAP_BREAK"
        if trade.get("target") is not None and ltp >= trade["target"]:
            return "TARGET"
        return None
