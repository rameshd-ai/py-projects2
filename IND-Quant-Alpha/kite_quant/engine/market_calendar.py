"""
Market Intelligence Calendar – expiry, events, earnings, AI market mood.
Single module for all calendar logic; used by /api/market-calendar and later by AI engine.
"""
from __future__ import annotations

import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Base dir: kite_quant (parent of engine)
_BASE_DIR = Path(__file__).resolve().parent.parent


def _nse_holidays_path() -> Path:
    return _BASE_DIR / "nse_holidays.json"


# ---------------------------------------------------------------------------
# Economic events (date -> list of { type, impact }). Update as needed.
# Types: RBI_POLICY, US_CPI, US_FED, INDIA_CPI, BUDGET, ELECTION, GLOBAL_EVENT
# ---------------------------------------------------------------------------
ECONOMIC_EVENTS: list[dict[str, Any]] = [
    {"date": "2026-02-12", "type": "US_CPI", "impact": "HIGH"},
    {"date": "2026-02-20", "type": "RBI_POLICY", "impact": "HIGH"},
    {"date": "2026-03-11", "type": "US_CPI", "impact": "HIGH"},
    {"date": "2026-04-10", "type": "US_CPI", "impact": "HIGH"},
    {"date": "2026-06-18", "type": "US_FED", "impact": "HIGH"},
    {"date": "2026-07-02", "type": "RBI_POLICY", "impact": "HIGH"},
]

# ---------------------------------------------------------------------------
# Earnings (symbol, impact, optional summary, info_url). Major F&O stocks.
# impact = HIGH when results move sector/index (large-cap, index weight).
# ---------------------------------------------------------------------------
EARNINGS_EVENTS: list[dict[str, Any]] = [
    {"date": "2026-02-10", "symbol": "HDFCBANK", "impact": "HIGH",
     "summary": "HDFC Bank results; heavy Nifty weight. Drives banking sentiment.",
     "info_url": "https://www.nseindia.com/get-quotes/equity?symbol=HDFCBANK"},
    {"date": "2026-02-12", "symbol": "RELIANCE", "impact": "HIGH",
     "summary": "Reliance Industries earnings; largest index constituent. O2C & retail key.",
     "info_url": "https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE"},
    {"date": "2026-02-14", "symbol": "TCS", "impact": "HIGH",
     "summary": "Tata Consultancy Services quarterly results. IT bellwether; sets tone for IT sector and Nifty IT index.",
     "info_url": "https://www.nseindia.com/get-quotes/equity?symbol=TCS"},
    {"date": "2026-02-18", "symbol": "INFY", "impact": "HIGH",
     "summary": "Infosys results; major IT stock. Often moves in tandem with TCS on sector view.",
     "info_url": "https://www.nseindia.com/get-quotes/equity?symbol=INFY"},
    {"date": "2026-03-05", "symbol": "ICICIBANK", "impact": "HIGH",
     "summary": "ICICI Bank earnings; key private bank. Affects banking and Nifty sentiment.",
     "info_url": "https://www.nseindia.com/get-quotes/equity?symbol=ICICIBANK"},
]


def _load_nse_holidays() -> set[str]:
    """Load NSE holidays as set of YYYY-MM-DD."""
    path = _nse_holidays_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("holidays") or [])
        except Exception:
            pass
    return set()


def _is_trading_day(d: date, holidays: set[str]) -> bool:
    """True if weekday and not in holidays."""
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in holidays


def _previous_trading_day(d: date, holidays: set[str]) -> date:
    """Previous trading day (step back until we hit a trading day)."""
    cur = d
    for _ in range(10):
        cur = cur - timedelta(days=1)
        if _is_trading_day(cur, holidays):
            return cur
    return cur


def get_expiry_type_clean(d: date, holidays: set[str]) -> str | None:
    """Simpler expiry: Weekly = Thursday (or Wed if Thu holiday). Monthly = last Thu (or prev trading)."""
    if not _is_trading_day(d, holidays):
        return None
    thursday = 3
    _, month = d.year, d.month
    last = monthrange(d.year, month)[1]
    last_thu = None
    for day in range(last, 0, -1):
        try:
            c = date(d.year, month, day)
            if c.weekday() == thursday:
                last_thu = c
                break
        except ValueError:
            continue
    if last_thu is not None:
        if d == last_thu:
            return "MONTHLY"
        if last_thu.isoformat() in holidays:
            prev = _previous_trading_day(last_thu, holidays)
            if d == prev:
                return "MONTHLY"
    # Weekly: every Thursday; if Thursday is holiday then Wednesday
    if d.weekday() == thursday:
        return "WEEKLY"
    if d.weekday() == 2:  # Wednesday – weekly expiry if Thu is holiday
        next_thu = d + timedelta(days=1)
        if next_thu.isoformat() in holidays:
            return "WEEKLY"
    return None


