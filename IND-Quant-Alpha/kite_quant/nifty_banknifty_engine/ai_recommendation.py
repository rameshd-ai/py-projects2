"""
AI trade recommendation for NIFTY/BANKNIFTY index options only.
"""
from __future__ import annotations

import logging
from typing import Any

from .bias import get_index_market_bias
from .options import get_affordable_index_options

logger = logging.getLogger(__name__)


def build_ai_trade_recommendation_index(
    index_label: str, capital: float, bias_data: dict | None = None
) -> dict[str, Any] | None:
    """
    Build a single AI trade recommendation for NIFTY or BANKNIFTY.
    Optional bias_data avoids re-fetch. Returns None if neutral or insufficient capital.
    """
    if bias_data is None:
        bias_data = get_index_market_bias()
    nifty_bias = bias_data.get("niftyBias", "NEUTRAL")
    bank_nifty_bias = bias_data.get("bankNiftyBias", "NEUTRAL")
    label = (index_label or "").upper().replace(" ", "")
    if "BANK" in label:
        bias = bank_nifty_bias
        label = "BANKNIFTY"
    else:
        bias = nifty_bias
        label = "NIFTY"
    if bias == "NEUTRAL":
        return None

    from engine.position_sizing import calculate_fo_position_size
    from engine.zerodha_client import get_nfo_option_tradingsymbol

    options, ai_rec, _ = get_affordable_index_options(
        label, bias, capital, confidence=bias_data.get("confidence")
    )
    if not options:
        return None
    best = options[0]
    opt_type = best.get("type", "CE")
    strike = best.get("strike", 0)
    lot_size = best.get("lotSize", 25)
    premium = best.get("premium", 0)

    lots, total_cost, can_afford = calculate_fo_position_size(capital, premium, lot_size)
    if not can_afford or lots < 1:
        logger.info("[F&O] Insufficient capital for %s. Recommended 0 lots.", label)
        return None

    risk_per_trade = min(capital * 0.02, total_cost)
    market_bias = "Bullish" if bias == "BULLISH" else "Bearish"
    premium = best.get("premium", 0)
    tradingsymbol_nfo = get_nfo_option_tradingsymbol(label, strike, opt_type)
    rec_out = {
        "instrumentType": "index",
        "instrument": label,
        "symbol": label,
        "marketBias": market_bias,
        "strategyId": "index_lead_stock_lag",
        "strategyName": "Index Momentum",
        "tradeType": "CALL" if opt_type == "CE" else "PUT",
        "suggestedStrike": str(strike) + " " + opt_type,
        "strike": strike,
        "optionType": opt_type,
        "entryCondition": "Index holds above/below open; momentum confirmation",
        "stopLossLogic": "Break of opening range / VWAP",
        "riskPerTrade": round(risk_per_trade, 2),
        "positionSizeLots": lots,
        "rewardLogic": "Trail or 20-90 min holding time",
        "confidence": ai_rec.get("confidence", 65),
        "totalCost": round(total_cost * lots, 2),
        "product_type": "OPTION",
        "exchange": "NFO",
        "lot_size": lot_size,
        "lotSize": lot_size,
        "premium": round(premium, 2),
    }
    if tradingsymbol_nfo:
        rec_out["tradingsymbol"] = tradingsymbol_nfo
    return rec_out
