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


def fetch_sp500_previous_close() -> tuple[float | None, float | None, str | None]:
    """
    Fetch S&P 500 (^GSPC) previous close, % change, and date.
    Returns (prev_close, pct_change, date_str) or (None, None, None) on error.
    """
    try:
        ticker = yf.Ticker("^GSPC")
        hist = ticker.history(period="5d")
        if hist.empty or len(hist) < 2:
            return None, None, None
        
        # Get data
        # We need the last CLOSED session.
        # If we are running this on Feb 4th IST (which is Feb 3rd/4th night in US),
        # hist.index[-1] might be today's date if yfinance has started a new candle or timezone issues.
        # We want to ensure we take the candle that represents the full previous session.
        
        # Check the last available date
        last_date = hist.index[-1]
        
        # Ensure we don't take "today's" candle if it's not closed.
        # Simple heuristic: if today is Feb 4, and last candle is Feb 4, ignore it.
        # But we need "today" in US time.
        
        today_us = pd.Timestamp.now(tz="America/New_York").date()
        
        # Filter out any data that is >= today_us
        # This ensures we only get closed sessions (yesterday and before)
        closed_hist = hist[hist.index.date < today_us]
        
        if closed_hist.empty:
             # Fallback if everything is filtered out (e.g. very early morning?)
             # Just take the last one available
             closed_hist = hist.iloc[[-1]]
        
        last_date = closed_hist.index[-1]
        last_close = closed_hist["Close"].iloc[-1]
        
        date_str = last_date.strftime("%Y-%m-%d")
        
        # Calculate change from the day BEFORE that.
        # We need to find the row in original 'hist' that corresponds to 'last_date'
        # and take the one before it.
        
        # Or simpler: just take the last 2 rows of 'closed_hist' if available
        if len(closed_hist) >= 2:
            prev_close = closed_hist["Close"].iloc[-2]
            pct = ((last_close - prev_close) / prev_close) * 100
        else:
            # Need to look at original hist to find the previous day
            # (e.g. if closed_hist has only 1 row because period=5d and holidays?)
            # But hist has 5 days.
            # Find index of last_date in hist
            loc = hist.index.get_loc(last_date)
            if loc > 0:
                prev_close = hist["Close"].iloc[loc-1]
                pct = ((last_close - prev_close) / prev_close) * 100
            else:
                pct = None
        
        return float(last_close), float(pct) if pct is not None else None, date_str
    except Exception:
        return None, None, None


def fetch_us_futures() -> dict[str, Any]:
    """
    Fetch live S&P 500 Futures (ES=F) data.
    Returns {price, pct_change, date_str} or {} on error.
    """
    try:
        # ES=F is S&P 500 Futures
        ticker = yf.Ticker("ES=F")
        # Get fast data (1d is usually enough for current price if market is open/electronic)
        # For futures, we want the latest price.
        df = ticker.history(period="2d", interval="5m")
        
        if df.empty:
            # Try daily if 5m fails
            df = ticker.history(period="2d", interval="1d")
        
        if df.empty:
            return {}
            
        last_price = float(df["Close"].iloc[-1])
        
        # Calculate change from previous close (yesterday's close)
        # yfinance provides 'previousClose' in info, but it's often delayed or None.
        # Better to calculate from history if possible.
        
        # If we have intraday data, we need yesterday's close.
        # But getting yesterday's close from 5m data is tricky if we only fetched 2d.
        # Let's fetch daily history separately for the reference close.
        daily = ticker.history(period="5d", interval="1d")
        if len(daily) >= 2:
             # The 'last' row in daily might be 'today' (incomplete).
             # So we want the close of the row BEFORE the last one?
             # Or if 'today' is a new day, we want yesterday's close.
             
             # Check if the last daily candle is today.
             last_daily_date = daily.index[-1].date()
             today_date = pd.Timestamp.now(tz="America/New_York").date()
             
             if last_daily_date == today_date:
                 prev_close = float(daily["Close"].iloc[-2])
             else:
                 prev_close = float(daily["Close"].iloc[-1])
        else:
             prev_close = last_price # Fallback
             
        pct_change = ((last_price - prev_close) / prev_close) * 100 if prev_close else 0.0
        
        return {
            "price": last_price,
            "pct_change": round(pct_change, 2),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    except Exception:
        return {}


def fetch_nifty50_live() -> dict[str, Any]:
    """
    Fetch live Nifty 50 index data (^NSEI) from yfinance with real-time updates.
    Returns {"price": float, "pct_change": float, "date": str, "open": float} or empty dict on error.
    """
    try:
        ticker = yf.Ticker("^NSEI")  # Nifty 50 index
        
        # Get intraday data (1-minute intervals) for real-time updates
        data = ticker.history(period="1d", interval="1m")
        if data.empty:
            # Fallback to daily data if intraday fails
            data = ticker.history(period="1d")
            if data.empty:
                return {}
        
        latest_candle = data.iloc[-1]
        first_candle = data.iloc[0]  # First candle of the day for open price
        
        current_price = latest_candle["Close"]
        open_price = first_candle["Open"]  # Day's opening price
        
        pct_change = ((current_price - open_price) / open_price) * 100 if open_price else None
        
        date_obj = latest_candle.name  # The index is the timestamp
        date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "price": float(current_price),
            "open": float(open_price),
            "pct_change": float(pct_change) if pct_change is not None else None,
            "date": date_str
        }
    except Exception:
        return {}


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
