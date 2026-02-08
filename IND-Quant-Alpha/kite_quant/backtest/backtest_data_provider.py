"""
Data provider for backtest: serves candles up to current index. No live/zerodha calls.
"""
from __future__ import annotations

from typing import Any


class BacktestDataProvider:
    """Provides get_recent_candles, get_ltp, get_vwap, get_rsi from a fixed candle list and current index."""

    def __init__(self, candles: list[dict[str, Any]], current_index: int = 0):
        self.candles = candles
        self.current_index = current_index

    def set_index(self, i: int) -> None:
        self.current_index = max(0, min(i, len(self.candles) - 1))

    def get_recent_candles(
        self,
        instrument: str,
        interval: str = "5m",
        count: int = 20,
        period: str = "1d",
    ) -> list[dict[str, Any]]:
        end = self.current_index + 1
        start = max(0, end - count)
        return self.candles[start:end]

    def get_ltp(self, instrument: str) -> float:
        if not self.candles or self.current_index < 0:
            return 0.0
        c = self.candles[self.current_index]
        return float(c.get("close", 0) or c.get("open", 0))

    def get_vwap(self, instrument: str, interval: str = "5m", count: int = 50) -> float:
        candles = self.get_recent_candles(instrument, interval=interval, count=count)
        if not candles:
            return 0.0
        total_vtp = 0.0
        total_vol = 0.0
        for c in candles:
            typical = (c.get("high", 0) + c.get("low", 0) + c.get("close", 0)) / 3.0
            vol = c.get("volume") or 0
            total_vtp += typical * vol
            total_vol += vol
        if total_vol <= 0:
            return float(candles[-1].get("close", 0))
        return round(total_vtp / total_vol, 2)

    def get_rsi(self, instrument: str, interval: str = "5m", period: int = 14, count: int | None = None) -> float | None:
        need = count or period + 2
        candles = self.get_recent_candles(instrument, interval=interval, count=need)
        if not candles:
            return None
        closes = [float(c.get("close", 0)) for c in candles if c.get("close")]
        if len(closes) < period + 1:
            return None
        return _rsi_from_prices(closes, period)


def _rsi_from_prices(prices: list[float], period: int) -> float | None:
    if not prices or len(prices) < period + 1:
        return None
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [c if c > 0 else 0.0 for c in changes[-period:]]
    losses = [-c if c < 0 else 0.0 for c in changes[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
