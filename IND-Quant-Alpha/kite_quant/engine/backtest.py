"""
Backtest mode: historical candles -> strategy decisions -> results.csv.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

from . import data_fetcher
from . import sentiment_engine
from . import strategy
from .session_manager import STOP_LOSS_PCT, TAKE_PROFIT_PCT


def run_backtest(
    symbol: str = "RELIANCE",
    days: int = 60,
    output_csv: str | None = None,
) -> list[dict]:
    """
    Run strategy on historical data; log decisions to results.csv (no real orders).
    """
    output_csv = output_csv or os.path.join(os.path.dirname(__file__), "..", "results.csv")
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = data_fetcher.get_historical_for_backtest(symbol, days=days)
    if df.empty or len(df) < 20:
        return []

    # Normalize columns
    if "Close" not in df.columns and "close" in df.columns:
        df = df.rename(columns={"close": "Close", "high": "High", "low": "Low", "open": "Open"})
    if "Volume" not in df.columns:
        df["Volume"] = 0

    us_bias = strategy.compute_us_bias()
    sent = sentiment_engine.get_sentiment_for_symbol(symbol)
    trades_today = 0
    results = []
    fieldnames = ["timestamp", "symbol", "signal", "price", "reason", "us_bias", "sentiment", "trades_today"]

    for i in range(19, len(df)):
        row = df.iloc[i]
        window = df.iloc[: i + 1]
        tech = strategy.compute_technicals(window)
        if not tech:
            continue
        is_first_hour = True  # simplified for daily backtest
        sig = strategy.consensus_signal(
            us_bias,
            tech,
            sentiment_ok=not sent.get("blacklist_24h", False),
            sentiment_buy=sent.get("buy_strong", False) or sent.get("score", 0) > 0.2,
            is_first_hour=is_first_hour,
        )
        if trades_today >= 3:
            sig = strategy.Signal.HOLD
        ts = row.get("Datetime", df.index[i])
        if hasattr(ts, "isoformat"):
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        else:
            ts_str = str(ts)
        price = tech.get("price", 0)
        reason = f"RSI={tech.get('rsi')}, EMA9/15 cross"
        if sig != strategy.Signal.HOLD:
            trades_today += 1
        results.append({
            "timestamp": ts_str,
            "symbol": symbol,
            "signal": sig.value,
            "price": price,
            "reason": reason,
            "us_bias": us_bias.bias,
            "sentiment": sent.get("score", 0),
            "trades_today": trades_today,
        })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)

    return results
