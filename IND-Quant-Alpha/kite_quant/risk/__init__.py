"""
Risk Manager: position sizing, daily loss cap, max trades, capital checks.
Works for LIVE, PAPER, and BACKTEST.
"""
from risk.risk_manager import RiskConfig, RiskManager

__all__ = ["RiskConfig", "RiskManager"]
