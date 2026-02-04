"""
High-conviction decision engine: US bias, technicals (RSI, VWAP, EMA 9/15), consensus.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd

from . import data_fetcher


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class USBias:
    prev_close: float | None
    pct_change: float | None
    bias: int  # -1 block long first hour, 0 neutral, +1 bullish
    block_long_first_hour: bool
    date_str: str | None = None


def compute_us_bias() -> USBias:
    """
    At 9:00–9:15 AM IST: S&P 500 previous close.
    Down > 0.5% -> block Long first hour.
    Up > 1% -> Bullish +1.
    """
    prev, pct, date_str = data_fetcher.fetch_sp500_previous_close()
    if pct is None:
        return USBias(prev, None, 0, False, None)
    block = pct < -0.5
    bias = 1 if pct > 1.0 else (0 if pct >= -0.5 else -1)
    return USBias(prev, pct, bias, block, date_str)


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _vwap_from_ohlc(df: pd.DataFrame) -> pd.Series:
    if "Volume" not in df.columns or df["Volume"].sum() == 0:
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        return typical
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    return (typical * df["Volume"]).cumsum() / df["Volume"].cumsum()


def compute_technicals(df: pd.DataFrame) -> dict[str, Any]:
    """RSI, EMA9, EMA15, VWAP, and price vs EMAs."""
    if df.empty or len(df) < 20:
        return {}
    close = df["Close"] if "Close" in df.columns else df["close"]
    close = pd.Series(close).astype(float)
    rsi = _rsi(close, 14)
    ema9 = _ema(close, 9)
    ema15 = _ema(close, 15)
    last = close.iloc[-1]
    return {
        "rsi": float(rsi.iloc[-1]) if len(rsi) else None,
        "ema9": float(ema9.iloc[-1]) if len(ema9) else None,
        "ema15": float(ema15.iloc[-1]) if len(ema15) else None,
        "price": float(last),
        "ema9_cross_up": bool(ema9.iloc[-1] > ema15.iloc[-1] and len(ema9) > 1 and ema9.iloc[-2] <= ema15.iloc[-2]) if len(ema9) > 1 else False,
        "ema9_cross_down": bool(ema9.iloc[-1] < ema15.iloc[-1] and len(ema9) > 1 and ema9.iloc[-2] >= ema15.iloc[-2]) if len(ema9) > 1 else False,
    }


def technical_signal(tech: dict[str, Any], allow_long: bool) -> Signal:
    """
    RSI 40–60 neutral bias; price near VWAP/EMA; EMA 9/15 cross as entry.
    """
    rsi = tech.get("rsi")
    if rsi is not None:
        if rsi > 70:
            return Signal.SELL
        if rsi < 30:
            return Signal.BUY if allow_long else Signal.HOLD
    cross_up = tech.get("ema9_cross_up")
    cross_down = tech.get("ema9_cross_down")
    if cross_up and allow_long:
        return Signal.BUY
    if cross_down:
        return Signal.SELL
    return Signal.HOLD


def consensus_signal(
    us_bias: USBias,
    tech: dict[str, Any],
    sentiment_ok: bool,
    sentiment_buy: bool,
    is_first_hour: bool,
) -> Signal:
    """
    Only BUY when: US not blocking long (or not first hour), sentiment OK, technical says BUY.
    """
    allow_long = sentiment_ok and (not us_bias.block_long_first_hour or not is_first_hour)
    if us_bias.bias == -1 and is_first_hour:
        allow_long = False
    tech_sig = technical_signal(tech, allow_long)
    if tech_sig == Signal.BUY and (sentiment_buy or sentiment_ok):
        return Signal.BUY
    if tech_sig == Signal.SELL:
        return Signal.SELL
    return Signal.HOLD


def suggest_min_trades(df: pd.DataFrame, symbol: str) -> dict[str, Any]:
    """
    Suggest minimum number of trades per day based on stock analysis.
    Factors: volatility, average daily range, volume, price level.
    Returns: {min_trades: int, suggested_max: int, reasoning: str, factors: dict}
    """
    if df.empty or len(df) < 20:
        return {
            "min_trades": 1,
            "suggested_max": 3,
            "reasoning": "Insufficient data for analysis",
            "factors": {}
        }
    
    close = df["Close"] if "Close" in df.columns else df["close"]
    high = df["High"] if "High" in df.columns else df["high"]
    low = df["Low"] if "Low" in df.columns else df["low"]
    volume = df["Volume"] if "Volume" in df.columns else df.get("volume", pd.Series([0] * len(df)))
    
    close = pd.Series(close).astype(float)
    high = pd.Series(high).astype(float)
    low = pd.Series(low).astype(float)
    volume = pd.Series(volume).astype(float)
    
    # Calculate volatility (standard deviation of returns)
    returns = close.pct_change().dropna()
    volatility = returns.std() * 100  # As percentage
    
    # Average daily range (High - Low) as percentage
    daily_range = ((high - low) / close) * 100
    avg_daily_range = daily_range.mean()
    
    # Average volume (normalized)
    avg_volume = volume.mean()
    volume_std = volume.std()
    volume_score = min(100, (avg_volume / (volume_std + 1)) * 10) if volume_std > 0 else 50
    
    # Price level factor (higher price = more stable typically)
    current_price = float(close.iloc[-1])
    price_factor = 1.0 if current_price > 1000 else (1.2 if current_price > 500 else 1.5)
    
    # Calculate score (0-100)
    volatility_score = min(100, volatility * 20)  # Higher volatility = more opportunities
    range_score = min(100, avg_daily_range * 5)  # Higher range = more opportunities
    
    # Combined score
    combined_score = (volatility_score * 0.4 + range_score * 0.3 + min(volume_score, 50) * 0.3) * price_factor
    
    # Suggest min trades (1-5) and max trades (3-10)
    if combined_score > 70:
        min_trades = 3
        suggested_max = 8
        reasoning = "High volatility and good range - multiple trading opportunities expected"
    elif combined_score > 50:
        min_trades = 2
        suggested_max = 5
        reasoning = "Moderate volatility - decent trading opportunities"
    elif combined_score > 30:
        min_trades = 1
        suggested_max = 4
        reasoning = "Lower volatility - fewer but quality opportunities"
    else:
        min_trades = 1
        suggested_max = 3
        reasoning = "Low volatility - conservative approach recommended"
    
    return {
        "min_trades": min_trades,
        "suggested_max": suggested_max,
        "reasoning": reasoning,
        "factors": {
            "volatility_pct": round(volatility, 2),
            "avg_daily_range_pct": round(avg_daily_range, 2),
            "volume_score": round(volume_score, 1),
            "combined_score": round(combined_score, 1),
            "current_price": round(current_price, 2),
        }
    }