"""
Unified Entry Logic for ALL trading modes (Live, Paper, Backtest).
One function to rule them all!
NOW WITH AI VALIDATION - AI decides if each trade is good or bad.
"""
from __future__ import annotations
import os
import logging
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from typing import Any
from engine.performance_context import build_live_performance_context

logger = logging.getLogger(__name__)
MIN_AI_CONFIDENCE_ORDER = {"reject": -1, "low": 0, "medium": 1, "high": 2}
MIN_AI_CONFIDENCE_REQUIRED = "medium"
LIVE_MIN_MOVE_PCT = float(os.getenv("LIVE_MIN_MOVE_PCT", "0.25") or 0.25)
LIVE_MIN_AI_CONFIDENCE_REQUIRED = str(os.getenv("LIVE_MIN_AI_CONFIDENCE_REQUIRED", "medium") or "medium").strip().lower()
LIVE_REQUIRE_TWO_CANDLE_CONFIRMATION = str(os.getenv("LIVE_REQUIRE_TWO_CANDLE_CONFIRMATION", "1")).strip().lower() in {"1", "true", "yes", "on"}
LIVE_MIN_PREV_CANDLE_MOVE_PCT = float(os.getenv("LIVE_MIN_PREV_CANDLE_MOVE_PCT", "0.10") or 0.10)
LIVE_ENTRY_WINDOW_1_START = time(9, 25)
LIVE_ENTRY_WINDOW_1_END = time(10, 45)
LIVE_ENTRY_WINDOW_2_START = time(13, 15)
LIVE_ENTRY_WINDOW_2_END = time(15, 10)


def _is_live_entry_time_allowed(now_ist: datetime | None = None) -> bool:
    now_ist = now_ist or datetime.now(ZoneInfo("Asia/Kolkata"))
    t = now_ist.time()
    in_window_1 = LIVE_ENTRY_WINDOW_1_START <= t <= LIVE_ENTRY_WINDOW_1_END
    in_window_2 = LIVE_ENTRY_WINDOW_2_START <= t <= LIVE_ENTRY_WINDOW_2_END
    return in_window_1 or in_window_2

# Cache for AI market analysis (avoid calling GPT every candle)
_ai_entry_cache = {
    "bias": "neutral",
    "conviction": "medium",
    "reasoning": "No AI analysis yet",
    "performance_context": {},
    "timestamp": None,
    "ttl_seconds": 900  # 15 minutes cache
}


def get_latest_ai_entry_conviction() -> str:
    """Return latest cached AI conviction for current market analysis."""
    c = str(_ai_entry_cache.get("conviction") or "low").strip().lower()
    return c if c in MIN_AI_CONFIDENCE_ORDER else "low"


def get_latest_ai_entry_snapshot() -> dict[str, Any]:
    """Return latest cached AI bias/conviction for score engine."""
    return {
        "bias": str(_ai_entry_cache.get("bias") or "neutral").strip().lower(),
        "conviction": get_latest_ai_entry_conviction(),
        "reasoning": str(_ai_entry_cache.get("reasoning") or ""),
        "performance_context": _ai_entry_cache.get("performance_context") or {},
    }


