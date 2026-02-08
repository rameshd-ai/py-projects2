"""
Data provider for strategies: recent candles and LTP. Uses engine.data_fetcher and zerodha.
"""
from __future__ import annotations

from typing import Any

from engine.data_fetcher import fetch_nse_ohlc
from engine.zerodha_client import get_quote as _kite_get_quote


def _nse_symbol(instrument: str) -> str:
    """Map session instrument to NSE symbol for OHLC/quote."""
    instrument = (instrument or "").strip().upper()
    if instrument == "NIFTY":
        return "NIFTY 50"
    if instrument == "BANKNIFTY":
        return "NIFTY BANK"
    return instrument


def _interval_kite(interval: str) -> str:
    """Map strategy interval to fetcher interval (e.g. 5minute -> 5m)."""
    if interval in ("5minute", "5min"):
        return "5m"
    if interval in ("15minute", "15min"):
        return "15m"
    if interval in ("1minute", "1min"):
        return "1m"
    return interval or "5m"


def get_recent_candles(
    instrument: str,
    interval: str = "5m",
    count: int = 20,
    period: str = "1d",
) -> list[dict[str, Any]]:
    """
    Return list of recent candles, newest last. Each candle: open, high, low, close, volume, date (iso).
    interval can be "5m" or "5minute".
    """
    symbol = _nse_symbol(instrument)
    kite_interval = _interval_kite(interval)
    df = fetch_nse_ohlc(symbol, interval=kite_interval, period=period)
    if df is None or df.empty or "Close" not in df.columns:
        return []
    # Standardize column names (Zerodha returns Datetime, Open, High, Low, Close, Volume)
    rename = {"Datetime": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    use = {rename.get(c, c.lower()): c for c in df.columns if c in rename or c.lower() in ("open", "high", "low", "close", "volume", "datetime")}
    out = []
    for _, row in df.tail(count).iterrows():
        c = {}
        if "Datetime" in df.columns:
            d = row.get("Datetime")
            c["date"] = d.isoformat() if hasattr(d, "isoformat") else str(d)
        else:
            c["date"] = str(row.get("date", ""))
        c["open"] = float(row.get("Open", row.get("open", 0)))
        c["high"] = float(row.get("High", row.get("high", 0)))
        c["low"] = float(row.get("Low", row.get("low", 0)))
        c["close"] = float(row.get("Close", row.get("close", 0)))
        c["volume"] = float(row.get("Volume", row.get("volume", 0)))
        out.append(c)
    return out


def get_quote(symbol: str, exchange: str = "NSE") -> dict[str, Any]:
    """Get quote from Zerodha. For NFO options pass exchange='NFO' and symbol as tradingsymbol."""
    return _kite_get_quote(symbol, exchange=exchange)


def get_ltp(instrument: str) -> float:
    """Return last traded price for instrument (NSE)."""
    symbol = _nse_symbol(instrument)
    quote = _kite_get_quote(symbol)
    return float(quote.get("last", 0) or quote.get("last_price", 0))


def get_vwap(instrument: str, interval: str = "5m", count: int = 50) -> float:
    """Volume-weighted average price from recent candles. Returns 0 if no data."""
    candles = get_recent_candles(instrument, interval=interval, count=count)
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


def get_rsi(instrument: str, interval: str = "5m", period: int = 14, count: int | None = None) -> float | None:
    """RSI from recent close prices. Returns None if not enough data."""
    need = (count or period + 2)
    candles = get_recent_candles(instrument, interval=interval, count=need)
    if not candles:
        return None
    closes = [float(c.get("close", 0)) for c in candles if c.get("close")]
    if len(closes) < period + 1:
        return None
    return _rsi_from_prices(closes, period)
