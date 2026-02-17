"""
Shared risk engine for session-level trading controls.

This module enforces hard limits:
- max_loss_per_trade <= 300
- max_daily_loss <= 3000
- stop trading after 3 consecutive losses
- apply cooldown after 2 consecutive losses
- enforce daily trade cap
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


HARD_MAX_LOSS_PER_TRADE = 300.0
HARD_MAX_DAILY_LOSS = 3000.0
DEFAULT_DAILY_TRADE_CAP = 20
STRICT_COOLDOWN_AFTER_TWO_LOSSES_MINUTES = 15
DEFAULT_COOLDOWN_MINUTES = STRICT_COOLDOWN_AFTER_TWO_LOSSES_MINUTES
STRICT_DAILY_TRADE_CAP = 20
SLIPPAGE_TOLERANCE_MULTIPLIER = 1.5
HARD_EMERGENCY_MULTIPLIER = 2.0


@dataclass
class TradeRecord:
    """Minimal trade record used by the risk engine."""

    pnl: float
    ts: str
    actual_pnl: float | None = None
    capped_pnl: float | None = None


@dataclass
class SessionRiskState:
    """Normalized risk state for a trading session."""

    session_id: str = ""
    status: str = "ACTIVE"
    stop_reason: str | None = None
    daily_pnl: float = 0.0
    actual_daily_pnl: float = 0.0
    risk_capped_daily_pnl: float = 0.0
    daily_trade_count: int = 0
    consecutive_losses: int = 0
    max_loss_per_trade: float = HARD_MAX_LOSS_PER_TRADE
    max_daily_loss: float = HARD_MAX_DAILY_LOSS
    daily_trade_cap: int = DEFAULT_DAILY_TRADE_CAP
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES
    cooldown_until: str | None = None
    last_trade_risk_band: str | None = None
    trade_history: list[TradeRecord] = field(default_factory=list)


@dataclass
class RiskDecision:
    """Standard result for risk checks."""

    approved: bool
    errors: list[str]
    updated_session_state: dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _to_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _normalize_limits(state: SessionRiskState) -> SessionRiskState:
    state.max_loss_per_trade = min(max(1.0, state.max_loss_per_trade), HARD_MAX_LOSS_PER_TRADE)
    state.max_daily_loss = min(max(1.0, state.max_daily_loss), HARD_MAX_DAILY_LOSS)
    state.daily_trade_cap = min(max(1, state.daily_trade_cap), STRICT_DAILY_TRADE_CAP)
    state.cooldown_minutes = max(1, state.cooldown_minutes)
    if state.daily_trade_count < 0:
        state.daily_trade_count = 0
    return state


def _from_dict(session_state: dict[str, Any]) -> SessionRiskState:
    raw_history = session_state.get("trade_history") or []
    history: list[TradeRecord] = []
    for item in raw_history:
        if isinstance(item, dict):
            history.append(
                TradeRecord(
                    pnl=_to_float(item.get("pnl"), 0.0),
                    actual_pnl=_to_float(item.get("actual_pnl"), _to_float(item.get("pnl"), 0.0)),
                    capped_pnl=_to_float(item.get("capped_pnl"), _to_float(item.get("pnl"), 0.0)),
                    ts=str(item.get("ts") or item.get("entry_time") or item.get("exit_time") or ""),
                )
            )

    daily_pnl_legacy = _to_float(session_state.get("daily_pnl"), 0.0)
    risk_capped_daily = _to_float(session_state.get("risk_capped_daily_pnl"), daily_pnl_legacy)
    state = SessionRiskState(
        session_id=str(session_state.get("session_id") or session_state.get("sessionId") or ""),
        status=str(session_state.get("status") or "ACTIVE"),
        stop_reason=session_state.get("stop_reason"),
        daily_pnl=risk_capped_daily,
        actual_daily_pnl=_to_float(session_state.get("actual_daily_pnl"), daily_pnl_legacy),
        risk_capped_daily_pnl=risk_capped_daily,
        daily_trade_count=_to_int(session_state.get("daily_trade_count"), 0),
        consecutive_losses=_to_int(session_state.get("consecutive_losses"), 0),
        max_loss_per_trade=_to_float(
            session_state.get("max_loss_per_trade", session_state.get("risk_amount_per_trade")),
            HARD_MAX_LOSS_PER_TRADE,
        ),
        max_daily_loss=_to_float(
            session_state.get("max_daily_loss", session_state.get("daily_loss_limit")),
            HARD_MAX_DAILY_LOSS,
        ),
        daily_trade_cap=_to_int(session_state.get("daily_trade_cap"), DEFAULT_DAILY_TRADE_CAP),
        cooldown_minutes=_to_int(session_state.get("cooldown_minutes"), DEFAULT_COOLDOWN_MINUTES),
        cooldown_until=session_state.get("cooldown_until"),
        last_trade_risk_band=session_state.get("last_trade_risk_band"),
        trade_history=history,
    )
    return _normalize_limits(state)


def _to_dict(state: SessionRiskState) -> dict[str, Any]:
    out = asdict(state)
    # Keep legacy daily_pnl field as capped stream for backward compatibility.
    out["daily_pnl"] = state.risk_capped_daily_pnl
    out["trade_history"] = [
        {
            "pnl": t.pnl,
            "actual_pnl": t.actual_pnl if t.actual_pnl is not None else t.pnl,
            "capped_pnl": t.capped_pnl if t.capped_pnl is not None else t.pnl,
            "ts": t.ts,
        }
        for t in state.trade_history
    ]
    # Backward-compatible key aliases used elsewhere in this codebase
    out["sessionId"] = state.session_id
    out["daily_loss_limit"] = state.max_daily_loss
    out["risk_amount_per_trade"] = state.max_loss_per_trade
    return out


def _decision(state: SessionRiskState, errors: list[str]) -> RiskDecision:
    return RiskDecision(
        approved=len(errors) == 0 and state.status == "ACTIVE",
        errors=errors,
        updated_session_state=_to_dict(state),
    )


def check_daily_loss(session_state: dict[str, Any]) -> RiskDecision:
    """
    Check daily loss breach.

    Breach condition:
        daily_pnl <= -max_daily_loss
    """
    state = _from_dict(session_state)
    errors: list[str] = []
    if state.actual_daily_pnl <= -state.max_daily_loss:
        state.status = "STOPPED"
        state.stop_reason = "DAILY_LOSS_LIMIT"
        errors.append(
            f"Daily loss limit breached: actual_daily_pnl={state.actual_daily_pnl:.2f}, max_daily_loss={state.max_daily_loss:.2f}"
        )
    return _decision(state, errors)


def check_consecutive_losses(session_state: dict[str, Any]) -> RiskDecision:
    """
    Stop trading when consecutive losses reach 3.
    """
    state = _from_dict(session_state)
    errors: list[str] = []
    if state.consecutive_losses >= 3:
        state.status = "STOPPED"
        state.stop_reason = "CONSECUTIVE_LOSSES"
        errors.append(f"Consecutive losses limit breached: {state.consecutive_losses} >= 3")
    return _decision(state, errors)


def check_trade_caps(session_state: dict[str, Any]) -> RiskDecision:
    """
    Enforce daily trade cap.
    """
    state = _from_dict(session_state)
    errors: list[str] = []
    if state.daily_trade_count >= state.daily_trade_cap:
        state.status = "STOPPED"
        state.stop_reason = "DAILY_TRADE_CAP"
        errors.append(
            f"Daily trade cap reached: daily_trade_count={state.daily_trade_count}, cap={state.daily_trade_cap}"
        )
    return _decision(state, errors)


def enforce_cooldown(session_state: dict[str, Any], now: datetime | None = None) -> RiskDecision:
    """
    Enforce cooldown after 2 consecutive losses.

    Behavior:
    - If consecutive_losses >= 2 and cooldown_until is not set, create cooldown window.
    - If now < cooldown_until, block trading.
    """
    state = _from_dict(session_state)
    errors: list[str] = []
    now_dt = now or _utc_now()

    cooldown_until_dt = _parse_ts(state.cooldown_until)
    if state.consecutive_losses >= 2 and cooldown_until_dt is None:
        cooldown_until_dt = now_dt + timedelta(minutes=state.cooldown_minutes)
        state.cooldown_until = cooldown_until_dt.isoformat()

    if cooldown_until_dt and now_dt < cooldown_until_dt:
        errors.append(f"Cooldown active until {cooldown_until_dt.isoformat()}")

    return _decision(state, errors)


def evaluate_risk(session_state: dict[str, Any], now: datetime | None = None) -> RiskDecision:
    """
    Run all risk checks and return a consolidated decision.

    Returns:
        RiskDecision(
            approved: bool,
            errors: list[str],
            updated_session_state: dict
        )
    """
    state = _from_dict(session_state)
    errors: list[str] = []
    check_fns = (
        lambda s: check_daily_loss(s),
        lambda s: check_consecutive_losses(s),
        lambda s: check_trade_caps(s),
        lambda s: enforce_cooldown(s, now=now),
    )
    for check in check_fns:
        d = check(_to_dict(state))
        errors.extend(d.errors)
        state = _from_dict(d.updated_session_state)

    return _decision(state, errors)


def evaluate_entry(session_state: dict[str, Any], now: datetime | None = None) -> RiskDecision:
    """
    Mandatory pre-entry gate.

    This is the single-source pre-trade risk decision entrypoint for runtime code.
    """
    state = _from_dict(session_state)
    errors: list[str] = []
    now_dt = now or _utc_now()

    # Strict daily trade cap block.
    if state.daily_trade_count >= STRICT_DAILY_TRADE_CAP:
        state.status = "STOPPED"
        state.stop_reason = "DAILY_TRADE_CAP"
        errors.append(
            f"Daily trade cap reached: daily_trade_count={state.daily_trade_count}, cap={STRICT_DAILY_TRADE_CAP}"
        )

    # Strict loss streak controls.
    cooldown_until_dt = _parse_ts(state.cooldown_until)
    if state.consecutive_losses >= 3:
        next_day_start = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        state.status = "STOPPED"
        state.stop_reason = "CONSECUTIVE_LOSSES_HARD_STOP"
        state.cooldown_until = next_day_start.isoformat()
        errors.append(
            f"Hard loss-streak stop: consecutive_losses={state.consecutive_losses} (blocked until next day)"
        )
    elif state.consecutive_losses >= 2:
        state.cooldown_minutes = STRICT_COOLDOWN_AFTER_TWO_LOSSES_MINUTES
        if cooldown_until_dt is None:
            cooldown_until_dt = now_dt + timedelta(minutes=STRICT_COOLDOWN_AFTER_TWO_LOSSES_MINUTES)
            state.cooldown_until = cooldown_until_dt.isoformat()
            errors.append(f"Cooldown active until {cooldown_until_dt.isoformat()}")
        elif now_dt < cooldown_until_dt:
            errors.append(f"Cooldown active until {cooldown_until_dt.isoformat()}")
        else:
            # Cooldown elapsed: reset streak so next cooldown requires two fresh losses.
            state.consecutive_losses = 0
            state.cooldown_until = None

    # Apply baseline checks (daily loss, etc.) on top of strict entry gates.
    base = evaluate_risk(_to_dict(state), now=now_dt)
    merged_state = _from_dict(base.updated_session_state)
    if merged_state.consecutive_losses >= 3:
        next_day_start = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        merged_state.status = "STOPPED"
        merged_state.stop_reason = "CONSECUTIVE_LOSSES_HARD_STOP"
        merged_state.cooldown_until = next_day_start.isoformat()
    errors.extend(base.errors)
    return _decision(merged_state, errors)


def register_trade_result(
    session_state: dict[str, Any],
    trade_pnl: float,
    trade_time: datetime | None = None,
) -> RiskDecision:
    """
    Update session state after a closed trade, then evaluate risk.

    This function applies hard per-trade loss cap:
        trade_pnl >= -max_loss_per_trade (with hard max cap <= 300)
    """
    state = _from_dict(session_state)
    trade_ts = (trade_time or _utc_now()).isoformat()

    actual_trade_pnl = float(trade_pnl)
    capped_trade_pnl = max(actual_trade_pnl, -state.max_loss_per_trade)
    state.actual_daily_pnl = round(state.actual_daily_pnl + actual_trade_pnl, 2)
    state.risk_capped_daily_pnl = round(state.risk_capped_daily_pnl + capped_trade_pnl, 2)
    state.daily_pnl = state.risk_capped_daily_pnl
    state.daily_trade_count += 1
    actual_loss = max(0.0, -actual_trade_pnl)
    tolerance_loss = float(state.max_loss_per_trade) * SLIPPAGE_TOLERANCE_MULTIPLIER
    emergency_loss = float(state.max_loss_per_trade) * HARD_EMERGENCY_MULTIPLIER
    if actual_loss >= emergency_loss:
        state.last_trade_risk_band = "EMERGENCY_BREACH"
        state.status = "STOPPED"
        state.stop_reason = "EMERGENCY_LOSS_BREACH"
    elif actual_loss >= tolerance_loss:
        state.last_trade_risk_band = "SLIPPAGE_TOLERANCE_BREACH"
    else:
        state.last_trade_risk_band = "WITHIN_RISK_BAND"
    state.trade_history.append(
        TradeRecord(
            pnl=round(capped_trade_pnl, 2),
            actual_pnl=round(actual_trade_pnl, 2),
            capped_pnl=round(capped_trade_pnl, 2),
            ts=trade_ts,
        )
    )

    if actual_trade_pnl < 0:
        state.consecutive_losses += 1
    else:
        state.consecutive_losses = 0
        state.cooldown_until = None

    return evaluate_risk(_to_dict(state), now=trade_time)


def evaluate_post_exit(
    session_state: dict[str, Any],
    trade_pnl: float,
    trade_time: datetime | None = None,
) -> RiskDecision:
    """
    Mandatory post-exit risk update.

    Updates daily PnL, trade counters, consecutive loss streak and cooldown,
    then applies hard-stop checks.
    """
    return register_trade_result(session_state, trade_pnl=trade_pnl, trade_time=trade_time)


# ==========================
# Unit tests (in-file)
# ==========================
if __name__ == "__main__":
    import unittest

    class RiskEngineTests(unittest.TestCase):
        def base_state(self) -> dict[str, Any]:
            return {
                "sessionId": "s1",
                "status": "ACTIVE",
                "daily_pnl": 0.0,
                "daily_trade_count": 0,
                "consecutive_losses": 0,
                "risk_amount_per_trade": 300.0,
                "daily_loss_limit": 3000.0,
                "daily_trade_cap": 20,
                "cooldown_minutes": 15,
                "trade_history": [],
            }

        def test_hard_limit_clamping(self) -> None:
            s = self.base_state()
            s["risk_amount_per_trade"] = 9999
            s["daily_loss_limit"] = 99999
            d = evaluate_risk(s)
            self.assertEqual(d.updated_session_state["risk_amount_per_trade"], 300.0)
            self.assertEqual(d.updated_session_state["daily_loss_limit"], 3000.0)

        def test_daily_loss_stop(self) -> None:
            s = self.base_state()
            s["daily_pnl"] = -3000.0
            d = evaluate_risk(s)
            self.assertFalse(d.approved)
            self.assertEqual(d.updated_session_state["status"], "STOPPED")
            self.assertEqual(d.updated_session_state["stop_reason"], "DAILY_LOSS_LIMIT")

        def test_trade_cap_stop(self) -> None:
            s = self.base_state()
            s["daily_trade_count"] = 20
            d = evaluate_risk(s)
            self.assertFalse(d.approved)
            self.assertEqual(d.updated_session_state["stop_reason"], "DAILY_TRADE_CAP")

        def test_entry_cooldown_after_two_losses(self) -> None:
            now = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
            s = self.base_state()
            s["consecutive_losses"] = 2
            d = evaluate_entry(s, now=now)
            self.assertFalse(d.approved)
            self.assertIn("Cooldown active", " | ".join(d.errors))
            self.assertIsNotNone(d.updated_session_state["cooldown_until"])

        def test_entry_hard_stop_after_three_losses(self) -> None:
            now = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
            s = self.base_state()
            s["consecutive_losses"] = 3
            d = evaluate_entry(s, now=now)
            self.assertFalse(d.approved)
            self.assertEqual(d.updated_session_state["status"], "STOPPED")
            self.assertEqual(d.updated_session_state["stop_reason"], "CONSECUTIVE_LOSSES_HARD_STOP")

        def test_cooldown_after_two_losses(self) -> None:
            now = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
            s = self.base_state()
            s["consecutive_losses"] = 2
            d = enforce_cooldown(s, now=now)
            self.assertFalse(d.approved)
            self.assertIn("Cooldown active", " | ".join(d.errors))
            self.assertIsNotNone(d.updated_session_state["cooldown_until"])

        def test_stop_after_three_losses(self) -> None:
            s = self.base_state()
            s["consecutive_losses"] = 3
            d = evaluate_risk(s)
            self.assertFalse(d.approved)
            self.assertEqual(d.updated_session_state["status"], "STOPPED")
            self.assertEqual(d.updated_session_state["stop_reason"], "CONSECUTIVE_LOSSES")

        def test_register_trade_caps_loss_per_trade(self) -> None:
            s = self.base_state()
            d = register_trade_result(s, trade_pnl=-900.0)
            hist = d.updated_session_state["trade_history"]
            self.assertEqual(len(hist), 1)
            self.assertEqual(hist[0]["pnl"], -300.0)
            self.assertEqual(hist[0]["actual_pnl"], -900.0)
            self.assertEqual(hist[0]["capped_pnl"], -300.0)
            self.assertEqual(d.updated_session_state["daily_pnl"], -300.0)
            self.assertEqual(d.updated_session_state["risk_capped_daily_pnl"], -300.0)
            self.assertEqual(d.updated_session_state["actual_daily_pnl"], -900.0)
            self.assertEqual(d.updated_session_state["last_trade_risk_band"], "EMERGENCY_BREACH")
            self.assertEqual(d.updated_session_state["stop_reason"], "EMERGENCY_LOSS_BREACH")

    unittest.main()
