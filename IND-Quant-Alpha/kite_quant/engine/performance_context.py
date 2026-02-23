from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_TRADE_HISTORY_FILE = _DATA_DIR / "trade_history.json"
_BROKER_ORDERS_HISTORY_FILE = _DATA_DIR / "live_broker_orders_history.json"


def _parse_ts(raw_ts: Any) -> datetime | None:
    if raw_ts is None:
        return None
    s = str(raw_ts).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _estimate_order_charges(side: str, avg_price: float, qty: float, symbol: str) -> float:
    if avg_price <= 0 or qty <= 0:
        return 0.0
    turnover = avg_price * qty
    is_buy = str(side or "").upper() == "BUY"
    sym = str(symbol or "").upper()
    is_options = sym.endswith("CE") or sym.endswith("PE")
    brokerage = 20.0 if is_options else min(20.0, turnover * 0.0003)
    txn = turnover * 0.0003503
    sebi = turnover * 0.000001
    stamp = turnover * 0.00003 if is_buy else 0.0
    stt = 0.0 if is_buy else turnover * 0.001
    gst = 0.18 * (brokerage + txn + sebi)
    return brokerage + txn + sebi + stamp + stt + gst


def build_live_performance_context(
    max_trades: int = 20,
    current_session_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build charge-aware, rolling live performance metrics for AI prompts/gates.
    """
    today = datetime.now(IST).date()

    trade_rows = (_read_json(_TRADE_HISTORY_FILE).get("trades") or [])
    live_today: list[dict[str, Any]] = []
    for t in trade_rows:
        if not isinstance(t, dict):
            continue
        if str(t.get("mode") or "").upper() != "LIVE":
            continue
        et = _parse_ts(t.get("entry_time"))
        if not et or et.date() != today:
            continue
        live_today.append(t)

    live_today.sort(key=lambda x: str(x.get("entry_time") or ""))
    recent = live_today[-max_trades:] if max_trades > 0 else live_today

    def _f(v: Any) -> float:
        try:
            return float(v or 0.0)
        except Exception:
            return 0.0

    net_values = [_f(t.get("net_pnl", t.get("pnl"))) for t in recent]
    gross_values = [_f(t.get("gross_pnl", t.get("net_pnl", t.get("pnl")))) for t in recent]

    trades_count = len(recent)
    wins = sum(1 for n in net_values if n > 0)
    losses = sum(1 for n in net_values if n < 0)
    win_rate = (wins / trades_count * 100.0) if trades_count > 0 else 0.0
    net_total = sum(net_values)
    gross_total = sum(gross_values)
    avg_net = (net_total / trades_count) if trades_count > 0 else 0.0

    recent_5 = net_values[-5:]
    prev_5 = net_values[-10:-5]
    recent_5_net = sum(recent_5) if recent_5 else 0.0
    prev_5_net = sum(prev_5) if prev_5 else 0.0
    net_decay_vs_prev5 = (recent_5_net - prev_5_net) if prev_5 else None

    order_rows = (_read_json(_BROKER_ORDERS_HISTORY_FILE).get("orders") or [])
    executed_orders_today = 0
    estimated_charges_today = 0.0
    for o in order_rows:
        if not isinstance(o, dict):
            continue
        ts = _parse_ts(o.get("order_timestamp"))
        if not ts or ts.date() != today:
            continue
        status = str(o.get("status") or "").upper()
        filled_qty = _f(o.get("filled_quantity"))
        if not (status == "COMPLETE" or filled_qty > 0):
            continue
        qty = filled_qty if filled_qty > 0 else _f(o.get("quantity"))
        avg = _f(o.get("average_price"))
        estimated_charges_today += _estimate_order_charges(
            side=str(o.get("side") or ""),
            avg_price=avg,
            qty=qty,
            symbol=str(o.get("symbol") or ""),
        )
        executed_orders_today += 1

    charges_to_gross_pct = None
    if gross_total > 0:
        charges_to_gross_pct = (estimated_charges_today / gross_total) * 100.0

    charges_dominate = (
        (gross_total > 0 and estimated_charges_today >= (gross_total * 0.60))
        or (trades_count >= 8 and estimated_charges_today >= 300 and net_total <= 0)
    )
    churn_score = min(
        100.0,
        (trades_count * 6.0) + (executed_orders_today * 1.2) + (20.0 if charges_dominate else 0.0),
    )
    low_edge_block = bool(
        charges_dominate and (win_rate < 55.0 or avg_net < 75.0 or (net_decay_vs_prev5 is not None and net_decay_vs_prev5 < 0))
    )

    # Lightweight learning profile from historical setups (if setup_features are present).
    hist_live = [t for t in trade_rows if isinstance(t, dict) and str(t.get("mode") or "").upper() == "LIVE"]
    hist_recent = hist_live[-120:]
    learned_matches: list[dict[str, Any]] = []
    current_bucket = str((current_session_features or {}).get("first_hour_breakout") or "na").lower()
    current_vwap_side = str((current_session_features or {}).get("vwap_side") or "na").lower()
    for t in hist_recent:
        sf = t.get("setup_features") if isinstance(t.get("setup_features"), dict) else {}
        sf_session = sf.get("session_features") if isinstance(sf.get("session_features"), dict) else {}
        if current_bucket != "na":
            b = str(sf_session.get("first_hour_breakout") or "na").lower()
            if b != current_bucket:
                continue
        if current_vwap_side != "na":
            vs = str(sf_session.get("vwap_side") or "na").lower()
            if vs != current_vwap_side:
                continue
        learned_matches.append(t)
    lm_count = len(learned_matches)
    learned_net = sum(_f(t.get("net_pnl", t.get("pnl"))) for t in learned_matches)
    learned_wins = sum(1 for t in learned_matches if _f(t.get("net_pnl", t.get("pnl"))) > 0)
    learned_win_rate = (learned_wins / lm_count * 100.0) if lm_count > 0 else 0.0
    learned_avg = (learned_net / lm_count) if lm_count > 0 else 0.0
    learned_quality_score = 50.0
    if lm_count >= 5:
        learned_quality_score = max(0.0, min(100.0, (learned_win_rate * 0.6) + (50.0 if learned_avg > 0 else 25.0)))
    learned_block = bool(lm_count >= 6 and (learned_win_rate < 45.0 or learned_avg < 0.0))

    return {
        "date_ist": today.isoformat(),
        "window_trades_count": trades_count,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(win_rate, 2),
        "net_pnl_total": round(net_total, 2),
        "gross_pnl_total": round(gross_total, 2),
        "avg_net_pnl_per_trade": round(avg_net, 2),
        "recent_5_net_pnl": round(recent_5_net, 2),
        "prev_5_net_pnl": round(prev_5_net, 2) if prev_5 else None,
        "net_decay_vs_prev5": round(net_decay_vs_prev5, 2) if net_decay_vs_prev5 is not None else None,
        "executed_orders_today": int(executed_orders_today),
        "estimated_charges_today": round(estimated_charges_today, 2),
        "charges_to_gross_pct": round(charges_to_gross_pct, 2) if charges_to_gross_pct is not None else None,
        "charges_dominate": charges_dominate,
        "churn_score": round(churn_score, 1),
        "low_edge_block": low_edge_block,
        "learned_setup_matches": lm_count,
        "learned_setup_win_rate_pct": round(learned_win_rate, 2),
        "learned_setup_avg_net_pnl": round(learned_avg, 2),
        "learned_quality_score": round(learned_quality_score, 2),
        "learned_block": learned_block,
    }