def get_ai_market_analysis(
    instrument: str,
    current_price: float,
    recent_candles: list[dict] | None = None,
    force_refresh: bool = False
) -> dict:
    """
    Get AI's current market analysis with caching.
    Returns: {bias: bullish/bearish/neutral, conviction: low/medium/high, reasoning: str}
    """
    try:
        from datetime import datetime as dt

        now = dt.now()

        # Check cache validity
        if not force_refresh and _ai_entry_cache["timestamp"]:
            age = (now - _ai_entry_cache["timestamp"]).total_seconds()
            if age < _ai_entry_cache["ttl_seconds"]:
                logger.debug(f"[AI CACHE] Using cached analysis (age: {age:.0f}s)")
                return {
                    "approved": True,
                    "bias": _ai_entry_cache["bias"],
                    "conviction": _ai_entry_cache["conviction"],
                    "reasoning": _ai_entry_cache["reasoning"],
                    "performance_context": _ai_entry_cache.get("performance_context") or {},
                }

        # Cache expired or force refresh - call AI
        logger.info(f"[AI ENTRY] Calling GPT for market analysis (instrument: {instrument})")

        # Import here to avoid circular dependencies
        from engine.ai_strategy_advisor import get_ai_strategy_recommendation, get_market_context

        candles_for_ai = recent_candles[-75:] if recent_candles else recent_candles
        context = get_market_context(
            nifty_price=current_price,
            nifty_change_pct=0.0,
            banknifty_price=current_price,
            banknifty_change_pct=0.0,
            vix=None,
            current_time=now.strftime("%Y-%m-%d %H:%M:%S"),
            recent_candles=candles_for_ai,
            expiry_type=None,
        )
        perf_ctx = build_live_performance_context(
            max_trades=20,
            current_session_features=context.get("session_features") if isinstance(context.get("session_features"), dict) else None,
        )
        context["instrument"] = instrument
        context["current_price"] = current_price
        context["time"] = now.strftime("%H:%M")
        context["performance_context"] = perf_ctx

        # Get AI recommendation
        ai_rec = get_ai_strategy_recommendation(context, current_strategy=None)
        if not ai_rec or ai_rec.get("rejected"):
            reason = (ai_rec or {}).get("reasoning") if isinstance(ai_rec, dict) else "AI unavailable"
            _ai_entry_cache["bias"] = "reject"
            _ai_entry_cache["conviction"] = "reject"
            _ai_entry_cache["reasoning"] = str(reason or "AI recommendation rejected")[:200]
            _ai_entry_cache["performance_context"] = perf_ctx
            _ai_entry_cache["timestamp"] = now
            return {
                "approved": True,
                "bias": "reject",
                "conviction": "reject",
                "reasoning": reason or "AI recommendation rejected",
                "performance_context": perf_ctx,
            }

        bias = str(ai_rec.get("market_bias", "neutral"))
        confidence = str(ai_rec.get("confidence", "low")).lower()
        reasoning = str(ai_rec.get("reasoning", "AI analysis complete"))

        # Update cache
        _ai_entry_cache["bias"] = bias
        _ai_entry_cache["conviction"] = confidence
        _ai_entry_cache["reasoning"] = reasoning[:200]  # Truncate
        _ai_entry_cache["performance_context"] = perf_ctx
        _ai_entry_cache["timestamp"] = now

        logger.info(f"[AI ENTRY] ✅ Bias: {bias} | Conviction: {confidence} | Reasoning: {reasoning[:100]}...")

        return {
            "approved": True,
            "bias": bias,
            "conviction": confidence,
            "reasoning": reasoning,
            "performance_context": perf_ctx,
        }

    except Exception as e:
        logger.warning(f"[AI ENTRY] ❌ GPT call failed: {e}. Using reject score bucket.")
        return {
            "approved": True,
            "bias": "reject",
            "conviction": "reject",
            "reasoning": f"AI exception: {str(e)[:120]}",
            "performance_context": {},
        }


