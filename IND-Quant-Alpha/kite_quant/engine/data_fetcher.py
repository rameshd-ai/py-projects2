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
    Fetch NSE OHLC for symbol. Uses Zerodha Kite Connect if credentials given,
    else returns empty for backtest to fill from yfinance.
    """
    try:
        from . import zerodha_client
        kite = zerodha_client._get_kite()
        
        if not kite:
            # No credentials: return empty for backtest to fill from CSV/yfinance
            return pd.DataFrame()
        
        # Map interval to Kite format
        interval_map = {
            "1m": "minute",
            "3m": "minute3",
            "5m": "minute5",
            "15m": "minute15",
            "30m": "minute30",
            "1h": "hour",
            "1d": "day",
        }
        kite_interval = interval_map.get(interval, "minute5")
        
        # Get instrument token
        instruments = kite.instruments("NSE")
        instrument_token = None
        for inst in instruments:
            if inst["tradingsymbol"] == symbol.upper():
                instrument_token = inst["instrument_token"]
                break
        
        if not instrument_token:
            return pd.DataFrame()
        
        # Calculate from/to dates based on period
        from datetime import datetime, timedelta
        to_date = datetime.now()
        if period == "1d":
            from_date = to_date - timedelta(days=1)
        elif period == "5d":
            from_date = to_date - timedelta(days=5)
        else:
            from_date = to_date - timedelta(days=60)
        
        # Fetch historical data
        data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=kite_interval
        )
        
        if not data:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        df = df.rename(columns={
            "date": "Datetime",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        })
        
        if "Datetime" in df.columns:
            df["Datetime"] = pd.to_datetime(df["Datetime"])
        
        return df
    except Exception:
        return pd.DataFrame()


def fetch_nse_quote(
    symbol: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Fetch current quote for symbol from Zerodha Kite (or mock)."""
    try:
        from . import zerodha_client
        return zerodha_client.get_quote(symbol)
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
