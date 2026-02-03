"""
Data fetcher: S&P 500 (yfinance), NSE/INDstocks (REST).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf
import requests


def fetch_sp500_previous_close() -> tuple[float | None, float | None]:
    """
    Fetch S&P 500 (^GSPC) previous close and % change.
    Returns (prev_close, pct_change) or (None, None) on error.
    """
    try:
        ticker = yf.Ticker("^GSPC")
        hist = ticker.history(period="5d")
        if hist.empty or len(hist) < 2:
            return None, None
        prev = hist["Close"].iloc[-2]
        curr = hist["Close"].iloc[-1]
        pct = ((curr - prev) / prev) * 100 if prev else None
        return float(prev), float(pct) if pct is not None else None
    except Exception:
        return None, None


def fetch_nse_ohlc(
    symbol: str,
    interval: str = "5m",
    period: str = "1d",
    api_key: str | None = None,
    base_url: str | None = None,
) -> pd.DataFrame:
    """
    Fetch NSE OHLC for symbol. Uses INDstocks-style API if credentials given,
    else returns mock/empty for backtest with local data.
    """
    api_key = api_key or os.getenv("IND_API_KEY")
    base_url = (base_url or os.getenv("IND_BASE_URL", "https://api.indstocks.com")).rstrip("/")

    if not api_key or base_url == "https://api.indstocks.com":
        # No credentials or default: return empty for backtest to fill from CSV/yfinance
        return pd.DataFrame()

    try:
        # INDstocks-style historical candles (adjust path to match actual API docs)
        url = f"{base_url}/v1/historical/candles"
        params = {"symbol": symbol, "interval": interval, "period": period}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict) and "candles" in data:
            df = pd.DataFrame(data["candles"])
        else:
            df = pd.DataFrame(data.get("data", []))
        if df.empty:
            return df
        # Normalize columns to OHLCV
        renames = {
            "open": "Open", "high": "High", "low": "Low", "close": "Close",
            "volume": "Volume", "timestamp": "Datetime", "date": "Datetime",
        }
        for k, v in renames.items():
            if k in df.columns and v not in df.columns:
                df = df.rename(columns={k: v})
        if "Datetime" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["Datetime"]):
            df["Datetime"] = pd.to_datetime(df["Datetime"], unit="s", errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def fetch_nse_quote(
    symbol: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Fetch current quote for symbol from INDstocks (or mock)."""
    api_key = api_key or os.getenv("IND_API_KEY")
    base_url = (base_url or os.getenv("IND_BASE_URL", "https://api.indstocks.com")).rstrip("/")

    if not api_key:
        return {"symbol": symbol, "last": 0.0, "open": 0.0, "high": 0.0, "low": 0.0}

    try:
        url = f"{base_url}/v1/quote"
        params = {"symbol": symbol}
        headers = {"Authorization": f"Bearer {api_key}"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        q = r.json()
        return {
            "symbol": q.get("symbol", symbol),
            "last": float(q.get("last", q.get("ltp", 0))),
            "open": float(q.get("open", 0)),
            "high": float(q.get("high", 0)),
            "low": float(q.get("low", 0)),
        }
    except Exception:
        return {"symbol": symbol, "last": 0.0, "open": 0.0, "high": 0.0, "low": 0.0}


def get_historical_for_backtest(symbol: str, days: int = 60) -> pd.DataFrame:
    """
    Get historical daily/5m data for backtest when INDstocks not used.
    Uses yfinance with NSE symbol (e.g. RELIANCE.NS).
    """
    nse_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        t = yf.Ticker(nse_symbol)
        df = t.history(period=f"{max(days, 1)}d", interval="1d")
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df = df.rename(columns={"Date": "Datetime"})
        return df
    except Exception:
        return pd.DataFrame()
