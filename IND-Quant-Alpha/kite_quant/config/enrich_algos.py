"""One-off: add groups, marketCondition, instruments, entryLogic, exitLogic, stopLogic, tags to algos.json"""
import json
from pathlib import Path

path = Path(__file__).parent / "algos.json"
algos = json.load(path.open(encoding="utf-8"))

ID_TO_GROUPS = {
    "momentum_breakout": ["TREND_FOLLOWING"],
    "vwap_trend_ride": ["TREND_FOLLOWING"],
    "pullback_continuation": ["TREND_FOLLOWING"],
    "orb_opening_range_breakout": ["TREND_FOLLOWING"],
    "relative_strength_breakout": ["TREND_FOLLOWING"],
    "sector_rotation_momentum": ["TREND_FOLLOWING", "SMART_MONEY"],
    "index_lead_stock_lag": ["TREND_FOLLOWING"],
    "trend_day_vwap_hold": ["TREND_FOLLOWING"],
    "ema_ribbon_trend_alignment": ["TREND_FOLLOWING"],
    "vwap_reclaim": ["TREND_FOLLOWING"],
    "rsi_reversal_fade": ["MEAN_REVERSION"],
    "bollinger_mean_reversion": ["MEAN_REVERSION"],
    "vwap_mean_reversion": ["MEAN_REVERSION"],
    "liquidity_sweep_reversal": ["MEAN_REVERSION", "SMART_MONEY"],
    "failed_breakdown_trap": ["MEAN_REVERSION"],
    "inside_bar_breakout": ["VOLATILITY_BREAKOUT"],
    "news_volatility_burst": ["VOLATILITY_BREAKOUT"],
    "time_based_volatility_play": ["VOLATILITY_BREAKOUT"],
    "range_compression_breakout": ["VOLATILITY_BREAKOUT"],
    "volume_dry_up_breakout": ["VOLATILITY_BREAKOUT"],
    "iv_expansion_play": ["OPTIONS_EDGE"],
    "gamma_scalping_lite": ["OPTIONS_EDGE"],
    "straddle_breakout": ["OPTIONS_EDGE"],
    "volume_climax_reversal": ["SMART_MONEY"],
    "daily_breakout_continuation": ["SWING"],
    "pullback_20_50_dma": ["SWING"],
    "weekly_range_breakout": ["SWING"],
    "gap_and_go_swing": ["SWING"],
    "stage2_trend_breakout": ["SWING"],
    "swing_rsi_compression_breakout": ["SWING"],
    "darvas_box_breakout": ["SWING"],
    "relative_strength_swing_leader": ["SWING"],
    "trendline_break_retest": ["SWING"],
    "swing_volume_accumulation": ["SWING"],
}
ADVANCED_IDS = [
    "market_regime_detection", "multi_timeframe_alignment", "liquidity_zone_reaction",
    "order_flow_imbalance_proxy", "volatility_contraction_expansion", "time_of_day_behavior",
    "smart_money_trap_detection", "options_flow_bias", "volatility_regime_switch",
    "risk_adaptive_position_sizing",
]
for aid in ADVANCED_IDS:
    ID_TO_GROUPS[aid] = ["ADVANCED"]


def market_condition(market_type, best_use):
    mt = (market_type or "").upper()
    if mt == "TREND":
        return ["TRENDING", "DIRECTIONAL"]
    if mt == "RANGE":
        return ["RANGE_BOUND", "SIDEWAYS"]
    if mt in ("VOLATILE", "EVENT"):
        return ["VOLATILE", "EVENT_DRIVEN"]
    if mt == "OPTIONS":
        return ["OPTIONS", "IV_SENSITIVE"]
    if mt == "ADVANCED":
        return ["ANY"]
    return ["GENERAL"]


def instruments(good_for):
    if not good_for:
        return ["EQUITY", "OPTIONS"]
    out = []
    if "stock" in good_for:
        out.append("EQUITY")
    if "index" in good_for:
        out.append("INDEX")
    if "options" in good_for:
        out.append("OPTIONS")
    return out if out else ["EQUITY", "OPTIONS"]


def tags(name, desc):
    words = ((name or "") + " " + (desc or "")).lower()
    keywords = [
        "momentum", "breakout", "trend", "vwap", "reversal", "mean reversion", "volatility",
        "options", "swing", "rsi", "bollinger", "liquidity", "straddle", "iv", "gamma",
        "sector", "index", "relative strength", "volume", "pullback", "orb", "gap", "darvas",
        "trendline", "accumulation", "regime", "trap", "sizing",
    ]
    t = set()
    for w in keywords:
        if w in words:
            t.add(w.replace(" ", "_"))
    return list(t)[:8]


for a in algos:
    aid = a.get("id", "")
    a["groups"] = ID_TO_GROUPS.get(aid, ["TREND_FOLLOWING"])
    a["marketCondition"] = a.get("marketCondition") or market_condition(a.get("marketType"), a.get("bestUseCase"))
    a["instruments"] = a.get("instruments") or instruments(a.get("goodFor", []))
    er = a.get("entryRules") or []
    a["entryLogic"] = a.get("entryLogic") or (er[0] if er else (a.get("description") or "")[:200])
    a["exitLogic"] = a.get("exitLogic") or ("Exit on stop or target; avoid: " + (a.get("avoidWhen") or "—"))
    a["stopLogic"] = a.get("stopLogic") or ("Stop below/above structure or VWAP break; risk " + (a.get("riskLevel") or "MEDIUM"))
    a["tags"] = a.get("tags") or tags(a.get("name"), a.get("description"))

path.write_text(json.dumps(algos, indent=2), encoding="utf-8")
print("Updated", len(algos), "algos")
