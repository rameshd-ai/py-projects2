"""
Dynamic Trade Frequency Engine
Capital-based trades-per-hour system with drawdown awareness.
Replaces fixed daily trade limits with intelligent, adaptive frequency control.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default trade frequency configuration
DEFAULT_TRADE_FREQUENCY_CONFIG = {
    "rules": [
        {"min_capital": 0, "max_capital": 50000, "max_trades_per_hour": 2},
        {"min_capital": 50000, "max_capital": 200000, "max_trades_per_hour": 3},
        {"min_capital": 200000, "max_capital": 500000, "max_trades_per_hour": 4},
        {"min_capital": 500000, "max_capital": None, "max_trades_per_hour": 5},
    ],
    "max_hourly_cap": 5,
    "drawdown_trigger_percent": 0.02,  # 2% loss triggers frequency reduction
    "hard_drawdown_trigger_percent": 0.05,  # 5% loss limits to 1 trade/hour
    "drawdown_reduce_percent": 0.5,  # Reduce frequency by 50% during drawdown
}


def get_trade_frequency_config() -> dict[str, Any]:
    """
    Get trade frequency configuration.
    Loads from config store, falls back to defaults.
    """
    try:
        from engine.config_store import load_config
        config = load_config()
        
        if "trade_frequency" in config:
            return config["trade_frequency"]
    except Exception as e:
        logger.warning(f"Could not load trade frequency config: {e}")
    
    return DEFAULT_TRADE_FREQUENCY_CONFIG.copy()


def save_trade_frequency_config(config: dict[str, Any]) -> bool:
    """
    Save trade frequency configuration.
    Validates before saving.
    """
    # Validate configuration
    if not validate_trade_frequency_config(config):
        return False
    
    try:
        from engine.config_store import load_config, save_config
        full_config = load_config()
        full_config["trade_frequency"] = config
        save_config(full_config)
        return True
    except Exception as e:
        logger.exception(f"Failed to save trade frequency config: {e}")
        return False


def validate_trade_frequency_config(config: dict[str, Any]) -> bool:
    """
    Validate trade frequency configuration.
    Ensures no overlapping slabs and valid ranges.
    """
    try:
        rules = config.get("rules", [])
        
        # Check max_hourly_cap
        max_cap = config.get("max_hourly_cap", 5)
        if not (1 <= max_cap <= 10):
            logger.error("max_hourly_cap must be between 1 and 10")
            return False
        
        # Check drawdown percentages
        dd_trigger = config.get("drawdown_trigger_percent", 0.02)
        hard_dd = config.get("hard_drawdown_trigger_percent", 0.05)
        dd_reduce = config.get("drawdown_reduce_percent", 0.5)
        
        if not (0 < dd_trigger <= 1):
            logger.error("drawdown_trigger_percent must be between 0 and 1")
            return False
        
        if not (0 < hard_dd <= 1):
            logger.error("hard_drawdown_trigger_percent must be between 0 and 1")
            return False
        
        if not (0 < dd_reduce <= 1):
            logger.error("drawdown_reduce_percent must be between 0 and 1")
            return False
        
        # Check rules
        if not rules:
            logger.error("At least one rule is required")
            return False
        
        # Sort rules by min_capital
        sorted_rules = sorted(rules, key=lambda r: r["min_capital"])
        
        # Check for overlaps and validate each rule
        for i, rule in enumerate(sorted_rules):
            min_cap = rule.get("min_capital", 0)
            max_cap_rule = rule.get("max_capital")
            trades_per_hour = rule.get("max_trades_per_hour", 1)
            
            # Validate trades per hour
            if not (1 <= trades_per_hour <= 10):
                logger.error(f"max_trades_per_hour must be between 1 and 10 in rule {i}")
                return False
            
            # Check overlap with next rule
            if i < len(sorted_rules) - 1:
                next_rule = sorted_rules[i + 1]
                next_min = next_rule.get("min_capital", 0)
                
                if max_cap_rule is None:
                    logger.error(f"Only last rule can have max_capital=None")
                    return False
                
                if max_cap_rule > next_min:
                    logger.error(f"Overlapping capital ranges: Rule {i} and {i+1}")
                    return False
        
        return True
        
    except Exception as e:
        logger.exception(f"Validation error: {e}")
        return False


def calculate_max_trades_per_hour(
    capital: float,
    daily_pnl: float,
    config: dict[str, Any] | None = None
) -> tuple[int, str]:
    """
    Calculate maximum trades per hour based on capital and drawdown.
    
    Args:
        capital: Current capital (or available balance)
        daily_pnl: Today's profit/loss
        config: Trade frequency configuration (optional, loads if None)
    
    Returns:
        (max_trades_per_hour, frequency_mode)
        frequency_mode: "NORMAL" | "REDUCED" | "HARD_LIMIT"
    """
    if config is None:
        config = get_trade_frequency_config()
    
    # Find matching capital slab
    rules = config.get("rules", [])
    base_limit = 2  # Fallback default
    
    for rule in rules:
        min_cap = rule.get("min_capital", 0)
        max_cap = rule.get("max_capital")
        
        if max_cap is None:
            # No upper bound
            if capital >= min_cap:
                base_limit = rule.get("max_trades_per_hour", 2)
                break
        else:
            # Check if capital falls in this slab
            if min_cap <= capital < max_cap:
                base_limit = rule.get("max_trades_per_hour", 2)
                break
    
    # Apply safety cap
    max_hourly_cap = config.get("max_hourly_cap", 5)
    base_limit = min(base_limit, max_hourly_cap)
    
    # Apply drawdown logic
    drawdown_trigger = config.get("drawdown_trigger_percent", 0.02)
    hard_drawdown = config.get("hard_drawdown_trigger_percent", 0.05)
    drawdown_reduce = config.get("drawdown_reduce_percent", 0.5)
    
    frequency_mode = "NORMAL"
    
    # Check for hard drawdown (5% loss)
    if daily_pnl <= -(capital * hard_drawdown):
        logger.warning(f"Hard drawdown triggered: PnL={daily_pnl}, Capital={capital}")
        base_limit = 1
        frequency_mode = "HARD_LIMIT"
    
    # Check for soft drawdown (2% loss)
    elif daily_pnl <= -(capital * drawdown_trigger):
        logger.info(f"Drawdown triggered: PnL={daily_pnl}, Capital={capital}")
        base_limit = max(1, int(base_limit * drawdown_reduce))
        frequency_mode = "REDUCED"
    
    # Always return at least 1
    base_limit = max(1, base_limit)
    
    logger.info(
        f"Trade frequency: Capital=₹{capital:.0f}, PnL=₹{daily_pnl:.0f}, "
        f"Limit={base_limit}/hour, Mode={frequency_mode}"
    )
    
    return base_limit, frequency_mode


def get_frequency_status(session: dict) -> dict[str, Any]:
    """
    Get current trade frequency status for a session.
    
    Returns:
        {
            "max_trades_per_hour": int,
            "trades_this_hour": int,
            "current_hour": int,
            "frequency_mode": str,
            "can_trade": bool,
            "reason": str
        }
    """
    capital = session.get("virtual_balance") or 100000
    daily_pnl = session.get("daily_pnl", 0)
    
    # Calculate limit
    max_per_hour, mode = calculate_max_trades_per_hour(capital, daily_pnl)
    
    # Get current hour stats
    current_hour = session.get("current_hour_block", 9)
    trades_this_hour = session.get("hourly_trade_count", 0)
    
    # Check if can trade
    can_trade = trades_this_hour < max_per_hour
    reason = ""
    
    if not can_trade:
        reason = f"Hourly limit reached ({trades_this_hour}/{max_per_hour})"
    
    return {
        "max_trades_per_hour": max_per_hour,
        "trades_this_hour": trades_this_hour,
        "current_hour": current_hour,
        "frequency_mode": mode,
        "can_trade": can_trade,
        "reason": reason,
    }
