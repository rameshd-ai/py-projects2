"""
Data fetcher: Zerodha preferred for all NSE data (quotes, indices, history).
yfinance fallback for NSE when Zerodha unavailable; yfinance only for US (S&P 500, ES futures).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
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


# Re-export from nifty_banknifty_engine so existing imports keep working.
# All NIFTY/BANKNIFTY logic lives in nifty_banknifty_engine.
def fetch_nifty50_live() -> dict[str, Any]:
    """Fetch live Nifty 50. Delegates to nifty_banknifty_engine."""
    from nifty_banknifty_engine.live_data import fetch_nifty50_live as _fetch
    return _fetch()


def fetch_bank_nifty_live() -> dict[str, Any]:
    """Fetch live Bank Nifty. Delegates to nifty_banknifty_engine."""
    from nifty_banknifty_engine.live_data import fetch_bank_nifty_live as _fetch
    return _fetch()


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
    import logging
    logger = logging.getLogger(__name__)
    
    print(f"[CANDLE FETCH] START: symbol={symbol}, interval={interval}, period={period}", flush=True)
    logger.info(f"fetch_nse_ohlc called: symbol={symbol}, interval={interval}, period={period}")
    
    try:
        from . import zerodha_client
        print(f"[CANDLE FETCH] Getting Kite client...", flush=True)
        kite = zerodha_client._get_kite()
        
        if not kite:
            print(f"[CANDLE FETCH] ERROR: No Kite client!", flush=True)
            logger.warning("No Kite client available")
            return pd.DataFrame()
        
        print(f"[CANDLE FETCH] Kite client OK", flush=True)
        
        # Map interval to Kite format (Zerodha uses "5minute" not "minute5")
        interval_map = {
            "1m": "minute",
            "3m": "3minute",
            "5m": "5minute",
            "15m": "15minute",
            "30m": "30minute",
            "1h": "60minute",
            "1d": "day",
        }
        kite_interval = interval_map.get(interval, "5minute")
        
        # Get instrument token
        # For indices like "NIFTY 50", match by name or tradingsymbol
        import logging
        logger = logging.getLogger(__name__)
        
        # Get instruments list (will be cached at kiteconnect level)
        print(f"[CANDLE FETCH] Fetching instruments list...", flush=True)
        try:
            instruments = kite.instruments("NSE")
            print(f"[CANDLE FETCH] Got {len(instruments)} instruments", flush=True)
        except Exception as e:
            print(f"[CANDLE FETCH] ERROR fetching instruments: {e}", flush=True)
            logger.exception(f"Failed to fetch instruments list for {symbol}: {e}")
            return pd.DataFrame()
            
        instrument_token = None
        symbol_upper = symbol.upper()
        
        print(f"[CANDLE FETCH] Searching for: {symbol_upper}", flush=True)
        logger.info(f"Searching for instrument: {symbol_upper} among {len(instruments)} NSE instruments")
        
        # First try exact tradingsymbol match
        for inst in instruments:
            if inst.get("tradingsymbol", "").upper() == symbol_upper:
                instrument_token = inst["instrument_token"]
                logger.info(f"✓ Found by tradingsymbol: token={instrument_token}, {inst.get('name')}")
                break
        
        # If not found, try name match for indices
        if not instrument_token:
            for inst in instruments:
                if inst.get("name", "").upper() == symbol_upper:
                    instrument_token = inst["instrument_token"]
                    logger.info(f"✓ Found by name: token={instrument_token}, tradingsymbol={inst.get('tradingsymbol')}")
                    break
        
        if not instrument_token:
            logger.error(f"✗ Could not find instrument token for: {symbol}")
            logger.error(f"Sample instruments: {[{k: v for k, v in inst.items() if k in ['name', 'tradingsymbol', 'instrument_type']} for inst in instruments[:5]]}")
            return pd.DataFrame()
        
        logger.info(f"Using instrument_token={instrument_token} for {symbol}")
        
        # Calculate from/to dates based on period
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        to_date = datetime.now(ZoneInfo("Asia/Kolkata"))
        
        # For intraday intervals, fetch from market open (9:15 AM IST) to capture full day's movement
        if "minute" in kite_interval.lower() and period == "1d":
            # Fetch from today's market open at 9:15 AM IST
            today_market_open = to_date.replace(hour=9, minute=15, second=0, microsecond=0)
            if to_date.time() < today_market_open.time():
                # Before market open - fetch from previous trading day
                from_date = (today_market_open - timedelta(days=1))
            else:
                # After market open - fetch from today's 9:15 AM
                from_date = today_market_open
        elif period == "1d":
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
        print(f"[CANDLE FETCH] Calling historical_data: token={instrument_token}, from={from_date}, to={to_date}, interval={kite_interval}", flush=True)
        logger.info(f"Fetching historical: token={instrument_token}, from={from_date}, to={to_date}, interval={kite_interval}")
        
        data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=kite_interval
        )
        
        print(f"[CANDLE FETCH] Received {len(data) if data else 0} records", flush=True)
        logger.info(f"Received {len(data) if data else 0} candle records from Zerodha")
        
        if not data:
            print(f"[CANDLE FETCH] ERROR: Empty data!", flush=True)
            logger.error(f"No historical data returned from Zerodha for {symbol}")
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
        
        logger.info(f"Successfully fetched {len(df)} candles for {symbol}")
        return df
    except Exception as e:
        logger.exception(f"Error fetching OHLC for {symbol}: {str(e)}")
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


def get_ohlc_for_date(symbol: str, target_date) -> dict:
    """
    Get open/close and % change for a specific calendar date (for backfilling actual).
    Uses yfinance with start/end window. Returns {"open", "close", "pct_change"} or {} if not found.
    """
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)
    start = (target_date - timedelta(days=10)).isoformat()
    end = (target_date + timedelta(days=3)).isoformat()
    nse_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        t = yf.Ticker(nse_symbol)
        df = t.history(start=start, end=end, interval="1d")
        if df.empty or len(df) < 1:
            return {}
        df = df.reset_index()
        if "Date" not in df.columns and "Datetime" in df.columns:
            df["Date"] = pd.to_datetime(df["Datetime"]).dt.date
        elif "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"]).dt.date
        else:
            return {}
        row = df[df["Date"].astype(str) == target_date.isoformat()]
        if row.empty:
            return {}
        r = row.iloc[0]
        o = float(r.get("Open", 0))
        c = float(r.get("Close", 0))
        if not o or o == 0:
            return {}
        pct = ((c - o) / o) * 100
        return {"open": o, "close": c, "pct_change": round(pct, 2)}
    except Exception:
        return {}
