"""
Algo Library: load config and suggest best-fit algos from stock/market indicators.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Config paths relative to kite_quant package (parent of engine/)
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "algos.json"
_GROUPS_PATH = Path(__file__).resolve().parent.parent / "config" / "strategy_groups.json"

_algos_cache: list[dict[str, Any]] | None = None
_groups_cache: list[dict[str, Any]] | None = None
_grouped_algos_cache: dict[str, list[dict[str, Any]]] | None = None

# Intraday-only: timeframes that count as intraday for UI/engine
_INTRADAY_TIMEFRAMES = frozenset({"5m", "15m", "30m", "intraday", "5min", "15min", "30min"})
_EXCLUDE_TAGS = frozenset({"swing", "multi-day", "multi-day swing"})


def _is_intraday_executable(algo: dict[str, Any]) -> bool:
    """True if algo is executable and intraday-only (no swing/multi-day)."""
    if algo.get("executable") is not True:
        return False
    tags = algo.get("tags") or []
    tag_set = {str(t).lower().strip() for t in tags}
    if tag_set & _EXCLUDE_TAGS:
        return False
    tf = algo.get("timeframe") or []
    tf_set = {str(t).lower().strip() for t in tf}
    if not tf_set:
        return True
    if tf_set & _INTRADAY_TIMEFRAMES:
        return True
    if "1d" in tf_set or "swing" in tf_set or "1day" in tf_set:
        return False
    return True


def load_algos() -> list[dict[str, Any]]:
    """Load algo definitions from config/algos.json. Cached. Returns only intraday-executable algos."""
    global _algos_cache
    if _algos_cache is not None:
        return _algos_cache
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        algos = raw or []
        _algos_cache = [a for a in algos if _is_intraday_executable(a)]
        return _algos_cache
    except Exception:
        return []


def get_algo_by_id(algo_id: str) -> dict[str, Any] | None:
    """Return full algo dict by id."""
    for a in load_algos():
        if a.get("id") == algo_id:
            return a
    return None


def get_primary_group(algo: dict[str, Any]) -> str:
    """Return first group id for display (e.g. 'Trend Following')."""
    groups = algo.get("groups") or []
    return groups[0] if groups else ""


def load_strategy_groups() -> list[dict[str, Any]]:
    """Load strategy group definitions from config/strategy_groups.json. Cached."""
    global _groups_cache
    if _groups_cache is not None:
        return _groups_cache
    try:
        with open(_GROUPS_PATH, encoding="utf-8") as f:
            _groups_cache = json.load(f)
        return _groups_cache or []
    except Exception:
        return []


def get_algos_grouped() -> dict[str, list[dict[str, Any]]]:
    """Return { group_id: [algo, ...] }. Each algo can appear in multiple groups (cross-tagging)."""
    global _grouped_algos_cache
    if _grouped_algos_cache is not None:
        return _grouped_algos_cache
    algos = load_algos()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for a in algos:
        for gid in a.get("groups") or []:
            grouped.setdefault(gid, []).append(a)
    _grouped_algos_cache = grouped
    return grouped


def get_suggested_algos(
    stock_indicators: dict[str, Any],
    market_indicators: dict[str, Any] | None = None,
    top_n: int = 3,
) -> list[str]:
    """
    Score all algos from algos.json and return top N algo ids for current conditions.
    Used in Manual Mode (show as tags) and AI Mode (auto-pick top algo).
    """
    market_indicators = market_indicators or {}
    score_raw = stock_indicators.get("score") or 0
    prediction = (stock_indicators.get("prediction") or "NEUTRAL").upper()
    rsi = stock_indicators.get("rsi")
    sentiment_score = stock_indicators.get("sentiment_score") or 0
    # Derive trend strength from score: -1..1 scale
    trend_strength = max(-1.0, min(1.0, score_raw)) if score_raw is not None else 0
    abs_trend = abs(trend_strength)
    # Volatility: high VIX or high sentiment move
    vix_high = market_indicators.get("vix_high", False)
    volatility_high = vix_high or abs(sentiment_score) > 0.5

    def score_algo(algo: dict[str, Any]) -> float:
        aid = algo.get("id", "")
        market_type = (algo.get("marketType") or "").upper()
        conditions = algo.get("entryConditions") or {}
        s = 0.0

        # TREND algos: momentum_breakout, vwap_trend_ride, orb, pullback_continuation
        if market_type == "TREND":
            if abs_trend > 0.5:
                s += 1.0
            if abs_trend > 0.3:
                s += 0.5
            if aid == "pullback_continuation" and 0.3 < abs_trend < 0.8:
                s += 0.6
            if aid == "momentum_breakout" and abs_trend > 0.6:
                s += 0.8
            if aid == "vwap_trend_ride" and abs_trend > 0.4:
                s += 0.5
            if aid == "orb_opening_range_breakout" and market_indicators.get("session_phase") == "OPENING":
                s += 0.7
            if aid == "sector_rotation_momentum" and abs_trend > 0.4:
                s += 0.5
            if aid == "index_lead_stock_lag" and abs_trend > 0.5:
                s += 0.6
            if aid == "relative_strength_breakout" and abs_trend > 0.4:
                s += 0.5

        # RANGE algos: rsi_reversal_fade, bollinger_mean_reversion, vwap_mean_reversion, liquidity_sweep_reversal
        if market_type == "RANGE":
            if abs_trend < 0.4:
                s += 0.8
            if rsi is not None:
                if (rsi < 32 or rsi > 68) and aid == "rsi_reversal_fade":
                    s += 1.0
                if aid == "bollinger_mean_reversion":
                    s += 0.4
            if aid == "rsi_reversal_fade" and abs_trend < 0.5:
                s += 0.5
            if aid == "vwap_mean_reversion" and abs_trend < 0.5:
                s += 0.5
            if aid == "liquidity_sweep_reversal" and abs_trend < 0.6:
                s += 0.4

        # EVENT / VOLATILE / OPTIONS: news_volatility_burst, iv_expansion_play, gamma_scalping_lite, straddle_breakout, inside_bar, time_based, volume_climax
        if market_type in ("EVENT", "VOLATILE", "OPTIONS") and volatility_high:
            s += 0.9
        if aid == "news_volatility_burst" and abs(sentiment_score) > 0.4:
            s += 0.8
        if aid == "gamma_scalping_lite" and volatility_high:
            s += 0.5
        if aid == "inside_bar_breakout" and volatility_high:
            s += 0.5
        if aid == "time_based_volatility_play" and market_indicators.get("volatility_window"):
            s += 0.6
        if aid == "volume_climax_reversal" and volatility_high:
            s += 0.5

        # RSI alignment for directional algos
        if rsi is not None and market_type == "TREND":
            if prediction == "BULLISH" and rsi > 55:
                s += 0.2
            if prediction == "BEARISH" and rsi < 45:
                s += 0.2
        if rsi is not None and aid == "rsi_reversal_fade":
            if rsi < 32 or rsi > 68:
                s += 0.4

        return s

    algos = load_algos()
    scored = [(a, score_algo(a)) for a in algos]
    scored.sort(key=lambda x: -x[1])
    # Return top N with score > 0 (at least some fit)
    out = [a["id"] for a, sc in scored if sc > 0][:top_n]
    # If nothing scores, return first 2 by default (momentum + vwap as safe defaults)
    if not out and algos:
        out = [a["id"] for a in algos[:2]]
    return out
