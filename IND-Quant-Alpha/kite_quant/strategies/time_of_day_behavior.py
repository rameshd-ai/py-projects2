"""
Time-of-Day Behavior: bias for strategy selection, not entry logic. Stub only.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class TimeOfDayBehavior(BaseStrategy):
    """Stub. Use in strategy scoring/selection (morning=breakout, etc.), not as entry strategy."""

    def check_entry(self) -> tuple[bool, float | None]:
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        return round(entry_price * 0.995, 2)

    def get_target(self, entry_price: float) -> float:
        return round(entry_price * 1.02, 2)

    def check_exit(self, trade: dict) -> str | None:
        return None
