"""
Index market bias for NIFTY and BANKNIFTY only.
Uses live index, VIX, optional US close, optional 5m OHLC. Cached 60s.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .live_data import fetch_nifty50_live, fetch_bank_nifty_live

_cache: dict | None = None
_cache_time: datetime | None = None
CACHE_TTL = timedelta(seconds=60)


def get_index_market_bias(us_bias_data: dict | None = None) -> dict[str, Any]:
    """
    AI market bias for NIFTY and BANKNIFTY. Uses live index, VIX, optional US close, 5m trend.
    Returns: niftyBias, bankNiftyBias, confidence, reasons. Cached 60s.
    us_bias_data: optional dict with sp500_pct_change (from app _get_cached_us_bias or similar).
    """
    global _cache, _cache_time
    now = datetime.now()
    if _cache is not None and _cache_time is not None and (now - _cache_time) < CACHE_TTL:
        return _cache

    from engine.data_fetcher import fetch_nse_ohlc, fetch_india_vix

    reasons = []
    nifty_score = 0.0
    bank_nifty_score = 0.0

    nifty = fetch_nifty50_live()
    bank_nifty = fetch_bank_nifty_live()
    vix_data = fetch_india_vix()
    us_bias_data = us_bias_data or {}

    nifty_price = (nifty.get("price") or 0) or (nifty.get("open") or 0)
    nifty_open = nifty.get("open") or nifty_price
    nifty_pct = nifty.get("pct_change") or 0

    bn_price = (bank_nifty.get("price") or 0) or (bank_nifty.get("open") or 0)
    bn_open = bank_nifty.get("open") or bn_price
    bn_pct = bank_nifty.get("pct_change") or 0

    if nifty_price > 0 and nifty_open > 0:
        if nifty_price > nifty_open:
            nifty_score += 0.35
            reasons.append("Nifty above open (VWAP proxy)")
        else:
            nifty_score -= 0.35
            reasons.append("Nifty below open")

    if bn_price > 0 and bn_open > 0:
        if bn_price > bn_open:
            bank_nifty_score += 0.35
            if "Nifty above open" not in " ".join(reasons):
                reasons.append("Bank Nifty above open")
        else:
            bank_nifty_score -= 0.35

    try:
        df_nifty_5m = fetch_nse_ohlc("NIFTY 50", interval="5m", period="1d")
        if df_nifty_5m is not None and not df_nifty_5m.empty and len(df_nifty_5m) >= 2:
            last_c = float(df_nifty_5m["Close"].iloc[-1])
            prev_c = float(df_nifty_5m["Close"].iloc[-2])
            if last_c > prev_c:
                nifty_score += 0.2
                reasons.append("Nifty 5m higher close")
            else:
                nifty_score -= 0.2
        df_bn_5m = fetch_nse_ohlc("NIFTY BANK", interval="5m", period="1d")
        if df_bn_5m is not None and not df_bn_5m.empty and len(df_bn_5m) >= 2:
            last_c = float(df_bn_5m["Close"].iloc[-1])
            prev_c = float(df_bn_5m["Close"].iloc[-2])
            if last_c > prev_c:
                bank_nifty_score += 0.2
            else:
                bank_nifty_score -= 0.2
    except Exception:
        pass

    if nifty_pct and nifty_pct > 0:
        nifty_score += 0.2
        if "Strong breadth" not in " ".join(reasons):
            reasons.append("Strong breadth (index green)")
    elif nifty_pct is not None and nifty_pct < 0:
        nifty_score -= 0.2

    if bn_pct and bn_pct > 0:
        bank_nifty_score += 0.2
    elif bn_pct is not None and bn_pct < 0:
        bank_nifty_score -= 0.2

    if nifty_pct is not None and bn_pct is not None and bn_pct > nifty_pct:
        bank_nifty_score += 0.25
        reasons.append("Banks leading")
    elif nifty_pct is not None and bn_pct is not None and bn_pct < nifty_pct:
        bank_nifty_score -= 0.2

    us_pct = us_bias_data.get("sp500_pct_change")
    if us_pct is not None:
        if us_pct > 0:
            nifty_score += 0.15
            bank_nifty_score += 0.15
            reasons.append("Positive global cues")
        elif us_pct < -0.5:
            nifty_score -= 0.15
            bank_nifty_score -= 0.15

    vix_val = vix_data.get("vix_value")
    if vix_val is not None:
        if vix_val > 18:
            reasons.append("Elevated VIX (breakout potential)")
        if vix_val < 12:
            reasons.append("Low VIX (range-bound)")

    def to_bias(score: float) -> str:
        if score > 0.2:
            return "BULLISH"
        if score < -0.2:
            return "BEARISH"
        return "NEUTRAL"

    nifty_bias = to_bias(nifty_score)
    bank_nifty_bias = to_bias(bank_nifty_score)

    if vix_val is not None and vix_val < 11 and nifty_bias == "NEUTRAL" and bank_nifty_bias == "NEUTRAL":
        reasons.append("Market lacks clear direction. Wait for better setup.")

    confidence = min(100, max(0, int(50 + (abs(nifty_score) + abs(bank_nifty_score)) * 25)))
    if not reasons:
        reasons.append("Index vs open and trend")

    out = {
        "niftyBias": nifty_bias,
        "bankNiftyBias": bank_nifty_bias,
        "confidence": confidence,
        "reasons": reasons[:6],
        "niftyScore": round(nifty_score, 2),
        "bankNiftyScore": round(bank_nifty_score, 2),
        "vixValue": vix_val,
    }
    _cache = out
    _cache_time = now
    return out
