"""
Trading on/off, auto-close time management.
Note: Trade frequency is now controlled by the dynamic hourly frequency system (engine.trade_frequency).
"""
from __future__ import annotations

import os
from datetime import datetime, time
from typing import Any

# Use Asia/Kolkata for auto-close time
TZ_NAME = os.getenv("TZ", "Asia/Kolkata")
AUTO_CLOSE_STR = os.getenv("AUTO_CLOSE_TIME", "14:30")


def _parse_auto_close_time() -> time:
    try:
        h, m = AUTO_CLOSE_STR.strip().split(":")
        return time(int(h), int(m))
    except Exception:
        return time(14, 30)


AUTO_CLOSE_TIME = _parse_auto_close_time()
STOP_LOSS_PCT = 1.5
TAKE_PROFIT_PCT = 3.0


class SessionStatus:
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    AUTO_CLOSED = "AUTO_CLOSED"


class SessionManager:
    def __init__(self):
        self._trading_on = False
        self._status = SessionStatus.STOPPED
        self._positions: list[dict[str, Any]] = []

    def is_trading_on(self) -> bool:
        return self._trading_on

    def start_trading(self) -> None:
        self._trading_on = True
        self._status = SessionStatus.RUNNING

    def stop_trading(self) -> None:
        self._trading_on = False
        if self._status == SessionStatus.RUNNING:
            self._status = SessionStatus.STOPPED

    def auto_close(self) -> None:
        self._trading_on = False
        self._status = SessionStatus.AUTO_CLOSED

    def get_status(self) -> str:
        return self._status

    def set_positions(self, positions: list[dict[str, Any]]) -> None:
        self._positions = list(positions)

    def get_positions(self) -> list[dict[str, Any]]:
        return list(self._positions)

    def is_past_auto_close(self) -> bool:
        """True if current time (IST) >= AUTO_CLOSE_TIME (e.g. 2:30 PM)."""
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(TZ_NAME)).time()
            return now >= AUTO_CLOSE_TIME
        except Exception:
            return False

    def minutes_until_auto_close(self) -> int | None:
        """Minutes until 2:30 PM IST; None if past."""
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(TZ_NAME)
            now = datetime.now(tz)
            close_dt = now.replace(hour=AUTO_CLOSE_TIME.hour, minute=AUTO_CLOSE_TIME.minute, second=0, microsecond=0)
            if now >= close_dt:
                return 0
            delta = close_dt - now
            return int(delta.total_seconds() / 60)
        except Exception:
            return None


# Singleton for app
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
