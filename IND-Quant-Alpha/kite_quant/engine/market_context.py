"""
Market regime detection: run periodically (e.g. once per minute) to tag market state.
Use in engine to enable/disable strategies dynamically. NOT a strategy — engine-level.
"""
from __future__ import annotations

from datetime import time
# Regimes that can drive strategy filtering
TREND = "TREND"
RANGE = "RANGE"
VOLATILE = "VOLATILE"
CLOSING_VOLATILITY = "CLOSING_VOLATILITY"
NEUTRAL = "NEUTRAL"
EXPIRY = "EXPIRY"
LOW_LIQUIDITY = "LOW_LIQUIDITY"


def detect_market_regime(
    *,
    vix: float | None = None,
    atr_pct: float | None = None,
    trend_strength: float | None = None,
    current_time: time | None = None,
    atr_range_threshold: float = 0.005,
    vix_volatile_threshold: float = 18.0,
) -> str:
    """
    Tag current market regime from available inputs.
    Call once per minute from session engine; use result to filter allowed strategies.

    Example usage in engine:
        regime = detect_market_regime(
            vix=india_vix,
            atr_pct=recent_atr_pct,
            trend_strength=technicals.get("trend_strength"),
            current_time=datetime.now().time(),
        )
        if regime == RANGE:
            allowed_strategies = ["bollinger_mean_reversion", "vwap_mean_reversion"]
    """
    now = current_time
    if now is not None:
        if now >= time(14, 30):
            return CLOSING_VOLATILITY

    if vix is not None and vix > vix_volatile_threshold:
        return VOLATILE

    if trend_strength is not None and trend_strength > 0.7:
        return TREND

    if atr_pct is not None and atr_pct < atr_range_threshold:
        return RANGE

    return NEUTRAL


def get_allowed_strategy_ids_for_regime(regime: str) -> list[str] | None:
    """
    Optional: return list of algo/strategy ids preferred for this regime.
    None = no filter (all strategies allowed). Engine can use this to narrow choices.
    """
    if regime == RANGE:
        return ["bollinger_mean_reversion", "vwap_mean_reversion", "liquidity_sweep_reversal"]
    if regime == TREND:
        return [
            "momentum_breakout",
            "vwap_trend_ride",
            "pullback_continuation",
            "relative_strength_breakout",
            "trend_day_vwap_hold",
        ]
    if regime == VOLATILE or regime == CLOSING_VOLATILITY:
        return [
            "news_volatility_burst",
            "time_based_volatility_play",
            "volume_climax_reversal",
            "range_compression_breakout",
        ]
    return None
