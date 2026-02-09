"""
RSI Reversal Fade: oversold bounce (RSI < 30). SL 0.7%, target 0.8%. Exit when RSI mean reversion complete.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class RSIReversal(BaseStrategy):
    def check_entry(self) -> tuple[bool, float | None]:
        # RSI-14 needs 16+ candles (period + 2)
        rsi = self.data.get_rsi(self.instrument, interval="5minute", period=14, count=20)
        ltp = self.data.get_ltp(self.instrument)
        if rsi is None or ltp <= 0:
            return False, None

        # Oversold bounce setup
        if rsi < 30:
            return True, ltp

        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        return round(entry_price * 0.993, 2)  # 0.7% SL

    def get_target(self, entry_price: float) -> float:
        return round(entry_price * 1.008, 2)  # 0.8% target (mean reversion)

    def check_exit(self, trade: dict) -> str | None:
        rsi = self.data.get_rsi(self.instrument, interval="5minute", period=14)
        ltp = self._get_exit_ltp(trade)
        if ltp <= 0:
            return None

        if trade.get("stop_loss") is not None and ltp <= trade["stop_loss"]:
            return "STOP_LOSS"
        if trade.get("target") is not None and ltp >= trade["target"]:
            return "TARGET"
        if rsi is not None and rsi > 55:
            return "RSI_MEAN_REVERSION_COMPLETE"

        return None
