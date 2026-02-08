"""
Momentum Breakout: new high with volume spike = entry. SL 0.5%, target 1%.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class MomentumBreakout(BaseStrategy):
    def check_entry(self) -> tuple[bool, float | None]:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=5)
        if not candles or len(candles) < 3:
            return False, None
        prev = candles[:-1]
        last = candles[-1]
        high_break = last["close"] > max(c["high"] for c in prev)
        avg_vol = sum(c.get("volume", 0) or 0 for c in prev) / max(len(prev), 1)
        vol = last.get("volume") or 0
        volume_spike = avg_vol > 0 and vol >= 1.5 * avg_vol
        if high_break and volume_spike:
            return True, last["close"]
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        return round(entry_price * 0.995, 2)

    def get_target(self, entry_price: float) -> float:
        return round(entry_price * 1.01, 2)

    def check_exit(self, trade: dict) -> str | None:
        ltp = self._get_exit_ltp(trade)
        if ltp <= 0:
            return None
        stop_loss = trade.get("stop_loss")
        target = trade.get("target")
        if stop_loss is not None and ltp <= stop_loss:
            return "STOP_LOSS"
        if target is not None and ltp >= target:
            return "TARGET"
        return None