def ai_validate_entry(
    current_price: float,
    recent_candles: list[dict] | None,
    price_change_pct: float,
    instrument: str = "NIFTY"
) -> tuple[bool, str]:
    """
    AI AGENTIC VALIDATION - SIMPLE SAFETY FILTER
    Just reject OBVIOUSLY BAD trades (strong conflicts only).
    Focus: Let scalping strategy (8% target, 15% stop) do the work.
    
    Returns: (should_enter, reasoning)
    """
    try:
        # Get AI's current market analysis (cached for 15 min)
        ai_analysis = get_ai_market_analysis(
            instrument=instrument,
            current_price=current_price,
            recent_candles=recent_candles,
            force_refresh=False
        )
        
        if not ai_analysis.get("approved", False):
            return False, f"❌ AI REJECT: {ai_analysis.get('reasoning', 'AI unavailable')}"

        bias = str(ai_analysis["bias"]).lower()
        conviction = str(ai_analysis["conviction"]).lower()
        perf = ai_analysis.get("performance_context") or {}
        if MIN_AI_CONFIDENCE_ORDER.get(conviction, -1) < MIN_AI_CONFIDENCE_ORDER.get(MIN_AI_CONFIDENCE_REQUIRED, 1):
            return False, f"❌ AI confidence below threshold ({conviction})"

        # Force stricter gating when charges/churn dominate the day.
        if perf.get("low_edge_block"):
            if conviction != "high":
                return False, "❌ Charge-aware block: day is low-edge and charge-heavy (requires HIGH AI conviction)"
            min_edge_move = max(0.45, LIVE_MIN_MOVE_PCT * 1.8)
            if abs(price_change_pct) < min_edge_move:
                return False, f"❌ Charge-aware block: move too weak ({abs(price_change_pct):.2f}% < {min_edge_move:.2f}%)"

        # Learning-aware gate from historical setup outcomes.
        if perf.get("learned_block"):
            return False, "❌ Learning block: this setup profile has weak historical edge"
        learned_score = float(perf.get("learned_quality_score") or 50.0)
        if learned_score < 45.0 and conviction != "high":
            return False, f"❌ Learning filter: low setup quality score ({learned_score:.1f})"
        
        # === SIMPLE SAFETY FILTER - REJECT ONLY OBVIOUS CONFLICTS ===
        
        # 1. Strong bullish bias + sharp fall = CONFLICT (reject)
        if bias == "bullish" and conviction == "high" and price_change_pct < -0.4:
            return False, f"❌ AI: HIGH bullish but sharp fall ({price_change_pct:+.2f}%)"
        
        # 2. Strong bearish bias + sharp rise = CONFLICT (reject)
        elif bias == "bearish" and conviction == "high" and price_change_pct > 0.4:
            return False, f"❌ AI: HIGH bearish but sharp rise ({price_change_pct:+.2f}%)"
        
        # 3. ALL OTHER CASES: APPROVE (let scalping strategy work)
        else:
            # Build informative reason
            if bias == "bullish":
                reason = f"✅ AI: Bullish bias, {price_change_pct:+.2f}% move, approved"
            elif bias == "bearish":
                reason = f"✅ AI: Bearish bias, {price_change_pct:+.2f}% move, approved"
            else:
                reason = f"✅ AI: Neutral bias, {price_change_pct:+.2f}% move, approved"
            
            return True, reason
                
    except Exception as e:
        logger.warning(f"[AI ENTRY] AI validation error: {e}, defaulting to REJECT")
        # Fail-safe: no trade on AI errors.
        return False, f"❌ AI validation error: {e}"


def check_unified_entry(
    current_price: float,
    recent_candles: list[dict] | None = None,
    strategy_name: str = "Momentum Breakout",
    instrument: str = "NIFTY",
    use_ai_validation: bool = True,
) -> tuple[bool, str]:
    """
    UNIFIED ENTRY LOGIC - Used by Live, Paper, and Backtest.
    NOW WITH AI AGENTIC VALIDATION!
    
    Args:
        current_price: Current LTP/close price
        recent_candles: Optional list of recent candles for better analysis
        strategy_name: Current strategy (for logging purposes)
        instrument: Trading instrument
        use_ai_validation: Enable AI validation (default True)
    
    Returns:
        (should_enter, reason)
    """
    # DEFAULT: Allow entry (start optimistic)
    should_enter = True
    reason = f"Auto entry @ Rs.{current_price:.2f}"
    price_change_pct = 0
    
    # If we have recent candles, analyze them
    if recent_candles and len(recent_candles) >= 2:
        try:
            last_candle = recent_candles[-1]
            prev_candle = recent_candles[-2] if len(recent_candles) > 1 else recent_candles[-1]
            
            # Calculate price change
            prev_close = prev_candle.get("close", current_price)
            price_change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            
            # Determine candle color
            candle_open = last_candle.get("open", current_price)
            is_green = current_price > candle_open
            is_red = current_price < candle_open
            
            # Generate technical reason
            if abs(price_change_pct) > 0.3:
                reason = f"Strong move {price_change_pct:+.2f}%"
            elif abs(price_change_pct) > 0.1:
                reason = f"Price move {price_change_pct:+.2f}%"
            elif is_green:
                reason = "Green candle (bullish)"
            elif is_red:
                reason = "Red candle (bearish)"
            else:
                reason = f"Flat movement ({price_change_pct:+.2f}%)"
            
            # ONLY EXCEPTION: Skip perfect doji with ZERO movement
            candle_high = last_candle.get("high", current_price)
            candle_low = last_candle.get("low", current_price)
            candle_body = abs(current_price - candle_open)
            candle_range = candle_high - candle_low
            
            is_doji = False
            if candle_range > 0:
                body_ratio = candle_body / candle_range
                is_doji = body_ratio < 0.1  # Body less than 10% of range
            
            # Only skip if perfect doji AND no price movement
            if is_doji and abs(price_change_pct) < 0.05:
                should_enter = False
                reason = "Perfect doji with no movement"
                
        except Exception as e:
            logger.debug(f"Error analyzing candles for entry: {e}")
            # On error, still allow entry
            should_enter = True
            reason = f"Auto entry (analysis error)"
    
    # === AI AGENTIC VALIDATION ===
    if should_enter and use_ai_validation:
        try:
            ai_approved, ai_reason = ai_validate_entry(
                current_price=current_price,
                recent_candles=recent_candles,
                price_change_pct=price_change_pct,
                instrument=instrument
            )
            
            if not ai_approved:
                # AI rejected the entry
                should_enter = False
                reason = ai_reason
                logger.info(f"[AI AGENT] 🚫 Entry REJECTED | {reason}")
            else:
                # AI approved the entry
                reason = f"{reason} | {ai_reason}"
                logger.info(f"[AI AGENT] ✅ Entry APPROVED | {reason}")
                
        except Exception as e:
            should_enter = False
            reason = f"❌ AI validation error: {e}"
            logger.warning(f"[AI AGENT] AI validation error: {e}, rejecting entry")
    
    logger.debug(f"[UNIFIED ENTRY] {strategy_name} | Price: Rs.{current_price:.2f} | Enter: {should_enter} | Reason: {reason}")
    
    return should_enter, reason


