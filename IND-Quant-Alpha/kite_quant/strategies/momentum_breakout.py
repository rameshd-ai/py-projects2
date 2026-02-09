"""
Momentum Breakout: new high with volume spike = entry. SL 0.5%, target 1%.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class MomentumBreakout(BaseStrategy):
    def check_entry(self) -> dict:
        # Momentum needs 5-10 recent candles for breakout detection
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=10, period="2d")
        if not candles or len(candles) < 3:
            return {
                "can_enter": False,
                "entry_price": None,
                "reason": "Insufficient candles",
                "conditions": {"enough_candles": False, "high_break": False, "volume_spike": False},
            }
        prev = candles[:-1]
        last = candles[-1]
        high_break = last["close"] > max(c["high"] for c in prev)
        avg_vol = sum(c.get("volume", 0) or 0 for c in prev) / max(len(prev), 1)
        vol = last.get("volume") or 0
        volume_spike = avg_vol > 0 and vol >= 1.5 * avg_vol
        if high_break and volume_spike:
            return {
                "can_enter": True,
                "entry_price": last["close"],
                "reason": "New high with volume spike",
                "conditions": {"enough_candles": True, "high_break": True, "volume_spike": True},
            }
        reasons = []
        if not high_break:
            reasons.append("Price below recent high")
        if not volume_spike:
            reasons.append("Volume spike missing")
        return {
            "can_enter": False,
            "entry_price": None,
            "reason": "; ".join(reasons) if reasons else "Condition not met",
            "conditions": {"enough_candles": True, "high_break": high_break, "volume_spike": volume_spike},
        }

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
