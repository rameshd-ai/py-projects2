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
        return round(entry_price * 0.985, 2)  # 1.5% SL - balanced

    def get_target(self, entry_price: float) -> float:
        return round(entry_price * 1.02, 2)  # 2% target - very easy to hit

    def check_exit(self, trade: dict) -> str | None:
        rsi = self.data.get_rsi(self.instrument, interval="5minute", period=14)
        
        # Check RSI mean reversion first (early exit on good signal)
        if rsi is not None and rsi > 55:
            return "RSI_MEAN_REVERSION_COMPLETE"
        
        # Use base strategy's trailing stop loss
        return super().check_exit(trade)
