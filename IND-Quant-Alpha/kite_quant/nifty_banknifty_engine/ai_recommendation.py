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
    nifty_score = float(bias_data.get("niftyScore") or 0.0)
    bank_nifty_score = float(bias_data.get("bankNiftyScore") or 0.0)
    label = (index_label or "").upper().replace(" ", "")
    fallback_bias_used = False
    fallback_bias_reason = None
    if "BANK" in label:
        bias = bank_nifty_bias
        score = bank_nifty_score
        other_bias = nifty_bias
        label = "BANKNIFTY"
    else:
        bias = nifty_bias
        score = nifty_score
        other_bias = bank_nifty_bias
        label = "NIFTY"

    # Neutral bias is common around flat/choppy candles and can block one index while the other is tradable.
    # Resolve safely with a light fallback before giving up:
    # 1) use selected index micro-score direction if meaningful,
    # 2) else use cross-index proxy only if it has clear direction.
    if bias == "NEUTRAL":
        if score >= 0.05:
            bias = "BULLISH"
            fallback_bias_used = True
            fallback_bias_reason = f"{label} neutral overridden by positive score ({score:.2f})"
        elif score <= -0.05:
            bias = "BEARISH"
            fallback_bias_used = True
            fallback_bias_reason = f"{label} neutral overridden by negative score ({score:.2f})"
        elif other_bias in ("BULLISH", "BEARISH"):
            bias = other_bias
            fallback_bias_used = True
            fallback_bias_reason = f"{label} neutral overridden by cross-index proxy ({other_bias})"
        else:
            return None

    from engine.position_sizing import calculate_fo_position_size
    from engine.zerodha_client import get_nfo_option_contract

    options, ai_rec, _ = get_affordable_index_options(
        label, bias, capital, confidence=bias_data.get("confidence")
    )
    if not options:
        return None
    best = options[0]
    opt_type = best.get("type", "CE")
    strike = best.get("strike", 0)
    lot_size = int(best.get("lotSize", 25) or 25)
    premium = best.get("premium", 0)
    tradingsymbol_nfo = None
    contract = get_nfo_option_contract(label, strike, opt_type)
    if contract:
        tradingsymbol_nfo = contract.get("tradingsymbol")
        broker_lot_size = contract.get("lot_size")
        if broker_lot_size and int(broker_lot_size) > 0:
            lot_size = int(broker_lot_size)

    lots, total_cost, can_afford = calculate_fo_position_size(capital, premium, lot_size)
    if not can_afford or lots < 1:
        logger.info("[F&O] Insufficient capital for %s. Recommended 0 lots.", label)
        return None

    risk_per_trade = min(capital * 0.02, total_cost)
    market_bias = "Bullish" if bias == "BULLISH" else "Bearish"
    premium = best.get("premium", 0)
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
        "totalCost": round(total_cost, 2),
        "product_type": "OPTION",
        "exchange": "NFO",
        "lot_size": lot_size,
        "lotSize": lot_size,
        "premium": round(premium, 2),
    }
    if fallback_bias_used:
        # Keep fallback confidence conservative so downstream filters can remain strict.
        try:
            rec_out["confidence"] = min(int(rec_out.get("confidence", 65)), 65)
        except Exception:
            rec_out["confidence"] = 65
        rec_out["fallbackBiasUsed"] = True
        rec_out["fallbackBiasReason"] = fallback_bias_reason
    if tradingsymbol_nfo:
        rec_out["tradingsymbol"] = tradingsymbol_nfo
    return rec_out
