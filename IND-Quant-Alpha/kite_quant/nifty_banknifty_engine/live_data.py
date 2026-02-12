"""
Live price data for NIFTY 50 and BANK NIFTY only.
Uses Zerodha when available, yfinance fallback.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import yfinance as yf

from .constants import NSE_NIFTY_50, NSE_NIFTY_BANK


def _quote_to_live_index(quote: dict, _name: str) -> dict[str, Any]:
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
        from engine import zerodha_client
        q = zerodha_client.get_quote(NSE_NIFTY_50)
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
    Returns {"price", "pct_change", "date", "open"} or {}.
    """
    try:
        from engine import zerodha_client
        q = zerodha_client.get_quote(NSE_NIFTY_BANK)
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
