"""
Sector Rotation Momentum: single-instrument approximation of sector leadership.
Strong relative momentum vs own recent range treated as sector leader.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class SectorRotationMomentum(BaseStrategy):
    """Treats strong relative momentum vs own range as sector leadership."""

    def check_entry(self) -> tuple[bool, float | None]:
        # Sector rotation needs 30 candles for momentum analysis
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=30, period="3d")
        if not candles or len(candles) < 20:
            return False, None
        last = candles[-1]
        recent_high = max(float(c.get("high", 0)) for c in candles[-20:])
        recent_low = min(float(c.get("low", float("inf")) or float("inf")) for c in candles[-20:])
        if recent_low <= 0 or recent_low == float("inf"):
            return False, None
        range_pct = (recent_high - recent_low) / recent_low
        move_pct = (last["close"] - recent_low) / recent_low
        avg_vol = sum(c.get("volume", 0) or 0 for c in candles[-10:]) / 10
        if avg_vol <= 0:
            return False, None
        if move_pct > range_pct * 0.6 and (last.get("volume") or 0) > avg_vol * 1.3:
            return True, round(float(last["close"]), 2)
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=5)
        if not candles:
            return round(entry_price * 0.995, 2)
        return round(min(float(c.get("low", entry_price)) for c in candles), 2)

    def get_target(self, entry_price: float) -> float:
        sl = self.get_stop_loss(entry_price)
        risk = entry_price - sl
        if risk <= 0:
            return round(entry_price * 1.02, 2)
        return round(entry_price + risk * 2, 2)

    def check_exit(self, trade: dict) -> str | None:
        ltp = self._get_exit_ltp(trade)
        if ltp <= 0:
            return None
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=10)
        stop_loss = trade.get("stop_loss")
        target = trade.get("target")
        side = (trade.get("side") or "BUY").upper()
        if side == "BUY":
            if stop_loss is not None and ltp <= stop_loss:
                return "STOP_LOSS"
            if vwap > 0 and ltp < vwap:
                return "MOMENTUM_FADE"
            if target is not None and ltp >= target:
                return "TARGET"
        else:
            if stop_loss is not None and ltp >= stop_loss:
                return "STOP_LOSS"
            if vwap > 0 and ltp > vwap:
                return "MOMENTUM_FADE"
            if target is not None and ltp <= target:
                return "TARGET"
        return None
