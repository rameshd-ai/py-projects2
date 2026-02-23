"""
AI-powered strategy advisor: Uses GPT to analyze market conditions and recommend best strategy.
Dynamically switches strategies based on real-time market analysis.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)
_GOVERNANCE_PROMPT_PATH = Path(__file__).resolve().parents[2] / "ai_governance_prompt.txt"
MIN_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
MIN_CONFIDENCE_REQUIRED = "medium"


def _load_governance_prompt() -> str:
    """Load governance prompt text; startup must fail if missing."""
    if not _GOVERNANCE_PROMPT_PATH.exists():
        raise RuntimeError(
            f"Missing mandatory governance prompt file: {_GOVERNANCE_PROMPT_PATH}"
        )
    text = _GOVERNANCE_PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(
            f"Governance prompt file is empty: {_GOVERNANCE_PROMPT_PATH}"
        )
    return text


def _reject_recommendation(reason: str) -> dict[str, Any]:
    """Standard fail-closed AI reject payload."""
    return {
        "decision": "REJECT",
        "recommended_strategy": None,
        "confidence": "low",
        "reasoning": reason,
        "switch_from_current": False,
        "market_assessment": "AI validation rejected",
        "market_bias": "reject",
        "rejected": True,
    }


# Abort system startup if governance prompt is not available.
_GOVERNANCE_PROMPT_BOOTSTRAP = _load_governance_prompt()

# All available strategies with their characteristics
STRATEGY_PROFILES = {
    "Momentum Breakout": {
        "id": "momentum_breakout",
        "best_for": "Strong trending markets with clear breakouts",
        "requires": "High volume, clear price momentum, breakout above resistance",
        "timeframe": "5-15 min",
    },
    "VWAP Trend Ride": {
        "id": "vwap_trend_ride",
        "best_for": "Sustained trending days with VWAP as support/resistance",
        "requires": "Clear trend, price respecting VWAP levels",
        "timeframe": "5-30 min",
    },
    "RSI Reversal Fade": {
        "id": "rsi_reversal_fade",
        "best_for": "Overbought/oversold reversals in ranging markets",
        "requires": "RSI extremes (>70 or <30), ranging market",
        "timeframe": "5-15 min",
    },
    "Bollinger Mean Reversion": {
        "id": "bollinger_mean_reversion",
        "best_for": "Range-bound markets with mean reversion tendency",
        "requires": "Low volatility, price at Bollinger band extremes",
        "timeframe": "5-15 min",
    },
    "Pullback Continuation": {
        "id": "pullback_continuation",
        "best_for": "Trending markets with healthy pullbacks",
        "requires": "Established trend, pullback to VWAP or support",
        "timeframe": "5-30 min",
    },
    "EMA Ribbon Trend Alignment": {
        "id": "ema_ribbon_trend_alignment",
        "best_for": "Strong trending markets with EMA alignment",
        "requires": "Multiple EMAs aligned, strong directional move",
        "timeframe": "15-60 min",
    },
    "VWAP Reclaim": {
        "id": "vwap_reclaim",
        "best_for": "Trend reversal when price reclaims VWAP",
        "requires": "VWAP reclaim, volume confirmation",
        "timeframe": "5-15 min",
    },
    "News Volatility Burst": {
        "id": "news_volatility_burst",
        "best_for": "High volatility events, news-driven moves",
        "requires": "VIX spike, sudden volatility increase",
        "timeframe": "1-5 min",
    },
    "Volume Climax Reversal": {
        "id": "volume_climax_reversal",
        "best_for": "Exhaustion reversals after climax volume",
        "requires": "Volume spike, price exhaustion",
        "timeframe": "5-15 min",
    },
    "Range Compression Breakout": {
        "id": "range_compression_breakout",
        "best_for": "Breakouts after tight consolidation",
        "requires": "Low ATR, tight range, building momentum",
        "timeframe": "5-15 min",
    },
    "Liquidity Sweep Reversal": {
        "id": "liquidity_sweep_reversal",
        "best_for": "Reversal after stop-loss hunting",
        "requires": "False breakout, liquidity grab, quick reversal",
        "timeframe": "5-15 min",
    },
    "Time-Based Volatility Play": {
        "id": "time_based_volatility_play",
        "best_for": "Market open and close volatility",
        "requires": "Specific time windows (9:15-9:45, 14:30-15:15)",
        "timeframe": "5-15 min",
    },
}


def get_market_context(
    nifty_price: float | None = None,
    nifty_change_pct: float | None = None,
    banknifty_price: float | None = None,
    banknifty_change_pct: float | None = None,
    vix: float | None = None,
    current_time: str | None = None,
    recent_candles: list[dict] | None = None,
    expiry_type: str | None = None,
) -> dict[str, Any]:
    """
    Gather comprehensive market context for AI analysis.
    """
    context = {
        "timestamp": current_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nifty": {
            "price": nifty_price,
            "change_pct": nifty_change_pct,
        },
        "banknifty": {
            "price": banknifty_price,
            "change_pct": banknifty_change_pct,
        },
        "vix": vix,
        "expiry": {
            "is_expiry_day": bool(expiry_type),
            "type": (str(expiry_type).upper() if expiry_type else None),
        },
    }

    def _f(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return float(default)

    # Analyze recent price action
    if recent_candles and len(recent_candles) >= 5:
        recent_5 = recent_candles[-5:]
        avg_volume = sum(c.get("volume", 0) for c in recent_5) / len(recent_5)
        last_candle = recent_5[-1]
        
        context["price_action"] = {
            "trend": "bullish" if recent_5[-1]["close"] > recent_5[0]["close"] else "bearish",
            "avg_volume": avg_volume,
            "latest_volume": last_candle.get("volume", 0),
            "volume_spike": last_candle.get("volume", 0) > avg_volume * 1.5,
            "range_high": max(c["high"] for c in recent_5),
            "range_low": min(c["low"] for c in recent_5),
        }

    # Compact intraday session features (better than raw 12h candle dump for intraday).
    if recent_candles and len(recent_candles) >= 10:
        candles = recent_candles[-75:]  # full current session window (~6h15m @ 5m)
        opens = [_f(c.get("open")) for c in candles]
        highs = [_f(c.get("high")) for c in candles]
        lows = [_f(c.get("low")) for c in candles]
        closes = [_f(c.get("close")) for c in candles]
        vols = [_f(c.get("volume")) for c in candles]
        if closes and highs and lows and opens:
            session_open = opens[0]
            session_close = closes[-1]
            session_high = max(highs)
            session_low = min(lows)
            session_range = max(session_high - session_low, 1e-9)
            session_change_pct = ((session_close - session_open) / max(session_open, 1e-9)) * 100.0
            dist_to_high_pct = ((session_high - session_close) / max(session_close, 1e-9)) * 100.0
            dist_to_low_pct = ((session_close - session_low) / max(session_close, 1e-9)) * 100.0
            typical = [((h + l + c) / 3.0) for h, l, c in zip(highs, lows, closes)]
            vol_sum = sum(vols)
            vwap = (sum(tp * v for tp, v in zip(typical, vols)) / vol_sum) if vol_sum > 0 else session_close
            vwap_side = "above" if session_close > vwap else ("below" if session_close < vwap else "at")
            first_n = min(len(candles), 12)  # first hour for 5m candles
            first_hour_high = max(highs[:first_n])
            first_hour_low = min(lows[:first_n])
            first_hour_breakout = (
                "up"
                if session_close > first_hour_high
                else ("down" if session_close < first_hour_low else "inside")
            )
            avg_vol_session = (vol_sum / len(vols)) if vols else 0.0
            recent_n = min(len(vols), 6)
            avg_vol_recent = (sum(vols[-recent_n:]) / recent_n) if recent_n > 0 else 0.0
            vol_regime = (
                "high"
                if avg_vol_recent > (avg_vol_session * 1.25)
                else ("low" if avg_vol_recent < (avg_vol_session * 0.8) else "normal")
            )
            context["session_features"] = {
                "candles_used": len(candles),
                "session_change_pct": round(session_change_pct, 2),
                "session_range_pct": round((session_range / max(session_open, 1e-9)) * 100.0, 2),
                "distance_to_day_high_pct": round(dist_to_high_pct, 2),
                "distance_to_day_low_pct": round(dist_to_low_pct, 2),
                "vwap": round(vwap, 2),
                "vwap_side": vwap_side,
                "first_hour_breakout": first_hour_breakout,
                "vol_regime": vol_regime,
            }
    
    return context


def build_gpt_prompt(context: dict[str, Any], current_strategy: str | None = None) -> str:
    """
    Build GPT prompt for strategy recommendation.
    """
    strategies_info = "\n".join([
        f"- {name}: {info['best_for']} (Requires: {info['requires']})"
        for name, info in STRATEGY_PROFILES.items()
    ])
    nifty = (context or {}).get("nifty") or {}
    banknifty = (context or {}).get("banknifty") or {}
    expiry = (context or {}).get("expiry") or {}
    perf = (context or {}).get("performance_context") or {}
    nifty_price = nifty.get("price")
    nifty_change = nifty.get("change_pct")
    bank_price = banknifty.get("price")
    bank_change = banknifty.get("change_pct")
    expiry_type = expiry.get("type")
    expiry_label = expiry_type if expiry_type else "NO"
    
    prompt = f"""You are an expert intraday trading advisor for Indian stock markets (NSE/BSE).

