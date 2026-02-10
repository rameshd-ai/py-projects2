"""
Unified Entry Logic for ALL trading modes (Live, Paper, Backtest).
One function to rule them all!
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def check_unified_entry(
    current_price: float,
    recent_candles: list[dict] | None = None,
    strategy_name: str = "Momentum Breakout",
) -> tuple[bool, str]:
    """
    UNIFIED ENTRY LOGIC - Used by Live, Paper, and Backtest.
    
    Args:
        current_price: Current LTP/close price
        recent_candles: Optional list of recent candles for better analysis
        strategy_name: Current strategy (for logging purposes)
    
    Returns:
        (should_enter, reason)
    """
    # DEFAULT: ALWAYS ENTER (Maximum Aggression)
    should_enter = True
    reason = f"Auto entry @ Rs.{current_price:.2f}"
    
    # If we have recent candles, generate better reason
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
            
            # Generate reason based on market action
            if abs(price_change_pct) > 0.3:
                reason = f"Strong move {price_change_pct:+.2f}%"
            elif abs(price_change_pct) > 0.1:
                reason = f"Price move {price_change_pct:+.2f}%"
            elif is_green:
                reason = "Green candle (bullish)"
            elif is_red:
                reason = "Red candle (bearish reversal)"
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
            # On error, still enter
            should_enter = True
            reason = f"Auto entry (analysis error)"
    
    logger.debug(f"[UNIFIED ENTRY] {strategy_name} | Price: Rs.{current_price:.2f} | Enter: {should_enter} | Reason: {reason}")
    
    return should_enter, reason


def should_enter_trade(
    mode: str,
    current_price: float,
    recent_candles: list[dict] | None = None,
    strategy_name: str = "Momentum Breakout",
    frequency_check_passed: bool = True,
) -> tuple[bool, str]:
    """
    Master entry function for ALL modes.
    
    Args:
        mode: "LIVE", "PAPER", or "BACKTEST"
        current_price: Current price
        recent_candles: Recent price data
        strategy_name: Current strategy
        frequency_check_passed: Has hourly frequency check passed?
    
    Returns:
        (should_enter, reason)
    """
    # Check frequency first
    if not frequency_check_passed:
        return False, "Hourly frequency limit reached"
    
    # Use unified entry logic
    should_enter, reason = check_unified_entry(
        current_price=current_price,
        recent_candles=recent_candles,
        strategy_name=strategy_name,
    )
    
    logger.info(f"[{mode}] Entry Decision: {should_enter} | Reason: {reason}")
    
    return should_enter, reason
