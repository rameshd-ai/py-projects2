"""
VWAP Mean Reversion: trade snap-back when price is far from VWAP and volume fades.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class VWAPMeanReversion(BaseStrategy):
    """
    VWAP Mean Reversion Strategy.
    Enters when price is overextended from VWAP with volume contraction; target = VWAP.
    """

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=20)
        if not candles or len(candles) < 10:
            return False, None

        ltp = self.data.get_ltp(self.instrument)
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=20)
        if ltp <= 0 or vwap <= 0:
            return False, None

        deviation = abs(ltp - vwap) / vwap
        avg_vol = sum(c.get("volume", 0) or 0 for c in candles[-10:]) / 10
        if avg_vol <= 0:
            return False, None
        last_vol = candles[-1].get("volume") or 0

        if deviation > 0.006 and ltp > vwap and last_vol < avg_vol * 0.8:
            return True, round(float(ltp), 2)
        if deviation > 0.006 and ltp < vwap and last_vol < avg_vol * 0.8:
            return True, round(float(ltp), 2)

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
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=20)
        if vwap <= 0:
            return round(entry_price * 1.01, 2) if entry_price > 0 else round(entry_price * 0.99, 2)
        return round(vwap, 2)

    def check_exit(self, trade: dict) -> str | None:
        ltp = self._get_exit_ltp(trade)
        if ltp <= 0:
            return None
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=10)
        stop_loss = trade.get("stop_loss")
        side = (trade.get("side") or "BUY").upper()

        if side == "BUY":
            if stop_loss is not None and ltp <= stop_loss:
                return "STOP_LOSS"
            if vwap > 0 and ltp >= vwap:
                return "VWAP_REVERT"
        else:
            if stop_loss is not None and ltp >= stop_loss:
                return "STOP_LOSS"
            if vwap > 0 and ltp <= vwap:
                return "VWAP_REVERT"
        return None
