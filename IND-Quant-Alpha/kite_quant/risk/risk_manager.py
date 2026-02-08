"""
Professional Risk Manager: position sizing, max loss per trade, daily loss cap,
capital allocation, trade throttling. Strategy gives signal; Risk Manager gives permission.
Works for LIVE, PAPER, and BACKTEST.
"""
from __future__ import annotations

from typing import Any


class RiskConfig:
    def __init__(
        self,
        capital: float,
        risk_percent_per_trade: float = 1.0,
        max_daily_loss_percent: float = 3.0,
        max_trades: int = 10,
    ):
        self.capital = float(capital)
        self.risk_percent_per_trade = float(risk_percent_per_trade)
        self.max_daily_loss_percent = float(max_daily_loss_percent)
        self.max_trades = int(max_trades)


class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        lot_size: int = 1,
    ) -> int:
        """Lots (or shares if lot_size=1) that keep risk within risk_percent_per_trade."""
        risk_amount = self.config.capital * (self.config.risk_percent_per_trade / 100)
        risk_per_unit = abs(entry_price - stop_loss_price)
        if risk_per_unit <= 0:
            return 0
        qty = risk_amount / risk_per_unit
        lots = int(qty // lot_size)
        return max(lots, 0)

    def can_trade_today(self, session: dict[str, Any]) -> tuple[bool, str | None]:
        """False if daily loss limit or max trades reached."""
        max_daily_loss = self.config.capital * (self.config.max_daily_loss_percent / 100)
        daily_pnl = session.get("daily_pnl") or 0
        if daily_pnl <= -max_daily_loss:
            return False, "Daily loss limit reached"
        taken = session.get("trades_taken_today") or 0
        if taken >= self.config.max_trades:
            return False, "Max trades reached"
        return True, None

    def can_afford_trade(self, premium: float, lot_size: int) -> bool:
        """True if capital can cover premium * lot_size (for options)."""
        required = premium * lot_size
        return required <= self.config.capital

    def validate_trade(
        self,
        session: dict[str, Any],
        entry_price: float,
        stop_loss: float,
        lot_size: int = 1,
        premium: float | None = None,
    ) -> tuple[bool, str, int]:
        """
        Full validation. Returns (approved, reason, lots).
        If approved, use returned lots for the order (qty = lots * lot_size).
        """
        can_trade, reason = self.can_trade_today(session)
        if not can_trade:
            return False, reason or "Cannot trade today", 0

        if premium is not None and premium > 0:
            if not self.can_afford_trade(premium, lot_size):
                return False, "Not enough capital", 0

        lots = self.calculate_position_size(entry_price, stop_loss, lot_size)

        if lots == 0:
            return False, "Position size too small for risk rules", 0

        return True, "Approved", lots
