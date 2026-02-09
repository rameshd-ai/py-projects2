"""
IV Expansion Play — SCAFFOLD ONLY.
Requires IV data and option-only execution. Not executable without IV feed.
"""
from __future__ import annotations

from .base_strategy import BaseStrategy


class IVExpansionPlay(BaseStrategy):
    """
    IV Expansion Play Strategy.
    Requires get_iv(tradingsymbol), IV history, and option-only executor.
    Do NOT implement fake IV logic — mark executable: false until IV feed exists.
    """

    def check_entry(self) -> tuple[bool, float | None]:
        return False, None

    def get_stop_loss(self, entry_price: float) -> float:
        return round(entry_price * 0.99, 2)

    def get_target(self, entry_price: float) -> float:
        return round(entry_price * 1.02, 2)

    def check_exit(self, trade: dict) -> str | None:
        return None