def get_expiry_type_for_date(d: date) -> str | None:
    """Public helper: return WEEKLY/MONTHLY expiry type for a date, else None."""
    holidays = _load_nse_holidays()
    return get_expiry_type_clean(d, holidays)


def get_events_for_date(d: date) -> list[dict[str, str]]:
    """Return economic events for date. Format: [{ type, impact }, ...]."""
    ds = d.isoformat()
    return [{"type": e["type"], "impact": e.get("impact", "MEDIUM")} for e in ECONOMIC_EVENTS if e.get("date") == ds]


def get_earnings_for_date(d: date) -> list[dict[str, Any]]:
    """Return earnings for date. Format: [{ symbol, impact, summary?, info_url? }, ...]."""
    ds = d.isoformat()
    out = []
    for e in EARNINGS_EVENTS:
        if e.get("date") != ds:
            continue
        item = {"symbol": e["symbol"], "impact": e.get("impact", "MEDIUM")}
        if e.get("summary"):
            item["summary"] = e["summary"]
        if e.get("info_url"):
            item["info_url"] = e["info_url"]
        out.append(item)
    return out


def get_market_mood(
    d: date,
    is_holiday: bool,
    is_expiry: str | None,
    events: list[dict],
    earnings: list[dict],
) -> dict[str, Any]:
    """
    AI-estimated market mood for the day.
    Returns { type, confidence, reason }.
    type: TRENDING | RANGE | VOLATILE | EVENT_RISK
    """
    if is_holiday:
        return {"type": "RANGE", "confidence": 100, "reason": "Market closed"}
    high_impact_events = [e for e in events if e.get("impact") == "HIGH"]
    high_earnings = [e for e in earnings if e.get("impact") == "HIGH"]
    reasons = []
    confidence = 70
    if is_expiry:
        reasons.append(f"{'Monthly' if is_expiry == 'MONTHLY' else 'Weekly'} expiry")
        mood = "VOLATILE"
        confidence = 78
    elif high_impact_events or high_earnings:
        if high_impact_events:
            reasons.append("High-impact event: " + ", ".join(e.get("type", "") for e in high_impact_events))
        if high_earnings:
            reasons.append("Earnings: " + ", ".join(e.get("symbol", "") for e in high_earnings))
        mood = "EVENT_RISK"
        confidence = 75
    elif events or earnings:
        reasons.append("Low-impact events")
        mood = "RANGE"
        confidence = 65
    else:
        mood = "RANGE"
        reasons.append("No major events – typical range day")
    return {
        "type": mood,
        "confidence": confidence,
        "reason": "; ".join(reasons) if reasons else "No significant drivers",
    }


def get_calendar_for_month(month_yyyy_mm: str) -> list[dict[str, Any]]:
    """
    Return list of day objects for the given month (YYYY-MM).
    Each item: date, isHoliday, isExpiry, events, earnings, aiMarketMood.
    """
    holidays = _load_nse_holidays()
    try:
        year, month = int(month_yyyy_mm[:4]), int(month_yyyy_mm[5:7])
    except (ValueError, IndexError):
        year, month = datetime.now().year, datetime.now().month
    _, last_day = monthrange(year, month)
    out = []
    for day in range(1, last_day + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        ds = d.isoformat()
        is_holiday = ds in holidays
        is_expiry = get_expiry_type_clean(d, holidays) if not is_holiday else None
        events = get_events_for_date(d)
        earnings = get_earnings_for_date(d)
        ai_mood = get_market_mood(d, is_holiday, is_expiry, events, earnings)
        out.append({
            "date": ds,
            "isHoliday": is_holiday,
            "isExpiry": is_expiry,
            "events": events,
            "earnings": earnings,
            "aiMarketMood": ai_mood,
        })
    return out
