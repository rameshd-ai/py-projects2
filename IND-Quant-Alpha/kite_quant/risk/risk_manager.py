"""
Professional Risk Manager: position sizing, max loss per trade, daily loss cap,
capital allocation, trade throttling. Strategy gives signal; Risk Manager gives permission.
Works for LIVE, PAPER, and BACKTEST.
"""
from __future__ import annotations

from typing import Any
from engine.position_sizing import calculate_position_size_auto, can_afford_fo_position


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
        """
        Calculate lots/quantity using centralized position sizing logic.
        Automatically handles F&O vs Stock based on lot_size.
        """
        lots_or_qty, _, _ = calculate_position_size_auto(
            capital=self.config.capital,
            entry_price=entry_price,
            lot_size=lot_size,
            stop_loss=stop_loss_price,
            risk_percent=self.config.risk_percent_per_trade,
        )
        return lots_or_qty

    def can_trade_today(self, session: dict[str, Any]) -> tuple[bool, str | None]:
        """False if daily loss limit or max trades reached."""
        # Prefer explicit per-session absolute daily loss limit when present.
        # Fallback to percent-of-capital only if session limit is unavailable.
        explicit_limit = session.get("max_daily_loss")
        if explicit_limit is None:
            explicit_limit = session.get("daily_loss_limit")
        try:
            max_daily_loss = float(explicit_limit)
        except Exception:
            max_daily_loss = 0.0
        if max_daily_loss <= 0:
            max_daily_loss = self.config.capital * (self.config.max_daily_loss_percent / 100)

        # Prefer actual daily pnl stream when available.
        daily_pnl = session.get("actual_daily_pnl")
        if daily_pnl is None:
            daily_pnl = session.get("daily_pnl")
        try:
            daily_pnl = float(daily_pnl or 0.0)
        except Exception:
            daily_pnl = 0.0

        if daily_pnl <= -max_daily_loss:
            return False, f"Daily loss limit reached ({daily_pnl:.2f} <= -{max_daily_loss:.2f})"
        taken = session.get("daily_trade_count") or 0
        if taken >= self.config.max_trades:
            return False, "Max trades reached"
        return True, None

    def can_afford_trade(self, premium: float, lot_size: int) -> bool:
        """True if capital can cover premium * lot_size (for options). Uses centralized position sizing."""
        return can_afford_fo_position(self.config.capital, premium, lot_size)

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
