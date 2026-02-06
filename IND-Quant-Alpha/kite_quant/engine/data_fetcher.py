"""
Data fetcher: Zerodha preferred for all NSE data (quotes, indices, history).
yfinance fallback for NSE when Zerodha unavailable; yfinance only for US (S&P 500, ES futures).
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
    Fetch S&P 500 (^GSPC) previous close, % change, and date (US session date).
    Returns (prev_close, pct_change, date_str) or (None, None, None) on error.
    Uses US Eastern to decide "last closed" session so India morning sees latest US close.
    """
    try:
        ticker = yf.Ticker("^GSPC")
        hist = ticker.history(period="5d")
        if hist.empty or len(hist) < 2:
            return None, None, None
        
        # yfinance index is often UTC; convert to US Eastern to get correct "last closed" session
        idx = hist.index
        if idx.tz is None:
            idx = idx.tz_localize("UTC", ambiguous="infer")
        idx_us = idx.tz_convert("America/New_York")
        now_et = pd.Timestamp.now(tz="America/New_York")
        today_us = now_et.date()
        # After 4 PM ET on a weekday, today's US session is closed — include it so date shows 5th when it's 5th in USA
        market_closed_today = (now_et.hour > 16 or (now_et.hour == 16 and now_et.minute >= 0)) and now_et.weekday() < 5
        if market_closed_today:
            closed_mask = pd.Series(idx_us.date, index=hist.index) <= today_us
        else:
            closed_mask = pd.Series(idx_us.date, index=hist.index) < today_us
        closed_hist = hist.loc[closed_mask]
        
        if closed_hist.empty:
            closed_hist = hist.iloc[[-1]]
        last_ts = closed_hist.index[-1]
        if getattr(last_ts, "tz", None) is None:
            last_ts = pd.Timestamp(last_ts).tz_localize("UTC", ambiguous="infer").tz_convert("America/New_York")
        else:
            last_ts = last_ts.tz_convert("America/New_York")
        last_us_date = last_ts.date()
        # Sanity: never show a future date (e.g. bad yfinance year or TZ edge case)
        if last_us_date > today_us or last_us_date.year > datetime.now().year:
            last_us_date = today_us - timedelta(days=1)
        date_str = last_us_date.strftime("%Y-%m-%d")
        
        last_close = closed_hist["Close"].iloc[-1]
        
        if len(closed_hist) >= 2:
            prev_close = closed_hist["Close"].iloc[-2]
            pct = ((last_close - prev_close) / prev_close) * 100
        else:
            loc = hist.index.get_loc(closed_hist.index[-1])
            if loc > 0:
                prev_close = hist["Close"].iloc[loc - 1]
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


def _quote_to_live_index(quote: dict, name: str) -> dict[str, Any]:
    """Build {price, pct_change, date, open} from Zerodha quote dict."""
    last = quote.get("last", 0) or 0
    open_p = quote.get("open", 0) or 0
    if not last and not open_p:
        return {}
    pct = ((float(last) - float(open_p)) / float(open_p)) * 100 if open_p else None
    return {
        "price": float(last),
        "open": float(open_p),
        "pct_change": round(pct, 4) if pct is not None else None,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch_nifty50_live() -> dict[str, Any]:
    """
    Fetch live Nifty 50. Prefers Zerodha (NSE:NIFTY 50); falls back to yfinance.
    Returns {"price", "pct_change", "date", "open"} or {}.
    """
    try:
        from . import zerodha_client
        q = zerodha_client.get_quote("NIFTY 50")
        if q and (q.get("last") or q.get("open")):
            return _quote_to_live_index(q, "Nifty 50")
    except Exception:
        pass
    try:
        ticker = yf.Ticker("^NSEI")
        data = ticker.history(period="1d", interval="1m")
        if data.empty:
            data = ticker.history(period="1d")
        if data.empty:
            return {}
        latest_candle = data.iloc[-1]
        first_candle = data.iloc[0]
        current_price = latest_candle["Close"]
        open_price = first_candle["Open"]
        pct_change = ((current_price - open_price) / open_price) * 100 if open_price else None
        return {
            "price": float(current_price),
            "open": float(open_price),
            "pct_change": float(pct_change) if pct_change is not None else None,
            "date": latest_candle.name.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception:
        return {}


def fetch_bank_nifty_live() -> dict[str, Any]:
    """
    Fetch live Bank Nifty. Prefers Zerodha (NSE:NIFTY BANK); falls back to yfinance.
    """
    try:
        from . import zerodha_client
        q = zerodha_client.get_quote("NIFTY BANK")
        if q and (q.get("last") or q.get("open")):
            return _quote_to_live_index(q, "Bank Nifty")
    except Exception:
        pass
    try:
        ticker = yf.Ticker("^NSEBANK")
        data = ticker.history(period="1d", interval="1m")
        if data.empty:
            data = ticker.history(period="1d")
        if data.empty:
            return {}
        latest = data.iloc[-1]
        open_p = data.iloc[0]["Open"] if "Open" in data.columns else data.iloc[0]["Close"]
        curr = latest["Close"]
        pct = ((curr - open_p) / open_p) * 100 if open_p else None
        return {
            "price": float(curr),
            "pct_change": float(pct) if pct is not None else None,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(open_p),
        }
    except Exception:
        return {}


def fetch_india_vix() -> dict[str, Any]:
    """
    Fetch India VIX. Prefers Zerodha (NSE:INDIA VIX); falls back to yfinance.
    Returns {"vix_value": float}.
    """
    try:
        from . import zerodha_client
        q = zerodha_client.get_quote("INDIA VIX")
        if q and q.get("last"):
            return {"vix_value": float(q["last"])}
    except Exception:
        pass
    try:
        ticker = yf.Ticker("^INDIAVIX")
        data = ticker.history(period="1d")
        if not data.empty:
            return {"vix_value": float(data.iloc[-1]["Close"])}
    except Exception:
        pass
    return {"vix_value": 16.5}


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
        elif period == "30d":
            from_date = to_date - timedelta(days=30)
        elif period == "60d":
            from_date = to_date - timedelta(days=60)
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
    Get historical daily data for backtest. Prefers Zerodha when connected;
    falls back to yfinance (NSE symbol e.g. RELIANCE.NS).
    """
    period = "1d" if days <= 1 else ("5d" if days <= 5 else ("30d" if days <= 30 else "60d"))
    try:
        df = fetch_nse_ohlc(symbol, interval="1d", period=period)
        if df is not None and not df.empty and len(df) >= 1:
            return df
    except Exception:
        pass
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


def get_historical_for_prediction(symbol: str, days: int = 60) -> pd.DataFrame:
    """
    Get historical daily data for prediction (RSI, EMA). Prefers Zerodha when
    connected (exchange data); falls back to yfinance. Use 60+ days so
    compute_technicals() has enough rows (needs >= 20).
    """
    period_map = {"1d": "1d", "5d": "5d", "30d": "30d", "60d": "60d"}
    period = period_map.get(f"{days}d", "60d")
    df = fetch_nse_ohlc(symbol, interval="1d", period=period)
    if df is not None and not df.empty and len(df) >= 20:
        return df
    return get_historical_for_backtest(symbol, days=days)
