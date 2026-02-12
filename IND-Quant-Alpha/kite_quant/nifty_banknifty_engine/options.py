"""
Index option candidates and affordable options for NIFTY/BANKNIFTY only.
Same logic used by Backtest, Paper, and Live.
"""
from __future__ import annotations

from .constants import (
    NIFTY,
    BANKNIFTY,
    INDEX_NAMES,
    normalize_index_name,
    get_strike_step_and_lot_size,
    default_spot,
)
from .live_data import fetch_nifty50_live, fetch_bank_nifty_live


def get_index_option_candidates(
    index_name: str, bias: str, spot: float
) -> list[dict]:
    """
    Build option candidates (ATM, 1 OTM, 2 OTM) for index in the given direction.
    CE for BULLISH, PE for BEARISH. Same premium model used by Live, Paper, and Backtest.
    Returns list of dicts: type, strike, premium, lotSize, distanceFromATM, etc.
    """
    index_name = normalize_index_name(index_name)
    strike_step, lot_size = get_strike_step_and_lot_size(index_name)
    if spot <= 0:
        spot = default_spot(index_name)
    base_strike = round(spot / strike_step) * strike_step
    use_ce = bias == "BULLISH"
    strikes = (
        [base_strike, base_strike + strike_step, base_strike + 2 * strike_step]
        if use_ce
        else [base_strike, base_strike - strike_step, base_strike - 2 * strike_step]
    )
    options = []
    for i, strike in enumerate(strikes):
        if use_ce:
            prem = max(50, 80 - (strike - spot) / 2 + (30 if i == 0 else 0))
        else:
            prem = max(50, 80 + (spot - strike) / 2 + (30 if i == 0 else 0))
        prem = round(prem, 2)
        total_cost = prem * lot_size
        options.append({
            "type": "CE" if use_ce else "PE",
            "strike": strike,
            "premium": prem,
            "lotSize": lot_size,
            "lotCost": total_cost,
            "totalCost": round(total_cost, 2),
            "distanceFromATM": i,
        })
    return options


def pick_best_index_option(candidates: list[dict], capital: float) -> dict | None:
    """
    Pick best index option: lower premium = more lots (same logic for Live, Paper, Backtest).
    Sorts by premium ascending, then by distanceFromATM; returns first affordable option.
    """
    from engine.position_sizing import calculate_fo_position_size
    sorted_candidates = sorted(
        candidates, key=lambda x: (x["premium"], x["distanceFromATM"])
    )
    for opt in sorted_candidates:
        lots, total_cost, can_afford = calculate_fo_position_size(
            capital, opt["premium"], opt["lotSize"]
        )
        if can_afford and lots >= 1:
            opt["status"] = "Affordable"
            opt["canTrade"] = True
            return opt
    return None


def get_affordable_index_options(
    index_name: str,
    bias: str,
    max_risk_per_trade: float,
    confidence: int | None = None,
) -> tuple[list, dict, bool]:
    """
    Get affordable index options. CE/PE from bias (BULLISH→CE, BEARISH→PE).
    Same logic used in Backtest and Live/Paper.
    Returns (options_list sorted by premium, ai_recommendation, safe_to_show).
    """
    index_name = (index_name or "").upper().replace(" ", "")
    if index_name not in INDEX_NAMES:
        index_name = BANKNIFTY if "BANK" in index_name else NIFTY

    if bias == "NEUTRAL":
        return [], {}, False

    quote_symbol = "NIFTY BANK" if index_name == BANKNIFTY else "NIFTY 50"
    try:
        if quote_symbol == "NIFTY 50":
            live = fetch_nifty50_live()
        else:
            live = fetch_bank_nifty_live()
        spot = float(live.get("price") or live.get("open") or 0)
    except Exception:
        spot = default_spot(index_name)
    if spot <= 0:
        spot = default_spot(index_name)

    candidates = get_index_option_candidates(index_name, bias, spot)
    options_sorted = sorted(
        candidates, key=lambda x: (x["premium"], x["distanceFromATM"])
    )
    for o in options_sorted:
        total_cost = o["premium"] * o["lotSize"]
        o["status"] = "Affordable" if total_cost <= max_risk_per_trade else "Over Budget"
        o["canTrade"] = total_cost <= max_risk_per_trade
    top = options_sorted[:3]

    use_ce = bias == "BULLISH"
    direction = "BUY CE" if use_ce else "BUY PE"
    move_type = "Momentum" if bias in ("BULLISH", "BEARISH") else "Reversal"
    summary = (
        f"{'NIFTY' if index_name == NIFTY else 'Bank Nifty'} is trading "
        f"{'above' if bias == 'BULLISH' else 'below'} open with {bias.lower()} intraday bias. "
        "AI selects best premium (lower premium = more lots)."
    )
    rec = {
        "direction": direction,
        "confidence": confidence if confidence is not None else 65,
        "expectedMoveType": move_type,
        "holdingTime": "20-90 min",
        "summary": summary,
    }
    safe = bias != "NEUTRAL" and (float(max_risk_per_trade) > 0)
    return top, rec, safe