def should_enter_trade(
    mode: str,
    current_price: float,
    recent_candles: list[dict] | None = None,
    strategy_name: str = "Momentum Breakout",
    frequency_check_passed: bool = True,
    instrument: str = "NIFTY",
    use_ai: bool = True,
) -> tuple[bool, str]:
    """
    Master entry function for ALL modes.
    NOW WITH AI AGENTIC VALIDATION!
    
    Args:
        mode: "LIVE", "PAPER", or "BACKTEST"
        current_price: Current price
        recent_candles: Recent price data
        strategy_name: Current strategy
        frequency_check_passed: Has hourly frequency check passed?
        instrument: Trading instrument
        use_ai: Enable AI validation (default True)
    
    Returns:
        (should_enter, reason)
    """
    # Check frequency first
    if not frequency_check_passed:
        return False, "Hourly frequency limit reached"

    # LIVE-only hard time windows: reduce midday churn and late-day overtrading.
    if str(mode or "").upper() == "LIVE":
        if not _is_live_entry_time_allowed():
            return (
                False,
                "Outside LIVE entry windows (09:25-10:45, 13:15-15:10 IST)",
            )
    
    mode_u = str(mode or "").upper()
    if mode_u != "LIVE":
        should_enter, reason = check_unified_entry(
            current_price=current_price,
            recent_candles=recent_candles,
            strategy_name=strategy_name,
            instrument=instrument,
            use_ai_validation=use_ai,
        )
        logger.info(f"[{mode}] Entry Decision: {should_enter} | Reason: {reason}")
        return should_enter, reason

    reason = f"LIVE candidate @ Rs.{current_price:.2f}"
    if recent_candles and len(recent_candles) >= 2:
        try:
            prev_close = float((recent_candles[-2] or {}).get("close") or 0.0)
            if prev_close > 0:
                move_pct = ((float(current_price) - prev_close) / prev_close) * 100.0
                reason = f"{reason} | move {move_pct:+.2f}%"
        except Exception:
            pass

    if use_ai:
        try:
            ai_state = get_ai_market_analysis(
                instrument=instrument,
                current_price=current_price,
                recent_candles=recent_candles,
                force_refresh=False,
            )
            ai_bias = str(ai_state.get("bias") or "neutral").lower()
            ai_conf = str(ai_state.get("conviction") or "reject").lower()
            reason = f"{reason} | AI={ai_bias}/{ai_conf}"
        except Exception as e:
            reason = f"{reason} | AI=unavailable ({str(e)[:60]})"

    # Keep as informative signal only.
    if LIVE_REQUIRE_TWO_CANDLE_CONFIRMATION and recent_candles and len(recent_candles) >= 3:
        try:
            c1 = recent_candles[-2] or {}
            c2 = recent_candles[-3] or {}
            c1_close = float(c1.get("close") or 0.0)
            c2_close = float(c2.get("close") or 0.0)
            if c1_close > 0 and c2_close > 0:
                prev_move = ((c1_close - c2_close) / c2_close) * 100.0
                if abs(prev_move) >= LIVE_MIN_PREV_CANDLE_MOVE_PCT:
                    reason = f"{reason} | 2-candle strong"
                else:
                    reason = f"{reason} | 2-candle weak"
        except Exception:
            pass

    logger.info(f"[{mode}] Entry Decision: True | Reason: {reason}")
    return True, reason
