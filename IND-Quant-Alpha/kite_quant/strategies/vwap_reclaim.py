"""
VWAP Reclaim: price was below VWAP then reclaims with volume.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class VWAPReclaim(BaseStrategy):
    """Long-only: was below VWAP then close above with volume."""

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=20)
        if not candles or len(candles) < 15:
            return False, None
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=20)
        if vwap <= 0:
            return False, None
        if not all(c["close"] < vwap for c in candles[-15:-5]):
            return False, None
        reclaim = candles[-1]
        prev_vol = candles[-2].get("volume") or 0
        if reclaim["close"] > vwap and (reclaim.get("volume") or 0) > prev_vol:
            return True, round(float(reclaim["close"]), 2)
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
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=10)
        if vwap > 0 and ltp < vwap:
            return "VWAP_LOST"
        if trade.get("target") is not None and ltp >= trade["target"]:
            return "TARGET"
        return None