Current Market Context:
- Time: {context.get('timestamp')}
- NIFTY 50: {nifty_price} ({(nifty_change if nifty_change is not None else 0.0):+.2f}%)
- BANK NIFTY: {bank_price} ({(bank_change if bank_change is not None else 0.0):+.2f}%)
- India VIX: {context.get('vix', 'N/A')}
- Expiry Day: {expiry_label}
"""
    
    if "price_action" in context:
        pa = context["price_action"]
        prompt += f"""
Recent Price Action (last 5 candles):
- Trend: {pa['trend']}
- Volume activity: {"High" if pa['volume_spike'] else "Normal"}
- Range: {pa['range_low']:.2f} - {pa['range_high']:.2f}
"""

    sf = (context or {}).get("session_features") or {}
    if sf:
        prompt += f"""
Intraday Session Features (compact):
- Session candles used: {sf.get('candles_used')}
- Session change: {sf.get('session_change_pct')}%
- Session range: {sf.get('session_range_pct')}%
- Distance to day high: {sf.get('distance_to_day_high_pct')}%
- Distance to day low: {sf.get('distance_to_day_low_pct')}%
- VWAP side: {sf.get('vwap_side')} (VWAP {sf.get('vwap')})
- First-hour breakout state: {sf.get('first_hour_breakout')}
- Volume regime: {sf.get('vol_regime')}
"""

    if perf:
        prompt += f"""
