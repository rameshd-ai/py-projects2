"""
Pullback Continuation: trade with the trend after a pullback to VWAP.
Enter when price rejects at VWAP with volume expansion. SL at structure, target ~2R.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class PullbackContinuation(BaseStrategy):
    """
    Pullback Continuation Strategy.
    Trades pullbacks to VWAP in a strong trend. Complements Momentum Breakout (avoids chasing).
    """

    def check_entry(self) -> tuple[bool, float | None]:
        # Pullback needs 20 candles to identify trend + pullback
        candles = self.data.get_recent_candles(self.instrument, interval="5m", count=20, period="2d")
        if not candles or len(candles) < 10:
            return False, None

        last = candles[-1]
        prev = candles[-2]
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=20, period="2d")
        ltp = self.data.get_ltp(self.instrument)

        if vwap <= 0 or ltp <= 0:
            return False, None

        avg_vol = sum(c.get("volume", 0) or 0 for c in candles[-10:]) / 10
        pullback_vol = prev.get("volume") or 0
        entry_vol = last.get("volume") or 0

        # --- Bullish trend: price above VWAP, pullback near VWAP ---
        if ltp > vwap and prev["low"] <= vwap * 1.002:
            if pullback_vol < avg_vol * 0.8:
                if (
                    last["close"] > last["open"]
                    and last["low"] < vwap
                    and entry_vol > avg_vol
                ):
                    return True, round(float(last["close"]), 2)

        # --- Bearish trend: price below VWAP, pullback near VWAP ---
        if ltp < vwap and prev["high"] >= vwap * 0.998:
            if pullback_vol < avg_vol * 0.8:
                if (
                    last["close"] < last["open"]
                    and last["high"] > vwap
                    and entry_vol > avg_vol
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
        # Bullish SL → recent swing low
        if entry_price >= vwap:
            return round(min(float(c.get("low", entry_price)) for c in candles), 2)
        # Bearish SL → recent swing high
        return round(max(float(c.get("high", entry_price)) for c in candles), 2)

    def get_target(self, entry_price: float) -> float:
        sl = self.get_stop_loss(entry_price)
        risk = abs(entry_price - sl)
        if risk <= 0:
            return round(entry_price * 1.02, 2) if entry_price >= sl else round(entry_price * 0.98, 2)
        # Trend continuation ~2R
        if entry_price > sl:
            return round(entry_price + 2 * risk, 2)
        return round(entry_price - 2 * risk, 2)

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

        # VWAP failure = early exit
        vwap = self.data.get_vwap(self.instrument, interval="5m", count=10)
        if vwap > 0:
            if side == "BUY" and ltp < vwap:
                return "VWAP_FAIL"
            if side == "SELL" and ltp > vwap:
                return "VWAP_FAIL"
        return None
