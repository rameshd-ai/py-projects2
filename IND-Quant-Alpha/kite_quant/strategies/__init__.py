"""
Multi-strategy trading: entry/exit/SL/target per strategy.
"""
from strategies.base_strategy import BaseStrategy
from strategies.strategy_registry import STRATEGY_MAP, get_strategy_for_session

__all__ = ["BaseStrategy", "STRATEGY_MAP", "get_strategy_for_session"]