Live Performance Context (charge-aware, rolling):
- Trades in rolling window: {perf.get('window_trades_count')}
- Win rate: {perf.get('win_rate_pct')}%
- Net P&L (window): {perf.get('net_pnl_total')}
- Gross P&L (window): {perf.get('gross_pnl_total')}
- Avg net/trade: {perf.get('avg_net_pnl_per_trade')}
- Executed orders today: {perf.get('executed_orders_today')}
- Estimated charges today: {perf.get('estimated_charges_today')}
- Charges to gross (%): {perf.get('charges_to_gross_pct')}
- Churn score (0-100): {perf.get('churn_score')}
- Charges dominating: {perf.get('charges_dominate')}
- Low-edge block mode: {perf.get('low_edge_block')}
- Learned setup matches: {perf.get('learned_setup_matches')}
- Learned setup win rate: {perf.get('learned_setup_win_rate_pct')}%
- Learned setup avg net: {perf.get('learned_setup_avg_net_pnl')}
- Learned quality score: {perf.get('learned_quality_score')}
- Learned block mode: {perf.get('learned_block')}
"""
    
    prompt += f"""
Currently using strategy: {current_strategy or "None"}

Available strategies:
{strategies_info}

Task: Based on the current market conditions, recommend the SINGLE BEST strategy for this moment.

Respond in JSON format:
{{
    "recommended_strategy": "Strategy Name",
    "confidence": "high/medium/low",
    "reasoning": "2-3 sentence explanation",
    "switch_from_current": true/false,
    "market_assessment": "brief market condition summary"
}}

