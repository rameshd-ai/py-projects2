"""
Unified Entry Logic for ALL trading modes (Live, Paper, Backtest).
One function to rule them all!
NOW WITH AI VALIDATION - AI decides if each trade is good or bad.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Cache for AI market analysis (avoid calling GPT every candle)
_ai_entry_cache = {
    "bias": "neutral",
    "conviction": "medium",
    "reasoning": "No AI analysis yet",
    "timestamp": None,
    "ttl_seconds": 900  # 15 minutes cache
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
                    "bias": _ai_entry_cache["bias"],
                    "conviction": _ai_entry_cache["conviction"],
                    "reasoning": _ai_entry_cache["reasoning"]
                }
        
        # Cache expired or force refresh - call AI
        logger.info(f"[AI ENTRY] Calling GPT for market analysis (instrument: {instrument})")
        
        # Import here to avoid circular dependencies
        from engine.ai_strategy_advisor import get_ai_strategy_recommendation
        
        # Build context for AI
        context = {
            "instrument": instrument,
            "current_price": current_price,
            "recent_candles": recent_candles[-10:] if recent_candles and len(recent_candles) >= 10 else recent_candles,
            "time": now.strftime("%H:%M")
        }
        
        # Get AI recommendation
        ai_rec = get_ai_strategy_recommendation(context, current_strategy=None)
        
        if ai_rec:
            bias = ai_rec.get("market_bias", "neutral")
            confidence = ai_rec.get("confidence", "medium")
            reasoning = ai_rec.get("reasoning", "AI analysis complete")
            
            # Update cache
            _ai_entry_cache["bias"] = bias
            _ai_entry_cache["conviction"] = confidence
            _ai_entry_cache["reasoning"] = reasoning[:200]  # Truncate
            _ai_entry_cache["timestamp"] = now
            
            logger.info(f"[AI ENTRY] ✅ Bias: {bias} | Conviction: {confidence} | Reasoning: {reasoning[:100]}...")
            
            return {
                "bias": bias,
                "conviction": confidence,
                "reasoning": reasoning
            }
        else:
            logger.warning("[AI ENTRY] ⚠️ GPT returned no recommendation, using neutral bias")
            return {
                "bias": "neutral",
                "conviction": "low",
                "reasoning": "AI unavailable"
            }
            
    except Exception as e:
        logger.warning(f"[AI ENTRY] ❌ GPT call failed: {e}, using cached/neutral bias")
        return {
            "bias": _ai_entry_cache.get("bias", "neutral"),
            "conviction": "low",
            "reasoning": f"AI error: {str(e)[:100]}"
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
        
        bias = ai_analysis["bias"].lower()
        conviction = ai_analysis["conviction"].lower()
        
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
        logger.warning(f"[AI ENTRY] AI validation error: {e}, defaulting to APPROVE")
        # On error, APPROVE (don't block trading)
        return True, f"⚠️ AI unavailable, allowing entry"


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
            logger.warning(f"[AI AGENT] AI validation error: {e}, proceeding without AI")
            # Don't block on AI errors
    
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
    
    # Use unified entry logic WITH AI VALIDATION
    should_enter, reason = check_unified_entry(
        current_price=current_price,
        recent_candles=recent_candles,
        strategy_name=strategy_name,
        instrument=instrument,
        use_ai_validation=use_ai,
    )
    
    logger.info(f"[{mode}] Entry Decision: {should_enter} | Reason: {reason}")
    
    return should_enter, reason
