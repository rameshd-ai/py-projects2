"""
Bollinger Band Mean Reversion: trade reversion from band extremes.
Entry on rejection wick outside band + volume contraction; target = middle band / VWAP.
"""
from __future__ import annotations

import statistics

from .base_strategy import BaseStrategy


class BollingerMeanReversion(BaseStrategy):
    """
    Bollinger Band Mean Reversion Strategy.
    Trades reversion from upper/lower band with rejection and volume confirmation.
    """

    def _get_bollinger(
        self, candles: list[dict], period: int = 20, std_mult: float = 2.0
    ) -> tuple[float, float, float]:
        if len(candles) < period:
            return 0.0, 0.0, 0.0
        closes = [float(c.get("close", 0)) for c in candles[-period:]]
        mean = statistics.mean(closes)
        std = statistics.stdev(closes) if len(closes) > 1 else 0.0
        upper = mean + std_mult * std
        lower = mean - std_mult * std
        return upper, mean, lower

    def check_entry(self) -> tuple[bool, float | None]:
        # Bollinger needs 20+ for std dev calculation
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=25, period="3d")
        if not candles or len(candles) < 20:
            return False, None

        last = candles[-1]
        upper, mid, lower = self._get_bollinger(candles)
        if upper <= 0 and lower <= 0:
            return False, None

        avg_vol = sum(c.get("volume", 0) or 0 for c in candles[-10:]) / 10
        if avg_vol <= 0:
            return False, None
        last_vol = last.get("volume") or 0

        # Bearish rejection above upper band → short
        if last["close"] > upper:
            if (
                last["high"] > upper
                and last["close"] < last["high"]
                and last_vol < avg_vol
            ):
                return True, round(float(last["close"]), 2)

        # Bullish rejection below lower band → long
        if last["close"] < lower:
            if (
                last["low"] < lower
                and last["close"] > last["low"]
                and last_vol < avg_vol
            ):
                return True, round(float(last["close"]), 2)

        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=5)
        if not candles:
            return round(entry_price * 0.995, 2)
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=5)
        if vwap <= 0:
            return round(entry_price * 0.995, 2)
        if entry_price > vwap:
            return round(max(float(c.get("high", entry_price)) for c in candles), 2)
        return round(min(float(c.get("low", entry_price)) for c in candles), 2)

    def get_target(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=25)
        if not candles or len(candles) < 20:
            return round(entry_price * 1.01, 2)
        _, mid, _ = self._get_bollinger(candles)
        if mid <= 0:
            return round(entry_price * 1.01, 2)
        return round(mid, 2)

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
