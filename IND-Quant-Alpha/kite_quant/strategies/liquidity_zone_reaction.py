"""
Liquidity Zone Reaction: price-based proxy at prior range H/L.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class LiquidityZoneReaction(BaseStrategy):
    """Reaction from previous range high/low."""

    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=30)
        if not candles or len(candles) < 20:
            return False, None
        pd_high = max(c["high"] for c in candles[:-10])
        pd_low = min(c["low"] for c in candles[:-10])
        if pd_low <= 0:
            return False, None
        last = candles[-1]
        if abs(last["low"] - pd_low) / pd_low < 0.002 and last["close"] > last["open"]:
            return True, round(float(last["close"]), 2)
        if pd_high > 0 and abs(last["high"] - pd_high) / pd_high < 0.002 and last["close"] < last["open"]:
            return True, round(float(last["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=5)
        if not candles:
            return round(entry_price * 0.995, 2)
        if entry_price > candles[-1]["open"]:
            return round(min(c["low"] for c in candles), 2)
        return round(max(c["high"] for c in candles), 2)

    def get_target(self, entry_price: float) -> float:
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=20)
        if vwap <= 0:
            return round(entry_price * 1.02, 2)
        return round(vwap, 2)

    def check_exit(self, trade: dict) -> str | None:
        ltp = self._get_exit_ltp(trade)
        if ltp <= 0:
            return None
        sl, tg = trade.get("stop_loss"), trade.get("target")
        side = (trade.get("side") or "BUY").upper()
        if side == "BUY":
            if sl is not None and ltp <= sl:
                return "STOP_LOSS"
            if tg is not None and ltp >= tg:
                return "TARGET"
        else:
            if sl is not None and ltp >= sl:
                return "STOP_LOSS"
            if tg is not None and ltp <= tg:
                return "TARGET"
        return None