Consider:
1. Current market trend and momentum
2. Volatility level (VIX)
3. Time of day (opening/mid-day/closing)
4. Recent price action and volume
5. Expiry-day behavior (weekly/monthly expiry can be more volatile)
6. Whether a switch is beneficial vs. staying with current strategy
7. If charges/churn are dominating, prefer defensive/no-switch stance and avoid low-edge setups"""
    
    return prompt


def get_ai_strategy_recommendation(
    context: dict[str, Any],
    current_strategy: str | None = None,
) -> dict[str, Any] | None:
    """
    Get AI-powered strategy recommendation using OpenAI GPT.
    Returns None if OpenAI is not configured or fails.
    """
    if not OPENAI_AVAILABLE:
        logger.warning("OpenAI library not installed. Install with: pip install openai")
        return _reject_recommendation("OpenAI library not available")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not configured. AI strategy selection disabled.")
        return _reject_recommendation("OPENAI_API_KEY missing")
    
    try:
        # Must load governance prompt before every call.
        governance_prompt = _load_governance_prompt()
        client = openai.OpenAI(api_key=api_key)
        
        prompt = build_gpt_prompt(context, current_strategy)
        
        logger.info(f"[AI ADVISOR] Requesting strategy recommendation...")
        
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert intraday trading advisor specializing in Indian markets.\n\n"
                        "You MUST obey this governance policy exactly:\n"
                        f"{governance_prompt}\n\n"
                        "If any rule is violated or input is insufficient, you MUST output a reject JSON."
                    ),
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,  # Lower temperature for more consistent recommendations
            max_completion_tokens=500,
        )
        
        result = response.choices[0].message.content
        try:
            recommendation = json.loads(result)
        except json.JSONDecodeError as e:
            logger.warning("[AI ADVISOR] Invalid JSON from model: %s", str(e))
            return _reject_recommendation(f"Invalid JSON from model: {e}")

        if not isinstance(recommendation, dict):
            return _reject_recommendation("Model output is not a JSON object")

        confidence = str(recommendation.get("confidence", "low")).lower()
        if MIN_CONFIDENCE_ORDER.get(confidence, -1) < MIN_CONFIDENCE_ORDER.get(MIN_CONFIDENCE_REQUIRED, 1):
            return _reject_recommendation(
                f"Confidence below threshold: {confidence} < {MIN_CONFIDENCE_REQUIRED}"
            )
        recommendation["rejected"] = False
        
        logger.info(
            f"[AI ADVISOR] Recommendation: {recommendation.get('recommended_strategy')} "
            f"(Confidence: {recommendation.get('confidence')}) "
            f"Switch: {recommendation.get('switch_from_current')}"
        )
        logger.info(f"[AI ADVISOR] Reasoning: {recommendation.get('reasoning')}")
        
        return recommendation
        
    except Exception as e:
        logger.exception(f"[AI ADVISOR] Failed to get recommendation: {e}")
        return _reject_recommendation(f"AI exception: {e}")


def should_switch_strategy(
    recommendation: dict[str, Any],
    current_strategy: str | None,
    min_confidence: str = "medium",
) -> tuple[bool, str | None]:
    """
    Determine if strategy should be switched based on AI recommendation.
    Returns (should_switch, new_strategy_name)
    """
    if not recommendation:
        return False, None
    if recommendation.get("rejected"):
        logger.info("[AI ADVISOR] Recommendation rejected by governance/rules")
        return False, None
    
    recommended = recommendation.get("recommended_strategy")
    confidence = recommendation.get("confidence", "low")
    switch_flag = recommendation.get("switch_from_current", False)
    
    # Confidence threshold check
    confidence_order = {"low": 0, "medium": 1, "high": 2}
    if confidence_order.get(confidence, 0) < confidence_order.get(min_confidence, 1):
        logger.info(f"[AI ADVISOR] Confidence too low ({confidence}), not switching")
        return False, None
    
    # If no current strategy, always accept recommendation
    if not current_strategy:
        return True, recommended
    
    # If same strategy, no switch needed
    if recommended == current_strategy:
        logger.info(f"[AI ADVISOR] Recommended same strategy ({recommended}), staying")
        return False, None
    
    # If AI explicitly says switch
    if switch_flag:
        logger.info(f"[AI ADVISOR] Switching {current_strategy} → {recommended}")
        return True, recommended
    
    return False, None
