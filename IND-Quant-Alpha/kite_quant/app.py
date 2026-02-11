"""
Flask server: dashboard, Start/Stop trading, 2:30 scheduler, /api/live, Kill Switch, Settings.
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
from flask import Flask, jsonify, redirect, render_template, request, url_for, Response
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

from engine.config_store import CONFIG_KEYS, apply_config_to_env, load_config, save_config
apply_config_to_env()

from engine.ai_strategy_advisor import get_market_context, get_ai_strategy_recommendation, should_switch_strategy
from engine.trade_frequency import calculate_max_trades_per_hour, get_frequency_status, get_trade_frequency_config, save_trade_frequency_config
from engine.strategy import compute_us_bias, suggest_min_trades, consensus_signal, compute_technicals
from engine.data_fetcher import (
    fetch_nse_quote,
    get_historical_for_backtest,
    get_historical_for_prediction,
    get_ohlc_for_date,
    fetch_nifty50_live,
    fetch_bank_nifty_live,
    fetch_india_vix,
    fetch_nse_ohlc,
)
from engine.sentiment_engine import get_sentiment_for_symbol
from engine.session_manager import get_session_manager, SessionStatus
from engine.backtest import run_backtest
from engine.zerodha_client import get_positions, get_balance, get_zerodha_profile_info, kill_switch, search_instruments, get_quotes_bulk, get_nfo_option_tradingsymbol
from engine.ai_strategy_advisor import get_market_context, get_ai_strategy_recommendation, should_switch_strategy
from execution.executor import execute_entry, execute_exit, get_balance_for_mode
from execution.trade_history_store import get_trade_history as get_stored_trade_history
from strategies import data_provider as strategy_data_provider
from strategies.strategy_registry import get_strategy_for_session
from risk.risk_manager import RiskConfig, RiskManager
from engine.market_calendar import get_calendar_for_month
from engine.algo_engine import load_algos, get_algo_by_id, get_suggested_algos, load_strategy_groups, get_algos_grouped, get_primary_group
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta, time
from functools import lru_cache
from threading import Lock, Thread
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    from backports.zoneinfo import ZoneInfo

# --- CACHING (real money: no room for stale data) ---
# NEVER CACHED: balance, positions, live price, orders — always fresh from Zerodha/poll.
# Cached only for performance, with short TTL + cleared at start of each calendar day (IST).
_news_cache: dict[str, tuple[list, datetime]] = {}
_prediction_cache: dict[str, tuple[dict, datetime]] = {}
_us_bias_cache: tuple[Any, datetime] | None = None
_last_cache_clear_date_ist: str | None = None  # ISO date (IST); clear all caches when this changes
_cache_lock = Lock()
NEWS_CACHE_TTL = timedelta(minutes=5)  # 5 min max — affects sentiment
PREDICTION_CACHE_TTL = timedelta(minutes=3)  # 3 min during market — trading decisions
US_BIAS_CACHE_TTL = timedelta(hours=2)  # 2h so India morning gets latest US close
US_BIAS_ERROR_CACHE_TTL = timedelta(minutes=1)  # Retry quickly if fetch failed

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production")
# Enable auto-reload for templates and code
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # Disable caching for development

# Never cache API responses (real money: avoid any stale data in browser)
@app.after_request
def after_request(response):
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif os.getenv("FLASK_ENV", "development").lower() == "development":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    """Single-page dashboard (all sections in one page)."""
    return render_template("dashboard.html")


@app.route("/dashboard/overview")
def dashboard_overview():
    return render_template("dashboard/overview.html", active_page="overview", page_title="Overview")


@app.route("/dashboard/analytics")
def dashboard_analytics():
    return render_template("dashboard/analytics.html", active_page="analytics", page_title="Analytics")


@app.route("/dashboard/zerodha")
def dashboard_zerodha():
    return render_template("dashboard/zerodha.html", active_page="zerodha", page_title="My Zerodha")


@app.route("/dashboard/ai-agent")
def dashboard_ai_agent():
    return render_template("dashboard/ai_agent.html", active_page="ai_agent", page_title="AI Trading Agent")


@app.route("/dashboard/backtest")
def dashboard_backtest():
    return render_template("dashboard/backtest.html", active_page="backtest", page_title="Backtesting")


# Algo ids that have executable strategy logic (check_entry, check_exit, SL/target). Others fall back to MomentumBreakout.
IMPLEMENTED_ALGO_IDS = frozenset({
    "momentum_breakout", "vwap_trend_ride", "rsi_reversal_fade", "orb_opening_range_breakout", "index_lead_stock_lag",
    "pullback_continuation",
    "bollinger_mean_reversion", "vwap_mean_reversion", "liquidity_sweep_reversal", "inside_bar_breakout",
    "news_volatility_burst", "time_based_volatility_play", "gamma_scalping_lite",
    "sector_rotation_momentum", "relative_strength_breakout", "volume_climax_reversal",
    "trend_day_vwap_hold", "ema_ribbon_trend_alignment",
    "range_compression_breakout", "failed_breakdown_trap", "vwap_reclaim",
    "volume_dry_up_breakout", "daily_breakout_continuation",
    "pullback_20_50_dma", "swing_rsi_compression_breakout", "swing_volume_accumulation",
    "multi_timeframe_alignment", "liquidity_zone_reaction", "order_flow_imbalance_proxy",
    "volatility_contraction_expansion", "time_of_day_behavior", "smart_money_trap_detection",
})


@app.route("/dashboard/algo-library")
def dashboard_algo_library():
    """Strategy Library: strategies grouped by market behavior, collapsible sections."""
    groups_meta = sorted(load_strategy_groups(), key=lambda g: g.get("order", 99))
    grouped = get_algos_grouped()
    groups_with_algos = [
        {"group": g, "algos": grouped.get(g["id"], [])}
        for g in groups_meta
        if grouped.get(g["id"], [])
    ]
    return render_template(
        "dashboard/strategy_library.html",
        active_page="algo_library",
        page_title="Strategy Library",
        groups_with_algos=groups_with_algos,
        implemented_algo_ids=IMPLEMENTED_ALGO_IDS,
    )


@app.route("/dashboard/algo-library/<algo_id>")
def dashboard_algo_detail(algo_id: str):
    """Single algo detail page (educational)."""
    algo = get_algo_by_id(algo_id)
    if not algo:
        return redirect(url_for("dashboard_algo_library"))
    return render_template("dashboard/algo_detail.html", active_page="algo_library", page_title=algo.get("name", "Algo"), algo=algo)


def _config_for_template() -> dict[str, str]:
    """Config for settings form; secrets masked so user sees 'saved' without exposing full value."""
    cfg = load_config()
    out = {}
    for k, v in cfg.items():
        if not v:
            out[k] = ""
        elif "SECRET" in k or "KEY" in k:
            # Show masked placeholder so user knows value is saved (last 4 chars only)
            out[k] = "••••••••" + (v[-4:] if len(v) > 4 else "") if v else ""
        else:
            out[k] = v
    return out


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        if data:
            save_config({k: str(data.get(k)).strip() for k in load_config().keys() if data.get(k)})
            if request.is_json:
                return {"ok": True}
            return redirect(url_for("settings"))
    return render_template("settings.html", config=_config_for_template())


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """GET: return current config (values masked for secrets). POST: save and apply."""
    if request.method == "GET":
        cfg = load_config()
        # Mask secrets for display (show last 4 chars only)
        out = {}
        for k, v in cfg.items():
            if not v:
                out[k] = ""
            elif "SECRET" in k or "KEY" in k:
                out[k] = "****" + v[-4:] if len(v) > 4 else "****"
            else:
                out[k] = v
        return out
    data = request.get_json()
    if data is None:
        return {"ok": False, "error": "Invalid JSON or missing Content-Type: application/json"}, 400
    payload = {}
    for k, v in data.items():
        if k not in CONFIG_KEYS:
            continue
        v_str = str(v).strip() if v is not None else ""
        if v_str:
            payload[k] = v_str
    if not payload:
        return {"ok": False, "error": "No valid settings to save"}, 400
    try:
        save_config(payload)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


# REMOVED: api_trading_amount endpoint - TRADING_AMOUNT is no longer used
# Position sizing is now controlled by virtual_balance per session


@app.route("/api/start", methods=["POST"])
def start_trading():
    sm = get_session_manager()
    if sm.is_past_auto_close():
        return {"ok": False, "error": "Past auto-close time (2:30 PM IST)"}, 400
    sm.start_trading()
    return {"ok": True, "status": sm.get_status()}


@app.route("/api/stop", methods=["POST"])
def stop_trading():
    get_session_manager().stop_trading()
    return {"ok": True, "status": get_session_manager().get_status()}


@app.route("/api/kill", methods=["POST"])
def panic_kill():
    results = kill_switch()
    get_session_manager().stop_trading()
    return {"ok": True, "closed": len(results), "results": results}


def _get_cached_news(symbol: str) -> list[dict[str, Any]]:
    """Get cached news or fetch new if cache expired."""
    with _cache_lock:
        cache_key = f"{symbol}_news"
        if cache_key in _news_cache:
            headlines, cached_time = _news_cache[cache_key]
            if datetime.now() - cached_time < NEWS_CACHE_TTL:
                return headlines
        
        # Fetch new news
        sent = get_sentiment_for_symbol(symbol)
        headlines = sent.get("headlines", [])
        _news_cache[cache_key] = (headlines, datetime.now())
        return headlines


def _get_cached_prediction(symbol: str) -> dict[str, Any]:
    """Get cached prediction or calculate new if cache expired. Uses frozen prediction if before market open."""
    today = date.today().isoformat()
    
    with _cache_lock:
        # Check if cache is from today, clear if not
        cache_key = f"{symbol}_prediction"
        if cache_key in _prediction_cache:
            prediction, cached_time = _prediction_cache[cache_key]
            # Clear cache if it's from yesterday
            if cached_time.date().isoformat() != today:
                del _prediction_cache[cache_key]
        
        # Always get or create today's prediction first
        today_pred = _get_or_create_todays_prediction(symbol)
        
        # If prediction is frozen (created before market open), return it directly
        if today_pred.get("frozen"):
            return today_pred
        
        # If not frozen, use cache for performance during market hours
        if cache_key in _prediction_cache:
            prediction, cached_time = _prediction_cache[cache_key]
            # Short TTL during market (3 min); longer after close. Real money: avoid stale predictions.
            cache_ttl = PREDICTION_CACHE_TTL if _is_indian_market_open() else timedelta(hours=1)
            if datetime.now() - cached_time < cache_ttl:
                return prediction
        
        # Cache the prediction
        _prediction_cache[cache_key] = (today_pred, datetime.now())
        return today_pred


def _get_cached_us_bias():
    """Get cached US bias or compute new if cache expired. Returns 'market_open' status if US market still open."""
    global _us_bias_cache
    with _cache_lock:
        if _us_bias_cache:
            us_bias_data, cached_time = _us_bias_cache
            # Check if we have valid data or error state
            ttl = US_BIAS_CACHE_TTL if us_bias_data.get("sp500_pct_change") is not None else US_BIAS_ERROR_CACHE_TTL
            if datetime.now() - cached_time < ttl:
                return us_bias_data
        
        # Check if US market is closed before computing bias        
        if not _is_us_market_closed():
            # US market is still open - return "waiting" status
            us_bias_data = {
                "bias": None,
                "block_long": False,
                "prev_close": None,
                "pct_change": None,
                "sp500_prev_close": None,
                "sp500_pct_change": None,
                "sp500_date": None,
                "us_bias_obj": None,
                "market_status": "open",
                "message": "US market still open - data will update after close (4:00 PM ET / ~1:30 AM IST)"
            }
            # Cache for shorter time when market is open (check again in 30 minutes)
            _us_bias_cache = (us_bias_data, datetime.now() - timedelta(minutes=25))
            return us_bias_data
        
        # Compute new US bias (market is closed)
        us_bias = compute_us_bias()
        # fetch_sp500_previous_close is called inside compute_us_bias now, so we can just use the object properties
        
        us_bias_data = {
            "bias": us_bias.bias,
            "block_long": us_bias.block_long_first_hour,
            "prev_close": us_bias.prev_close,
            "pct_change": us_bias.pct_change,
            "sp500_prev_close": us_bias.prev_close,
            "sp500_pct_change": us_bias.pct_change,
            "sp500_date": us_bias.date_str,
            "us_bias_obj": us_bias,
            "market_status": "closed",
        }
        
        _us_bias_cache = (us_bias_data, datetime.now())
        return us_bias_data


def _clear_trading_caches_if_new_day() -> None:
    """Clear all trading-related caches at start of each calendar day (IST). Prevents stale data with real money."""
    global _news_cache, _prediction_cache, _us_bias_cache, _last_cache_clear_date_ist
    try:
        today_ist = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    except Exception:
        today_ist = date.today().isoformat()
    with _cache_lock:
        if _last_cache_clear_date_ist == today_ist:
            return
        _news_cache.clear()
        _prediction_cache.clear()
        _us_bias_cache = None
        _last_cache_clear_date_ist = today_ist
    # Clear caches defined later in this module (exist when this runs on first request of the day)
    try:
        globals()["_accuracy_cache"].clear()
    except (KeyError, AttributeError):
        pass
    try:
        globals()["_intraday_picks_cache"] = None
        globals()["_intraday_picks_cache_time"] = None
    except (KeyError, AttributeError):
        pass


@app.route("/api/live")
def api_live():
    """Current price(s), signal, positions, P&L, status. Poll every 5–10 s. Balance/positions/price are never cached."""
    apply_config_to_env()  # so NEWS_API_KEY and Zerodha token from Settings are used this request
    _clear_trading_caches_if_new_day()
    global _accuracy_cache, _prediction_cache
    today = date.today().isoformat()
    with _cache_lock:
        to_delete = [k for k, (_, ct) in _accuracy_cache.items() if ct.date().isoformat() != today]
        for key in to_delete:
            del _accuracy_cache[key]
    sm = get_session_manager()
    symbol = request.args.get("symbol", "RELIANCE")
    mode = request.args.get("mode", "backtest")

    # Use cached US bias for faster response
    us_market_status = _get_cached_us_bias()
    us_bias_obj = us_market_status["us_bias_obj"]
    
    # Fetch live US futures only if US market is open
    from engine.data_fetcher import fetch_us_futures, fetch_nifty50_live
    us_futures = {}
    if not _is_us_market_closed():
        us_futures = fetch_us_futures()
    # If market is closed, us_futures will be empty dict
    
    # Fetch live Nifty 50, Bank Nifty, India VIX in parallel when market open (faster homepage load)
    nifty_live = {}
    bank_nifty_live = {}
    india_vix_data = {}
    market_status = {}
    if _is_indian_market_open():
        try:
            with ThreadPoolExecutor(max_workers=3) as ex:
                f_nifty = ex.submit(fetch_nifty50_live)
                f_bank = ex.submit(fetch_bank_nifty_live)
                f_vix = ex.submit(fetch_india_vix)
                nifty_live = f_nifty.result(timeout=12)
                bank_nifty_live = f_bank.result(timeout=12)
                india_vix_data = f_vix.result(timeout=12)
        except Exception as e:
            logger.warning("api_live: parallel index fetch failed, using fallback: %s", str(e))
            nifty_live = fetch_nifty50_live()
            bank_nifty_live = fetch_bank_nifty_live()
            india_vix_data = fetch_india_vix()
        market_status = _determine_market_status(nifty_live)
    
    # Use cached news and prediction for faster response
    headlines = _get_cached_news(symbol)
    sent = get_sentiment_for_symbol(symbol)
    # Update sentiment but use cached headlines
    sent["headlines"] = headlines
    
    quote = fetch_nse_quote(symbol)
    if quote.get("last", 0) == 0 and mode == "live":
        quote = {"symbol": symbol, "last": 0, "open": 0, "high": 0, "low": 0}

    positions = []
    balance = 0.0
    if mode == "live":
        positions = get_positions()
        sm.set_positions(positions)
    else:
        positions = sm.get_positions()
    # Always fetch balance from Zerodha when connected; show — if call fails (e.g. not connected)
    balance_val, balance_ok = get_balance()
    balance = balance_val if balance_ok else None

    pnl = 0.0
    today_pnl = 0.0
    for p in positions:
        position_pnl = float(p.get("pnl", p.get("unrealized", 0)))
        pnl += position_pnl
        # TODO: Filter only today's trades for today_pnl when real trading starts
        # For now, today_pnl = pnl (will be updated with proper trade tracking)
        today_pnl += position_pnl

    minutes_left = sm.minutes_until_auto_close()
    if sm.is_past_auto_close():
        sm.auto_close()
        minutes_left = 0

    # Get market prediction (cached)
    prediction_data = _get_cached_prediction(symbol)
    accuracy_data = _update_prediction_accuracy(symbol)
    
    # Handle US market still open case
    us_bias_value = us_bias_obj.bias if us_bias_obj else None
    us_bias_block = us_bias_obj.block_long_first_hour if us_bias_obj else False
    
    # FORCE today's actual to be None if market is not closed yet
    # This prevents showing yesterday's data
    actual_direction = None
    price_change = 0
    accuracy = None
    
    if _can_show_actual_for_today():
        # Trading day and market closed - can show actual data (never on NSE holidays)
        actual_direction = accuracy_data.get("today_actual")
        price_change = accuracy_data.get("price_change_pct", 0)
        accuracy = accuracy_data.get("today_accuracy")
    # else: leave as None (market still open, or today is holiday/weekend)
    
    return {
        "status": sm.get_status(),
        "trading_on": sm.is_trading_on(),
        "mode": mode,
        "symbol": symbol,
        "price": quote.get("last", 0),
        "us_bias": us_bias_value,
        "us_bias_block_long": us_bias_block,
        "us_market_status": us_market_status.get("market_status", "unknown"),
        "us_market_prev_close": us_market_status.get("sp500_prev_close"),
        "us_market_pct_change": us_market_status.get("sp500_pct_change"),
        "us_market_date": us_market_status.get("sp500_date"),
        "us_futures_price": us_futures.get("price"),
        "us_futures_pct_change": us_futures.get("pct_change"),
        "us_futures_date": us_futures.get("date"),
        "nifty_live_price": nifty_live.get("price"),
        "nifty_live_pct_change": nifty_live.get("pct_change"),
        "nifty_live_date": nifty_live.get("date"),
        "bank_nifty_price": bank_nifty_live.get("price"),
        "bank_nifty_pct_change": bank_nifty_live.get("pct_change"),
        "bank_nifty_date": bank_nifty_live.get("date"),
        "india_vix": india_vix_data.get("vix_value"),
        "market_status_type": market_status.get("status_type"),
        "sentiment_score": sent.get("score", 0),
        "sentiment_blacklist": sent.get("blacklist_24h", False),
        "news_headlines": sent.get("headlines", []),
        "positions": positions,
        "balance": balance,
        "pnl": pnl,
        "today_pnl": today_pnl,
        "minutes_until_auto_close": minutes_left,
        "auto_close_time": os.getenv("AUTO_CLOSE_TIME", "14:30"),
        "market_prediction": prediction_data.get("prediction", "NEUTRAL"),
        "prediction_confidence": prediction_data.get("confidence", 50),
        "prediction_factors": prediction_data.get("factors", []),
        "prediction_accuracy": accuracy,
        "actual_direction": actual_direction,
        "overall_accuracy": accuracy_data.get("overall_accuracy", 0),
        "price_change_pct": price_change,
    }


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    data = request.get_json() or {}
    symbol = data.get("symbol", "RELIANCE")
    days = int(data.get("days", 60))
    results = run_backtest(symbol=symbol, days=days)
    return {"ok": True, "count": len(results), "results": results[:50]}


def _get_log_dir() -> Path:
    """Log folder for prediction history and other tracking data."""
    log_dir = Path(__file__).resolve().parent / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _get_predictions_file() -> Path:
    """Get path to predictions history file (inside log folder)."""
    return _get_log_dir() / "prediction_history.json"


def _get_nse_holidays() -> set[str]:
    """Load NSE (India) trading holidays as set of 'YYYY-MM-DD' strings. Cached for process."""
    path = Path(__file__).resolve().parent / "nse_holidays.json"
    if not path.exists():
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("holidays") or [])
    except Exception:
        return set()


def _is_nse_trading_day(d: date) -> bool:
    """True if the given date is an NSE trading day (weekday and not a holiday)."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return d.isoformat() not in _get_nse_holidays()


def _load_predictions() -> dict:
    """Load predictions history from log folder. Migrates from old location if needed."""
    path = _get_predictions_file()
    old_path = Path(__file__).resolve().parent / "predictions.json"
    if not path.exists() and old_path.exists():
        # One-time migration: move history from old file to log folder
        try:
            with open(old_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _save_predictions(data)
        except Exception:
            pass
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_predictions(data: dict) -> None:
    """Save predictions history and update cache."""
    global _predictions_cache, _predictions_cache_time
    path = _get_predictions_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    # Update cache immediately
    _predictions_cache = data
    _predictions_cache_time = datetime.now()


def _get_opening_range_file() -> Path:
    """Path for storing today's opening price per symbol (inside log folder)."""
    return _get_log_dir() / "opening_range.json"


def _load_opening_range() -> dict:
    today = date.today().isoformat()
    path = _get_opening_range_file()
    old_path = Path(__file__).resolve().parent / "opening_range.json"
    if not path.exists() and old_path.exists():
        try:
            with open(old_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _save_opening_range(data)
        except Exception:
            pass
    if not path.exists():
        return {"date": today, "symbols": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") != today:
            return {"date": today, "symbols": {}}
        return data
    except Exception:
        return {"date": today, "symbols": {}}


def _save_opening_range(data: dict) -> None:
    path = _get_opening_range_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _get_todays_open(symbol: str) -> float | None:
    """Return stored opening price for symbol today, or None."""
    data = _load_opening_range()
    val = data.get("symbols", {}).get(symbol.upper())
    return float(val) if val is not None else None


def _update_todays_open(symbol: str, open_price: float) -> None:
    """Store today's open for symbol (only if valid and we're early in session or not yet stored)."""
    if not open_price or open_price <= 0:
        return
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(ist)
    if now_ist.weekday() >= 5:
        return
    current_time = now_ist.time()
    market_open = time(9, 15)
    market_close = time(15, 30)
    if not (market_open <= current_time <= market_close):
        return
    data = _load_opening_range()
    sym_key = symbol.upper()
    if sym_key in data.get("symbols", {}):
        return
    data.setdefault("symbols", {})[sym_key] = open_price
    _save_opening_range(data)


def _get_market_prediction(symbol: str = "RELIANCE") -> dict[str, Any]:
    """Predict today's market direction (bullish/bearish). Uses Zerodha when connected for better data."""
    try:
        us_bias = compute_us_bias()
        
        # Get sentiment (this is fast, no need to cache separately)
        sent = get_sentiment_for_symbol(symbol)
        
        # Technicals: prefer Zerodha historical (exchange data) when connected; need 60d for RSI/EMA
        df = get_historical_for_prediction(symbol, days=60)
        tech = compute_technicals(df) if not df.empty else {}
        
        # Calculate prediction score
        score = 0.0
        factors = []
        
        # US Bias contribution (40% weight)
        if us_bias.bias == 1:
            score += 0.4
            factors.append("US Market: Bullish (+1%)")
        elif us_bias.bias == -1:
            score -= 0.4
            factors.append("US Market: Bearish (<-0.5%)")
        else:
            factors.append("US Market: Neutral")
        
        # Sentiment contribution (30% weight)
        sentiment_score = sent.get("score", 0)
        if sentiment_score > 0.3:
            score += 0.3
            factors.append(f"Sentiment: Positive ({sentiment_score:.2f})")
        elif sentiment_score < -0.3:
            score -= 0.3
            factors.append(f"Sentiment: Negative ({sentiment_score:.2f})")
        else:
            factors.append(f"Sentiment: Neutral ({sentiment_score:.2f})")
        
        # Technical indicators (30% weight) – from Zerodha or yfinance
        if tech:
            rsi = tech.get("rsi")
            if rsi:
                if rsi > 60:
                    score += 0.15
                    factors.append(f"RSI: Bullish ({rsi:.1f})")
                elif rsi < 40:
                    score -= 0.15
                    factors.append(f"RSI: Bearish ({rsi:.1f})")
                else:
                    factors.append(f"RSI: Neutral ({rsi:.1f})")
            
            if tech.get("ema9_cross_up"):
                score += 0.15
                factors.append("EMA: Bullish Cross")
            elif tech.get("ema9_cross_down"):
                score -= 0.15
                factors.append("EMA: Bearish Cross")
        
        # Index alignment (Nifty & Bank Nifty) – ~5% when both agree
        try:
            nifty = fetch_nifty50_live()
            bank_nifty = fetch_bank_nifty_live()
            nifty_pct = nifty.get("pct_change")
            bank_pct = bank_nifty.get("pct_change")
            if nifty_pct is not None and bank_pct is not None:
                if nifty_pct > 0.3 and bank_pct > 0.3:
                    score += 0.05
                    factors.append("Indices: Bullish (Nifty & Bank Nifty up)")
                elif nifty_pct < -0.3 and bank_pct < -0.3:
                    score -= 0.05
                    factors.append("Indices: Bearish (Nifty & Bank Nifty down)")
        except Exception:
            pass
        
        # India VIX: high VIX -> add cautious factor (confidence reduced later)
        vix_high = False
        try:
            vix_data = fetch_india_vix()
            vix_val = vix_data.get("vix_value")
            if vix_val is not None and float(vix_val) > 18:
                vix_high = True
                factors.append(f"High VIX: cautious ({vix_val:.1f})")
        except Exception:
            pass
        
        # Intraday: opening range (price vs open) and live quote for depth
        if _is_indian_market_open():
            try:
                quote = fetch_nse_quote(symbol)
                open_p = quote.get("open") or 0
                last_p = quote.get("last") or 0
                if open_p > 0:
                    _update_todays_open(symbol, open_p)
                stored_open = _get_todays_open(symbol) or open_p
                if stored_open and stored_open > 0 and last_p > 0:
                    pct_vs_open = ((last_p - stored_open) / stored_open) * 100
                    if pct_vs_open > 0.2:
                        score += 0.03
                        factors.append(f"Price vs open: above (+{pct_vs_open:.2f}%)")
                    elif pct_vs_open < -0.2:
                        score -= 0.03
                        factors.append(f"Price vs open: below ({pct_vs_open:.2f}%)")
                buy_q = quote.get("buy_quantity") or 0
                sell_q = quote.get("sell_quantity") or 0
                if buy_q and sell_q:
                    total = buy_q + sell_q
                    imbalance = (buy_q - sell_q) / total if total else 0
                    if imbalance > 0.1:
                        score += 0.02
                        factors.append("Depth: bid bias")
                    elif imbalance < -0.1:
                        score -= 0.02
                        factors.append("Depth: ask bias")
            except Exception:
                pass
        
        # Intraday 15m trend (Zerodha) – only when market is open
        if _is_indian_market_open():
            try:
                df_15 = fetch_nse_ohlc(symbol, interval="15m", period="1d")
                if df_15 is not None and not df_15.empty and len(df_15) >= 1:
                    row0 = df_15.iloc[0]
                    open_15 = float(row0.get("Open", 0))
                    close_15 = float(row0.get("Close", 0))
                    if open_15 and close_15:
                        chg = ((close_15 - open_15) / open_15) * 100
                        if chg > 0.15:
                            score += 0.02
                            factors.append("Intraday 15m: bullish")
                        elif chg < -0.15:
                            score -= 0.02
                            factors.append("Intraday 15m: bearish")
            except Exception:
                pass
        
        # Determine prediction
        if score > 0.2:
            prediction = "BULLISH"
            confidence = min(100, int((score + 1) * 50))
        elif score < -0.2:
            prediction = "BEARISH"
            confidence = min(100, int((abs(score) + 1) * 50))
        else:
            prediction = "NEUTRAL"
            confidence = 50
        
        if vix_high:
            confidence = min(confidence, 72)
        # Extra fields for algo suggestion engine
        rsi_val = tech.get("rsi") if tech else None
        return {
            "prediction": prediction,
            "confidence": confidence,
            "score": round(score, 2),
            "factors": factors,
            "timestamp": datetime.now().isoformat(),
            "rsi": rsi_val,
            "sentiment_score": sentiment_score,
            "vix_high": vix_high,
        }
    except Exception as e:
        return {
            "prediction": "NEUTRAL",
            "confidence": 50,
            "score": 0.0,
            "factors": [f"Error: {str(e)}"],
            "timestamp": datetime.now().isoformat(),
            "rsi": None,
            "sentiment_score": 0,
            "vix_high": False,
        }


def _is_us_market_closed() -> bool:
    """Check if US market has closed for the day (4:00 PM ET = ~1:30-2:30 AM IST next day)."""
    try:
        et = ZoneInfo('America/New_York')
        now_et = datetime.now(et)
        current_time_et = now_et.time()
        
        # US market closes at 4:00 PM ET
        market_close_et = time(16, 0)
        
        # Market is closed if it's after 4:00 PM ET or before 9:30 AM ET (next day)
        market_open_et = time(9, 30)
        
        # If weekend, market is closed
        if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return True
            
        # Market is closed from 4:00 PM to 9:30 AM next day
        if current_time_et >= market_close_et or current_time_et < market_open_et:
            return True
        
        return False
    except Exception:
        # If we can't determine, assume closed (safer for data integrity)
        return True


def _is_indian_market_open() -> bool:
    """Check if Indian stock market (NSE) is currently open (trading day + time)."""
    ist = ZoneInfo('Asia/Kolkata')
    now_ist = datetime.now(ist)
    if not _is_nse_trading_day(now_ist.date()):
        return False
    current_time = now_ist.time()
    market_open = time(9, 15)  # 9:15 AM IST
    market_close = time(15, 30)  # 3:30 PM IST
    return market_open <= current_time <= market_close


def _is_before_market_open() -> bool:
    """Check if current time is before Indian market opens (before 9:15 AM IST)."""
    ist = ZoneInfo('Asia/Kolkata')
    now_ist = datetime.now(ist)
    current_time = now_ist.time()
    market_open = time(9, 15)  # 9:15 AM IST
    return current_time < market_open


def _is_after_market_close() -> bool:
    """Check if current time is after Indian market closes (after 3:30 PM IST)."""
    ist = ZoneInfo('Asia/Kolkata')
    now_ist = datetime.now(ist)
    current_time = now_ist.time()
    market_close = time(15, 30)  # 3:30 PM IST
    return current_time > market_close


def _can_show_actual_for_today() -> bool:
    """True only if today is an NSE trading day AND market has closed (so we can compute/freeze actual)."""
    today = date.today()
    return _is_nse_trading_day(today) and _is_after_market_close()


def _determine_market_status(nifty_data: dict) -> dict:
    """Determine if market is trending, sideways, or volatile. Prefers Zerodha Nifty 50 history."""
    try:
        # Prefer Zerodha 5d Nifty 50 OHLC when connected
        df = fetch_nse_ohlc("NIFTY 50", interval="1d", period="5d")
        if df is not None and not df.empty and len(df) >= 3:
            closes = df["Close"].values
            highs = df["High"].values
            lows = df["Low"].values
            price_range = (max(closes) - min(closes)) / min(closes) * 100
            avg_daily_range = sum((highs[i] - lows[i]) / lows[i] for i in range(len(lows))) / len(lows) * 100
            if avg_daily_range > 3:
                return {"status_type": "volatile"}
            if price_range < 2:
                return {"status_type": "sideways"}
            return {"status_type": "trending"}
    except Exception:
        pass
    try:
        import yfinance as yf
        data = yf.Ticker("^NSEI").history(period="5d", interval="1d")
        if len(data) >= 3:
            closes = data["Close"].values
            highs = data["High"].values
            lows = data["Low"].values
            price_range = (max(closes) - min(closes)) / min(closes) * 100
            avg_daily_range = sum((highs[i] - lows[i]) / lows[i] for i in range(len(lows))) / len(lows) * 100
            if avg_daily_range > 3:
                return {"status_type": "volatile"}
            if price_range < 2:
                return {"status_type": "sideways"}
            return {"status_type": "trending"}
    except Exception:
        pass
    return {"status_type": "trending"}


def _get_today_ohlc_from_yfinance(symbol: str) -> dict[str, float]:
    """Get today's OHLC data from yfinance as fallback."""
    try:
        import yfinance as yf
        nse_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
        ticker = yf.Ticker(nse_symbol)
        # Get today's data
        hist = ticker.history(period="2d", interval="1d")
        if hist.empty or len(hist) < 1:
            return {"open": 0.0, "close": 0.0, "high": 0.0, "low": 0.0}
        
        # Get the most recent day (today or last trading day)
        latest = hist.iloc[-1]
        return {
            "open": float(latest.get("Open", 0)),
            "close": float(latest.get("Close", 0)),
            "high": float(latest.get("High", 0)),
            "low": float(latest.get("Low", 0)),
        }
    except Exception:
        return {"open": 0.0, "close": 0.0, "high": 0.0, "low": 0.0}


def _get_or_create_todays_prediction(symbol: str = "RELIANCE") -> dict[str, Any]:
    """Get today's prediction, creating and freezing it if before market open. Only creates after US market closes."""
    predictions = _load_predictions()
    today = date.today().isoformat()
    
    # Check if US market is closed first
    if not _is_us_market_closed():
        # US market still open - cannot create prediction yet
        # Even if prediction exists in file, don't use it until US closes
        return {
            "prediction": "WAITING",
            "confidence": None,  # Blank confidence when waiting
            "score": 0,
            "factors": ["⏳ Waiting for US market to close (4:00 PM ET / ~1:30 AM IST)"],
            "timestamp": datetime.now().isoformat(),
            "usa_bias": "N/A",
            "usa_bias_value": 0,
            "frozen": False,
            "waiting_for_us_close": True,
        }
    
    # US market is closed - check if prediction already exists for today
    if today in predictions and predictions[today].get("prediction") and predictions[today].get("prediction") != "WAITING":
        is_frozen = predictions[today].get("frozen_at") is not None or _can_show_actual_for_today()
        return {
            "prediction": predictions[today]["prediction"],
            "confidence": predictions[today].get("confidence", 50),
            "score": predictions[today].get("score", 0),
            "factors": predictions[today].get("factors", []),
            "timestamp": predictions[today].get("timestamp", datetime.now().isoformat()),
            "usa_bias": predictions[today].get("usa_bias", "N/A"),
            "usa_bias_value": predictions[today].get("usa_bias_value", 0),
            "frozen": is_frozen,
        }
    
    # Create prediction for today
    pred = _get_market_prediction(symbol)
    
    # Get USA bias for today
    us_bias = compute_us_bias()
    usa_bias_label = f"{us_bias.bias:+d}" if us_bias.bias else "0"
    if us_bias.pct_change:
        usa_bias_label += f" ({us_bias.pct_change:+.2f}%)"
    
    # If before market open, freeze it
    is_before_open = _is_before_market_open()
    prediction_data = {
        "symbol": symbol,
        "prediction": pred["prediction"],
        "confidence": pred["confidence"],
        "score": pred["score"],
        "factors": pred["factors"],
        "timestamp": pred["timestamp"],
        "usa_bias": usa_bias_label,
        "usa_bias_value": us_bias.bias,
        "usa_bias_pct": us_bias.pct_change,
        "actual": None,
        "accuracy": None,
    }
    
    if is_before_open:
        prediction_data["frozen_at"] = datetime.now().isoformat()
    
    predictions[today] = prediction_data
    _save_predictions(predictions)
    
    return {**pred, "frozen": is_before_open}


# Cache for prediction accuracy
_accuracy_cache: dict[str, tuple[dict, datetime]] = {}
ACCURACY_CACHE_TTL = timedelta(minutes=1)  # Cache accuracy for 1 minute


def _update_prediction_accuracy(symbol: str = "RELIANCE") -> dict[str, Any]:
    """Update prediction accuracy by comparing today's prediction with actual market movement."""
    try:
        # Check cache first - but invalidate if it's a new day
        cache_key = f"{symbol}_accuracy"
        today = date.today().isoformat()
        
        with _cache_lock:
            if cache_key in _accuracy_cache:
                accuracy_data, cached_time = _accuracy_cache[cache_key]
                # Invalidate cache if it's from a different day OR if TTL expired
                cached_date = cached_time.date().isoformat()
                if cached_date == today and datetime.now() - cached_time < ACCURACY_CACHE_TTL:
                    return accuracy_data
                # Clear old cache if it's from yesterday
                else:
                    del _accuracy_cache[cache_key]
        
        predictions = _load_predictions()
        today = date.today().isoformat()
        today_date = date.today()
        
        # On NSE holiday/weekend: never compute or show actual for today
        if not _is_nse_trading_day(today_date):
            base = {
                "overall_accuracy": _calculate_overall_accuracy(predictions),
                "correct_predictions": sum(1 for p in predictions.values() if p.get("accuracy") == "CORRECT"),
                "total_predictions": sum(1 for p in predictions.values() if p.get("accuracy") is not None),
            }
            if today in predictions:
                return {
                    "today_prediction": predictions[today].get("prediction", "NEUTRAL"),
                    "today_actual": None,
                    "today_accuracy": None,
                    "price_change_pct": 0,
                    **base,
                }
            return {"today_prediction": "WAITING", "today_actual": None, "today_accuracy": None, "price_change_pct": 0, **base}
        
        # If actual is already frozen (calculated after market close), return it
        if today in predictions and predictions[today].get("actual") is not None:
            if _can_show_actual_for_today() or predictions[today].get("actual_frozen"):
                accuracy_data = {
                    "today_prediction": predictions[today].get("prediction", "NEUTRAL"),
                    "today_actual": predictions[today]["actual"],
                    "today_accuracy": predictions[today].get("accuracy"),
                    "price_change_pct": predictions[today].get("actual_change_pct", 0),
                    "overall_accuracy": _calculate_overall_accuracy(predictions),
                    "correct_predictions": sum(1 for p in predictions.values() if p.get("accuracy") == "CORRECT"),
                    "total_predictions": sum(1 for p in predictions.values() if p.get("accuracy") is not None),
                }
                with _cache_lock:
                    _accuracy_cache[cache_key] = (accuracy_data, datetime.now())
                return accuracy_data
        
        # Only calculate actual if today was a trading day and market is closed
        if not _can_show_actual_for_today():
            # Market still open - return existing data or placeholder
            if today in predictions:
                return {
                    "today_prediction": predictions[today].get("prediction", "NEUTRAL"),
                    "today_actual": None,  # Always None until market closes today
                    "today_accuracy": None,
                    "price_change_pct": 0,  # Always 0 until market closes today
                    "overall_accuracy": _calculate_overall_accuracy(predictions),
                }
            # No prediction for today yet - return empty data
            return {
                "today_prediction": "WAITING",
                "today_actual": None,
                "today_accuracy": None,
                "price_change_pct": 0,
                "overall_accuracy": _calculate_overall_accuracy(predictions),
            }
        
        # Market is closed - calculate and freeze actual result
        quote = fetch_nse_quote(symbol)
        current_price = quote.get("last", 0)
        open_price = quote.get("open", 0)
        
        # Fallback to yfinance if Zerodha not available
        if not open_price or not current_price or open_price == 0 or current_price == 0:
            yf_data = _get_today_ohlc_from_yfinance(symbol)
            open_price = yf_data.get("open", 0)
            current_price = yf_data.get("close", 0)
        
        if not open_price or not current_price or open_price == 0 or current_price == 0:
            # Still no data - return existing if available
            if today in predictions:
                return {
                    "today_prediction": predictions[today].get("prediction", "NEUTRAL"),
                    "today_actual": predictions[today].get("actual"),
                    "today_accuracy": predictions[today].get("accuracy"),
                    "price_change_pct": predictions[today].get("actual_change_pct", 0),
                    "overall_accuracy": _calculate_overall_accuracy(predictions),
                }
            return {"accuracy": None, "message": "Price data not available"}
        
        # Calculate actual movement
        price_change_pct = ((current_price - open_price) / open_price) * 100 if open_price else 0
        actual_direction = "BULLISH" if price_change_pct > 0.5 else ("BEARISH" if price_change_pct < -0.5 else "NEUTRAL")
        
        # Ensure prediction exists for today
        if today not in predictions:
            pred = _get_market_prediction(symbol)
            predictions[today] = {
                "symbol": symbol,
                "prediction": pred["prediction"],
                "confidence": pred["confidence"],
                "score": pred["score"],
                "factors": pred["factors"],
                "timestamp": pred["timestamp"],
                "actual": None,
                "accuracy": None,
            }
        
        # Freeze actual result (only update if not already frozen)
        if not predictions[today].get("actual_frozen"):
            predictions[today]["actual"] = actual_direction
            predictions[today]["actual_change_pct"] = round(price_change_pct, 2)
            predictions[today]["actual_frozen"] = True
            predictions[today]["actual_frozen_at"] = datetime.now().isoformat()
            
            # Calculate accuracy and analyze
            predicted = predictions[today]["prediction"]
            if predicted == actual_direction:
                predictions[today]["accuracy"] = "CORRECT"
            elif predicted == "NEUTRAL" or actual_direction == "NEUTRAL":
                predictions[today]["accuracy"] = "PARTIAL"
            else:
                predictions[today]["accuracy"] = "INCORRECT"
            
            # Always analyze - for both correct and incorrect predictions
            predictions[today]["analysis"] = _analyze_prediction_failure(predictions[today], actual_direction, price_change_pct)
            
            _save_predictions(predictions)
        
        accuracy_data = {
            "today_prediction": predictions[today]["prediction"],
            "today_actual": predictions[today]["actual"],
            "today_accuracy": predictions[today]["accuracy"],
            "price_change_pct": predictions[today].get("actual_change_pct", 0),
            "overall_accuracy": _calculate_overall_accuracy(predictions),
            "correct_predictions": sum(1 for p in predictions.values() if p.get("accuracy") == "CORRECT"),
            "total_predictions": sum(1 for p in predictions.values() if p.get("accuracy") is not None),
        }
        
        # Cache the result
        with _cache_lock:
            _accuracy_cache[cache_key] = (accuracy_data, datetime.now())
        
        return accuracy_data
    except Exception as e:
        return {"accuracy": None, "error": str(e)}


def _analyze_prediction_failure(prediction_data: dict, actual_direction: str, price_change_pct: float) -> str:
    """Analyze prediction result and return supporting/contradicting factors."""
    predicted = prediction_data.get("prediction", "NEUTRAL")
    factors = prediction_data.get("factors", [])
    usa_bias_value = prediction_data.get("usa_bias_value", 0)
    
    # If prediction was CORRECT, analyze what supported it
    if predicted == actual_direction:
        supporting_factors = []
        
        # Check USA Bias contribution
        if usa_bias_value > 0 and actual_direction == "BULLISH":
            supporting_factors.append("✓ USA bullish bias correct")
        elif usa_bias_value < 0 and actual_direction == "BEARISH":
            supporting_factors.append("✓ USA bearish bias confirmed")
        elif usa_bias_value == 0 and actual_direction == "NEUTRAL":
            supporting_factors.append("✓ USA neutral aligned")
        
        # Check Sentiment alignment
        sentiment_factor = next((f for f in factors if "Sentiment" in f), None)
        if sentiment_factor:
            if "Positive" in sentiment_factor and actual_direction == "BULLISH":
                supporting_factors.append("✓ Positive sentiment validated")
            elif "Negative" in sentiment_factor and actual_direction == "BEARISH":
                supporting_factors.append("✓ Negative sentiment confirmed")
        
        # Check Technical Indicators
        rsi_factor = next((f for f in factors if "RSI" in f), None)
        ema_factor = next((f for f in factors if "EMA" in f), None)
        
        if rsi_factor:
            if "Bullish" in rsi_factor and actual_direction == "BULLISH":
                supporting_factors.append("✓ RSI bullish signal accurate")
            elif "Bearish" in rsi_factor and actual_direction == "BEARISH":
                supporting_factors.append("✓ RSI bearish signal accurate")
        
        if ema_factor:
            if "Bullish" in ema_factor and actual_direction == "BULLISH":
                supporting_factors.append("✓ EMA crossover confirmed")
            elif "Bearish" in ema_factor and actual_direction == "BEARISH":
                supporting_factors.append("✓ EMA bearish trend confirmed")
        
        # Add price movement context
        if abs(price_change_pct) > 1.5:
            supporting_factors.append(f"✓ Strong move ({price_change_pct:+.1f}%)")
        elif abs(price_change_pct) < 0.5:
            supporting_factors.append(f"✓ Low volatility ({price_change_pct:+.1f}%)")
        
        return "; ".join(supporting_factors[:3]) if supporting_factors else "✓ All indicators aligned correctly"
    
    # If prediction was INCORRECT, analyze what went wrong
    reasons = []
    
    # Check USA Bias influence
    usa_factor = next((f for f in factors if "US Market" in f), None)
    if usa_bias_value > 0 and actual_direction == "BEARISH":
        reasons.append("✗ USA bullish bias misleading")
    elif usa_bias_value < 0 and actual_direction == "BULLISH":
        reasons.append("✗ USA bearish bias failed")
    
    # Check Sentiment
    sentiment_factor = next((f for f in factors if "Sentiment" in f), None)
    if sentiment_factor:
        if "Positive" in sentiment_factor and actual_direction == "BEARISH":
            reasons.append("✗ Positive sentiment misleading")
        elif "Negative" in sentiment_factor and actual_direction == "BULLISH":
            reasons.append("✗ Negative sentiment wrong")
    
    # Check Technical Indicators
    rsi_factor = next((f for f in factors if "RSI" in f), None)
    if rsi_factor:
        if "Bullish" in rsi_factor and actual_direction == "BEARISH":
            reasons.append("✗ RSI overbought signal")
        elif "Bearish" in rsi_factor and actual_direction == "BULLISH":
            reasons.append("✗ RSI oversold signal")
    
    # Check if all factors were aligned but still wrong
    bullish_factors = sum(1 for f in factors if "Bullish" in f or "Positive" in f)
    bearish_factors = sum(1 for f in factors if "Bearish" in f or "Negative" in f)
    
    if predicted == "BULLISH" and bullish_factors >= 2 and actual_direction == "BEARISH":
        reasons.append("✗ Unexpected reversal despite positive signals")
    elif predicted == "BEARISH" and bearish_factors >= 2 and actual_direction == "BULLISH":
        reasons.append("✗ Market resilience overcame indicators")
    
    # Check magnitude of price change
    if abs(price_change_pct) < 0.5:
        reasons.append("✗ Low volatility - sideways market")
    elif abs(price_change_pct) > 2.0:
        reasons.append(f"✗ High volatility ({abs(price_change_pct):.1f}%) - external factors")
    
    # Return combined reasons or generic message
    if reasons:
        return "; ".join(reasons[:2])  # Limit to 2 most important reasons
    else:
        return "✗ Multiple factors misaligned"


def _calculate_overall_accuracy(predictions: dict) -> float:
    """Calculate overall accuracy percentage from predictions."""
    correct = sum(1 for p in predictions.values() if p.get("accuracy") == "CORRECT")
    total = sum(1 for p in predictions.values() if p.get("accuracy") is not None)
    return round((correct / total * 100) if total > 0 else 0, 1)


@app.route("/api/market-prediction")
def api_market_prediction():
    """Get today's market prediction (bullish/bearish)."""
    symbol = request.args.get("symbol", "RELIANCE")
    prediction = _get_market_prediction(symbol)
    accuracy = _update_prediction_accuracy(symbol)
    return {
        "ok": True,
        "symbol": symbol,
        **prediction,
        **accuracy,
    }


def _backfill_actual_for_date(date_str: str, symbol: str, pred_data: dict, predictions: dict) -> dict:
    """For a past trading day with no stored actual, fetch OHLC and compute actual/accuracy/analysis; persist and return updated pred_data."""
    if pred_data.get("actual") is not None or pred_data.get("actual_frozen"):
        return pred_data
    try:
        d = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return pred_data
    if d >= date.today():
        return pred_data
    ohlc = get_ohlc_for_date(symbol, d)
    if not ohlc or "pct_change" not in ohlc:
        return pred_data
    price_change_pct = ohlc["pct_change"]
    actual_direction = "BULLISH" if price_change_pct > 0.5 else ("BEARISH" if price_change_pct < -0.5 else "NEUTRAL")
    predicted = pred_data.get("prediction", "NEUTRAL")
    if predicted == actual_direction:
        accuracy = "CORRECT"
    elif predicted == "NEUTRAL" or actual_direction == "NEUTRAL":
        accuracy = "PARTIAL"
    else:
        accuracy = "INCORRECT"
    analysis = _analyze_prediction_failure(pred_data, actual_direction, price_change_pct)
    pred_data = dict(pred_data)
    pred_data["actual"] = actual_direction
    pred_data["actual_change_pct"] = price_change_pct
    pred_data["actual_frozen"] = True
    pred_data["accuracy"] = accuracy
    pred_data["analysis"] = analysis
    predictions[date_str] = pred_data
    _save_predictions(predictions)
    return pred_data


@app.route("/api/prediction-history")
def api_prediction_history():
    """Get historical predictions with dates."""
    symbol = request.args.get("symbol", "RELIANCE")
    limit = int(request.args.get("limit", 30))  # Default last 30 days
    
    try:
        predictions = _load_predictions()
        
        # Filter by symbol and sort by date (newest first)
        history = []
        today = date.today().isoformat()
        
        for date_str, pred_data in predictions.items():
            if pred_data.get("symbol", "RELIANCE").upper() != symbol.upper():
                continue
            try:
                d = date.fromisoformat(date_str)
                is_trading = _is_nse_trading_day(d)
            except (ValueError, TypeError):
                is_trading = True
            if is_trading:
                # Backfill actual for past trading days that have no stored actual
                if pred_data.get("actual") is None and date_str < today:
                    pred_data = _backfill_actual_for_date(date_str, symbol, pred_data, predictions)
                history.append({
                    "date": date_str,
                    "prediction": pred_data.get("prediction", "NEUTRAL"),
                    "confidence": pred_data.get("confidence", 50),
                    "usa_bias": pred_data.get("usa_bias", "N/A"),
                    "usa_bias_value": pred_data.get("usa_bias_value", 0),
                    "actual": pred_data.get("actual"),
                    "accuracy": pred_data.get("accuracy"),
                    "price_change_pct": pred_data.get("actual_change_pct", 0),
                    "analysis": pred_data.get("analysis", "N/A"),
                    "factors": pred_data.get("factors", []),
                    "market_closed": False,
                })
            else:
                # NSE holiday or weekend: do not show stored actual/accuracy; show Market closed
                history.append({
                    "date": date_str,
                    "prediction": pred_data.get("prediction", "NEUTRAL"),
                    "confidence": pred_data.get("confidence", 50),
                    "usa_bias": pred_data.get("usa_bias", "N/A"),
                    "usa_bias_value": pred_data.get("usa_bias_value", 0),
                    "actual": None,
                    "accuracy": None,
                    "price_change_pct": 0,
                    "analysis": "Market closed",
                    "factors": pred_data.get("factors", []),
                    "market_closed": True,
                })
        
        # Add today's incomplete record if not already present
        if not any(h["date"] == today for h in history):
            today_pred = _get_or_create_todays_prediction(symbol)
            today_is_trading = _is_nse_trading_day(date.today())
            history.append({
                "date": today,
                "prediction": today_pred.get("prediction", "—"),
                "confidence": today_pred.get("confidence", 0),
                "usa_bias": today_pred.get("usa_bias", "—"),
                "usa_bias_value": today_pred.get("usa_bias_value", 0),
                "actual": None,
                "accuracy": None,
                "price_change_pct": 0,
                "analysis": "Market closed" if not today_is_trading else "⏳ In progress...",
                "factors": today_pred.get("factors", []),
                "market_closed": not today_is_trading,
            })
        
        # Sort by date descending (newest first)
        history.sort(key=lambda x: x["date"], reverse=True)
        
        # Limit results
        history = history[:limit]
        
        return {
            "ok": True,
            "symbol": symbol,
            "count": len(history),
            "history": history,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "history": [],
        }


@app.route("/api/trade-suggestions")
def api_trade_suggestions():
    """Get trade suggestions (min/max) for a symbol based on analysis."""
    symbol = request.args.get("symbol", "RELIANCE")
    
    try:
        # Try to get historical data for analysis
        df = fetch_nse_ohlc(symbol, interval="1d", period="30d")
        if df.empty:
            # Fallback to yfinance
            df = get_historical_for_backtest(symbol, days=30)
        
        if df.empty:
            return {
                "ok": False,
                "error": "Could not fetch data for analysis",
                "min_trades": 1,
                "suggested_max": 3,
            }
        
        suggestion = suggest_min_trades(df, symbol)
        
        return {
            "ok": True,
            "symbol": symbol,
            "min_trades": suggestion["min_trades"],
            "suggested_max": suggestion["suggested_max"],
            "reasoning": suggestion["reasoning"],
            "factors": suggestion["factors"],
            "note": "Trade frequency now controlled by dynamic hourly system (see Settings → Trade Frequency)",
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "min_trades": 1,
            "suggested_max": 3,
        }


@app.route("/api/analytics")
def api_analytics():
    """Get profit analytics by weekday and time of day."""
    time_range = request.args.get("range", "week")
    
    try:
        # TODO: Replace this with real trade data from database/logs
        # For now, use dummy data to demonstrate the analytics
        use_dummy = True  # Set to False once real trade data is available
        
        if use_dummy:
            # Generate realistic dummy data
            weekday_profits = {
                "Monday": 2500.50,
                "Tuesday": -800.25,
                "Wednesday": 3200.75,
                "Thursday": 1500.00,
                "Friday": 4100.25,
                "Saturday": 0,
                "Sunday": 0
            }
            time_of_day_profits = {
                "9-10 AM": 1800.50,
                "10-11 AM": 2200.75,
                "11-12 PM": -500.25,
                "12-1 PM": 1500.00,
                "1-2 PM": 3100.50,
                "2-3 PM": 2400.75,
                "3-4 PM": 1000.00
            }
            
            total_trades = 45
            best_day = {"day": "Friday", "profit": 4100.25}
            worst_day = {"day": "Tuesday", "profit": -800.25}
            best_time = {"time": "1-2 PM", "profit": 3100.50}
            
            return {
                "ok": True,
                "by_weekday": weekday_profits,
                "by_time_of_day": time_of_day_profits,
                "best_day": f"{best_day['day']} (₹{best_day['profit']:.2f})",
                "worst_day": f"{worst_day['day']} (₹{worst_day['profit']:.2f})",
                "best_time": f"{best_time['time']} (₹{best_time['profit']:.2f})",
                "total_trades": total_trades,
            }
        
        predictions_file = _predictions_file()
        
        if predictions_file.exists():
            with open(predictions_file, "r") as f:
                predictions = json.load(f)
        else:
            predictions = []
        
        # Filter by time range
        now = datetime.now()
        if time_range == "week":
            start_date = now - timedelta(days=7)
        elif time_range == "month":
            start_date = now - timedelta(days=30)
        else:  # all
            start_date = datetime(2000, 1, 1)
        
        # Initialize data structures
        weekday_profits = {
            "Monday": 0, "Tuesday": 0, "Wednesday": 0, 
            "Thursday": 0, "Friday": 0, "Saturday": 0, "Sunday": 0
        }
        time_of_day_profits = {
            "9-10 AM": 0, "10-11 AM": 0, "11-12 PM": 0, "12-1 PM": 0,
            "1-2 PM": 0, "2-3 PM": 0, "3-4 PM": 0
        }
        
        total_trades = 0
        best_day = {"day": "N/A", "profit": 0}
        worst_day = {"day": "N/A", "profit": 0}
        best_time = {"time": "N/A", "profit": 0}
        
        # Process predictions data (mock profit calculation)
        for pred in predictions:
            try:
                pred_date = datetime.strptime(pred.get("date", ""), "%Y-%m-%d")
                if pred_date < start_date:
                    continue
                
                # Mock profit calculation based on prediction accuracy
                # In reality, this should come from actual trade data
                price_change = pred.get("price_change_pct", 0)
                if price_change is not None:
                    # Simple mock: if prediction was correct, profit = abs(change) * 1000
                    # if incorrect, profit = -abs(change) * 500
                    predicted = pred.get("predicted_direction", "")
                    actual = pred.get("actual_direction", "")
                    
                    if predicted and actual:
                        if predicted == actual:
                            profit = abs(price_change) * 1000
                        else:
                            profit = -abs(price_change) * 500
                        
                        # Aggregate by weekday
                        weekday = pred_date.strftime("%A")
                        weekday_profits[weekday] += profit
                        
                        # Aggregate by time of day (distribute randomly for now)
                        # In reality, use actual trade timestamps
                        import random
                        random.seed(pred_date.toordinal())
                        hour = random.randint(9, 15)
                        if hour == 9:
                            time_slot = "9-10 AM"
                        elif hour == 10:
                            time_slot = "10-11 AM"
                        elif hour == 11:
                            time_slot = "11-12 PM"
                        elif hour == 12:
                            time_slot = "12-1 PM"
                        elif hour == 13:
                            time_slot = "1-2 PM"
                        elif hour == 14:
                            time_slot = "2-3 PM"
                        else:
                            time_slot = "3-4 PM"
                        
                        time_of_day_profits[time_slot] += profit
                        total_trades += 1
            except (ValueError, KeyError):
                continue
        
        # Find best/worst day and time
        for day, profit in weekday_profits.items():
            if profit > best_day["profit"]:
                best_day = {"day": day, "profit": profit}
            if profit < worst_day["profit"]:
                worst_day = {"day": day, "profit": profit}
        
        for time, profit in time_of_day_profits.items():
            if profit > best_time["profit"]:
                best_time = {"time": time, "profit": profit}
        
        return {
            "ok": True,
            "by_weekday": weekday_profits,
            "by_time_of_day": time_of_day_profits,
            "best_day": f"{best_day['day']} (₹{best_day['profit']:.2f})" if best_day['day'] != "N/A" else "N/A",
            "worst_day": f"{worst_day['day']} (₹{worst_day['profit']:.2f})" if worst_day['day'] != "N/A" else "N/A",
            "best_time": f"{best_time['time']} (₹{best_time['profit']:.2f})" if best_time['time'] != "N/A" else "N/A",
            "total_trades": total_trades,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "by_weekday": {},
            "by_time_of_day": {},
            "best_day": "N/A",
            "worst_day": "N/A",
            "best_time": "N/A",
            "total_trades": 0,
        }


@app.route("/api/comparison")
def api_comparison():
    """Get backtest vs live comparison data."""
    try:
        # TODO: Replace this with real backtest and live trade data
        # For now, use dummy data to demonstrate the comparison
        use_dummy = True  # Set to False once real trade data is available
        
        # Mock backtest performance (from historical backtesting)
        backtest_data = {
            "win_rate": 68.5,
            "total_pnl": 18500.0,
            "avg_profit": 308.33,
            "total_trades": 60,
            "max_drawdown": 7.5,
            "sharpe_ratio": 1.95,
        }
        
        # Mock live performance with realistic dummy data showing slight degradation from backtest
        # (This is typical in live trading due to slippage, fees, etc.)
        if use_dummy:
            live_data = {
                "win_rate": 62.2,  # Slightly lower than backtest (realistic)
                "total_pnl": 11500.25,  # Lower due to real-world conditions
                "avg_profit": 255.56,  # Lower avg profit per trade
                "total_trades": 45,  # Fewer trades executed
                "max_drawdown": 9.8,  # Slightly higher drawdown (worse)
                "sharpe_ratio": 1.65,  # Lower risk-adjusted returns
            }
        else:
            live_data = {
                "win_rate": 0.0,  # Will be populated from real trades
                "total_pnl": 0.0,
                "avg_profit": 0.0,
                "total_trades": 0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
            }
        
        # Try to get real live trading data if available
        sm = get_session_manager()
        positions = sm.get_positions()
        
        # Calculate real P&L if positions exist
        if positions:
            total_pnl = 0.0
            for p in positions:
                total_pnl += float(p.get("pnl", p.get("unrealized", 0)))
            live_data["total_pnl"] = total_pnl
            live_data["total_trades"] = sm.trade_count_today()
            
            # Calculate other metrics from positions
            if live_data["total_trades"] > 0:
                live_data["avg_profit"] = total_pnl / live_data["total_trades"]
                
                # Simple win rate calculation (count profitable positions)
                winning_trades = sum(1 for p in positions if float(p.get("pnl", p.get("unrealized", 0))) > 0)
                live_data["win_rate"] = (winning_trades / live_data["total_trades"]) * 100 if live_data["total_trades"] > 0 else 0
        
        return {
            "ok": True,
            "backtest": backtest_data,
            "live": live_data,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "backtest": {
                "win_rate": None,
                "total_pnl": None,
                "avg_profit": None,
                "total_trades": 0,
                "max_drawdown": None,
                "sharpe_ratio": None,
            },
            "live": {
                "win_rate": None,
                "total_pnl": None,
                "avg_profit": None,
                "total_trades": 0,
                "max_drawdown": None,
                "sharpe_ratio": None,
            },
        }


def _do_auto_close():
    sm = get_session_manager()
    if sm.is_trading_on() and sm.is_past_auto_close():
        sm.auto_close()


# Zerodha OAuth Token Generation Endpoints
@app.route("/api/zerodha/start-auth")
def start_zerodha_auth():
    """Start Zerodha OAuth flow - redirects user to Zerodha login"""
    try:
        from kiteconnect import KiteConnect
        api_key = os.getenv("ZERODHA_API_KEY")
        
        if not api_key:
            return {"error": "ZERODHA_API_KEY not configured", "ok": False}
        
        kite = KiteConnect(api_key=api_key)
        login_url = kite.login_url()
        
        return {"login_url": login_url, "ok": True}
    except Exception as e:
        return {"error": str(e), "ok": False}


@app.route("/kite/callback")
def zerodha_callback():
    """Handle Zerodha OAuth callback and generate access token"""
    request_token = request.args.get('request_token')
    status = request.args.get('status')
    
    if status != 'success' or not request_token:
        return render_template('oauth_result.html', 
                             success=False, 
                             message="Authorization failed. Please try again.")
    
    try:
        from kiteconnect import KiteConnect
        api_key = os.getenv("ZERODHA_API_KEY")
        api_secret = os.getenv("ZERODHA_API_SECRET")
        
        if not api_key or not api_secret:
            return render_template('oauth_result.html',
                                 success=False,
                                 message="API credentials not configured")
        
        kite = KiteConnect(api_key=api_key)
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        
        # Save to config with timestamp
        from engine.config_store import save_config
        config = load_config()
        config["ZERODHA_ACCESS_TOKEN"] = access_token
        config["ZERODHA_TOKEN_GENERATED_AT"] = datetime.now().isoformat()
        save_config(config)
        
        # Also set in environment for immediate use
        os.environ["ZERODHA_ACCESS_TOKEN"] = access_token
        
        return render_template('oauth_result.html',
                             success=True,
                             message="Access token generated successfully!",
                             token=access_token)
    except Exception as e:
        return render_template('oauth_result.html',
                             success=False,
                             message=f"Error: {str(e)}")


@app.route("/api/zerodha/check-auth")
def check_zerodha_auth():
    """Check if Zerodha is authenticated. Returns user_name and email for 'Logged in as' display."""
    try:
        apply_config_to_env()
        from kiteconnect import KiteConnect
        api_key = os.getenv("ZERODHA_API_KEY")
        access_token = os.getenv("ZERODHA_ACCESS_TOKEN")
        
        if not api_key or not access_token:
            return {"authenticated": False, "ok": True}
        
        # Get token generation timestamp from config (reload from file to get latest)
        config_path = Path(__file__).resolve().parent / "config.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        token_generated_at = config.get("ZERODHA_TOKEN_GENERATED_AT")
        
        # Calculate time remaining (tokens valid for 24 hours)
        time_remaining = None
        expires_at = None
        if token_generated_at:
            try:
                generated_time = datetime.fromisoformat(token_generated_at)
                expires_time = generated_time + timedelta(hours=24)
                expires_at = expires_time.isoformat()
                time_diff = expires_time - datetime.now()
                
                # Convert to seconds
                time_remaining = int(time_diff.total_seconds())
                
                print(f"[DEBUG] Token generated at: {token_generated_at}")
                print(f"[DEBUG] Expires at: {expires_at}")
                print(f"[DEBUG] Time remaining: {time_remaining} seconds ({time_remaining/3600:.2f} hours)")
                
                # If expired, mark as not authenticated
                if time_remaining <= 0:
                    return {
                        "authenticated": False,
                        "ok": True,
                        "expired": True,
                        "message": "Token has expired. Please generate a new one."
                    }
            except Exception as e:
                print(f"[ERROR] Error parsing token timestamp: {e}")
                import traceback
                traceback.print_exc()
        
        # Must successfully call Zerodha API to show "Connected" — otherwise token may be invalid/expired
        profile = {}
        try:
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            import socket
            socket.setdefaulttimeout(10)
            profile = kite.profile()
        except Exception as profile_err:
            print(f"[WARN] Zerodha profile failed (token invalid or network): {profile_err}")
            return {
                "authenticated": False,
                "ok": True,
                "message": "Token invalid or connection failed. Generate a new token from Settings."
            }
        
        # Prefer user_name, fallback to user_shortname or user_id
        user_name = (profile.get("user_name") or profile.get("user_shortname") or "").strip()
        if not user_name:
            user_name = profile.get("user_id") or "Zerodha User"
        email = (profile.get("email") or "").strip()
        
        return {
            "authenticated": True,
            "ok": True,
            "user_name": user_name,
            "email": email,
            "time_remaining_seconds": time_remaining,
            "expires_at": expires_at
        }
    except Exception as e:
        print(f"[ERROR] Auth check error: {e}")
        import traceback
        traceback.print_exc()
        return {"authenticated": False, "ok": True}


@app.route("/api/zerodha/profile")
def api_zerodha_profile():
    """Return full Zerodha profile, margins, and positions summary for the My Zerodha page. Always JSON."""
    try:
        data = get_zerodha_profile_info()
        return jsonify(data)
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})


@app.route("/api/market-calendar")
def api_market_calendar():
    """Market Intelligence Calendar for a given month. Returns holidays, expiry, events, earnings, AI mood."""
    month = request.args.get("month", "")
    if not month:
        from datetime import datetime
        month = datetime.now().strftime("%Y-%m")
    try:
        days = get_calendar_for_month(month)
        return jsonify({"ok": True, "month": month, "days": days})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "days": []}), 500


@app.route("/api/zerodha/search-symbols")
def api_zerodha_search_symbols():
    """Search NSE equity symbols from Zerodha with live price (fast with fallback)."""
    apply_config_to_env()
    q = (request.args.get("q") or "").strip()
    limit = min(30, max(5, int(request.args.get("limit", 20))))
    if len(q) < 2:
        return jsonify({"ok": True, "symbols": []})
    try:
        # Fast search without waiting for quotes
        results = search_instruments(q, limit=limit)
        if not results:
            return jsonify({"ok": True, "symbols": []})
        
        # Try to get quotes quickly (with timeout)
        nse_symbols = [r.get("symbol") or r.get("tradingsymbol", "") for r in results if (r.get("exchange") or "NSE") == "NSE" and (r.get("symbol") or r.get("tradingsymbol"))]
        
        quotes = {}
        try:
            # Try Zerodha quotes first
            quotes = get_quotes_bulk(nse_symbols) or {}
        except Exception as e:
            logger.debug(f"Zerodha quote fetch failed: {e}")
            quotes = {}
        
        # If Zerodha failed, try NSE fallback for important symbols
        if not quotes:
            try:
                from engine.data_fetcher import fetch_nifty50_live, fetch_bank_nifty_live
                # Fetch major indices as fallback
                for sym in ["NIFTY 50", "NIFTY50", "NIFTY"]:
                    if any(sym in r.get("tradingsymbol", "") for r in results):
                        nifty_data = fetch_nifty50_live()
                        if nifty_data:
                            quotes["NIFTY 50"] = {
                                "last": nifty_data.get("last_price"),
                                "open": nifty_data.get("open"),
                                "high": nifty_data.get("high"),
                                "low": nifty_data.get("low"),
                                "change": nifty_data.get("change"),
                                "change_pct": nifty_data.get("change_percent")
                            }
                        break
                
                for sym in ["NIFTY BANK", "BANKNIFTY", "BANK NIFTY"]:
                    if any(sym in r.get("tradingsymbol", "") for r in results):
                        bnf_data = fetch_bank_nifty_live()
                        if bnf_data:
                            quotes["NIFTY BANK"] = {
                                "last": bnf_data.get("last_price"),
                                "open": bnf_data.get("open"),
                                "high": bnf_data.get("high"),
                                "low": bnf_data.get("low"),
                                "change": bnf_data.get("change"),
                                "change_pct": bnf_data.get("change_percent")
                            }
                        break
            except Exception as e2:
                logger.debug(f"NSE fallback also failed: {e2}")
        
        for r in results:
            sym = (r.get("symbol") or r.get("tradingsymbol") or "").strip().upper()
            r["exchange"] = r.get("exchange", "NSE")
            
            # Try to match symbol in quotes
            found_quote = None
            if sym in quotes:
                found_quote = quotes[sym]
            elif sym.replace(" ", "") in quotes:
                found_quote = quotes[sym.replace(" ", "")]
            elif "NIFTY 50" in sym and "NIFTY 50" in quotes:
                found_quote = quotes["NIFTY 50"]
            elif "NIFTY BANK" in sym and "NIFTY BANK" in quotes:
                found_quote = quotes["NIFTY BANK"]
            
            if found_quote:
                r["last"] = found_quote.get("last", 0) or 0
                r["open"] = found_quote.get("open", 0) or 0
                r["high"] = found_quote.get("high", 0) or 0
                r["low"] = found_quote.get("low", 0) or 0
                r["change"] = found_quote.get("change", 0) or 0
                r["change_pct"] = found_quote.get("change_pct", 0) or 0
            else:
                # No quotes available - show 0 (market closed or data unavailable)
                r["last"] = 0
                r["open"] = 0
                r["high"] = 0
                r["low"] = 0
                r["change"] = 0
                r["change_pct"] = 0
        return jsonify({"ok": True, "symbols": results})
    except Exception as e:
        return jsonify({"ok": False, "symbols": [], "error": str(e)})


# Top intraday/F&O picks: liquid NSE stocks (futures & options). Score first N for faster response.
LIQUID_FNO_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL",
    "TATAMOTORS", "KOTAKBANK", "LT", "HINDUNILVR", "ITC", "AXISBANK", "MARUTI",
    "BAJFINANCE", "WIPRO", "HCLTECH", "ASIANPAINT", "TITAN", "SUNPHARMA",
]
# Gold & Silver ETFs (NSE) for AI Trading Agent commodity block
GOLD_SILVER_ETFS = ["GOLDBEES", "GOLDSHARE", "SILVERETF"]
INTRADAY_PICKS_STOCK_COUNT = 12  # Score 12 stocks in parallel for faster response
INTRADAY_PICKS_WORKERS = 6  # Parallel workers for scoring
INTRADAY_PICKS_CACHE_TTL = timedelta(minutes=5)
_intraday_picks_cache: dict | None = None
_intraday_picks_cache_time: datetime | None = None


def _score_stock_for_intraday(symbol: str) -> dict[str, Any]:
    """Score one stock using the same Today's Market Prediction logic (US bias, sentiment, technicals, indices, VIX, price vs open, depth, 15m). Data from Zerodha when connected."""
    try:
        pred = _get_market_prediction(symbol)
        score = pred.get("score", 0) or 0
        factors = pred.get("factors", [])
        prediction = pred.get("prediction", "NEUTRAL")
        return {
            "symbol": symbol,
            "score": round(float(score), 3),
            "tags": factors[:6],
            "prediction": prediction,
        }
    except Exception:
        return {"symbol": symbol, "score": 0.0, "tags": ["Error"], "prediction": "NEUTRAL"}


def _get_ai_trade_suggestion(picks: list[dict]) -> dict[str, Any]:
    """Combine picks with AI (OpenAI) or rule-based logic to suggest best 1-3 stocks to trade."""
    if not picks:
        return {"suggested_symbols": [], "reasoning": "No picks available.", "source": "none"}
    top_for_prompt = picks[:10]
    summary = "\n".join(
        f"- {p.get('symbol', '?')}: {p.get('prediction', 'NEUTRAL')}, score={p.get('score', 0):.2f}, factors: {', '.join((p.get('tags') or [])[:4])}"
        for p in top_for_prompt
    )
    api_key = (os.getenv("OPENAI_API_KEY") or load_config().get("OPENAI_API_KEY") or "").strip()
    if api_key:
        try:
            import requests as req
            r = req.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a concise intraday trading assistant for Indian NSE F&O. Reply in 1-3 short sentences. Suggest only from the given list.",
                        },
                        {
                            "role": "user",
                            "content": f"Based on these intraday picks (Today's Market Prediction + Zerodha data), which 1-3 stocks are the BEST to trade today for intraday/F&O? Reply with: (1) comma-separated symbols e.g. RELIANCE, TCS (2) one short reason.\n\n{summary}",
                        },
                    ],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                symbols = []
                for s in top_for_prompt:
                    if (s.get("symbol") or "").upper() in text.upper():
                        symbols.append((s.get("symbol") or "").upper())
                if not symbols:
                    symbols = [p.get("symbol", "").upper() for p in top_for_prompt[:3] if p.get("symbol")]
                return {"suggested_symbols": symbols[:3], "reasoning": text.strip() or "AI suggested based on scores.", "source": "openai"}
        except Exception as e:
            pass
    bullish = [p for p in top_for_prompt if (p.get("prediction") or "").upper() == "BULLISH" and (p.get("score") or 0) > 0.2]
    if bullish:
        suggested = [p.get("symbol", "").upper() for p in bullish[:3]]
        reasoning = f"Top BULLISH picks by score: {', '.join(suggested)}. Strong sentiment/technicals and positive intraday factors."
    else:
        suggested = [p.get("symbol", "").upper() for p in top_for_prompt[:3] if p.get("symbol")]
        reasoning = f"Top by combined score (no BULLISH above threshold): {', '.join(suggested)}. Consider lower conviction or wait for clearer setup."
    return {"suggested_symbols": suggested[:3], "reasoning": reasoning, "source": "rules"}


@app.route("/api/gpt-status")
def api_gpt_status():
    """Check if OpenAI API key works. Returns working=True/False and message."""
    api_key = (os.getenv("OPENAI_API_KEY") or load_config().get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return jsonify({"working": False, "message": "No OPENAI_API_KEY set. Add it in Settings → AI (optional)."})
    try:
        import requests as req
        r = req.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5,
            },
            timeout=10,
        )
        if r.status_code == 200:
            return jsonify({"working": True, "message": "GPT is working. AI suggestions will use OpenAI."})
        err = r.json().get("error", {}) if r.headers.get("content-type", "").startswith("application/json") else {}
        msg = err.get("message", r.text or f"HTTP {r.status_code}")
        return jsonify({"working": False, "message": f"OpenAI error: {msg}"})
    except Exception as e:
        return jsonify({"working": False, "message": str(e)})


@app.route("/api/intraday-picks")
def api_intraday_picks():
    """Top 15 intraday/F&O picks + AI/rules-based best-to-trade suggestion. Cached 5 min."""
    global _intraday_picks_cache, _intraday_picks_cache_time
    force = request.args.get("refresh", "").lower() in ("1", "true", "yes")
    now = datetime.now()
    if not force and _intraday_picks_cache is not None and _intraday_picks_cache_time is not None:
        if now - _intraday_picks_cache_time < INTRADAY_PICKS_CACHE_TTL:
            return jsonify(_intraday_picks_cache)
    symbols = LIQUID_FNO_STOCKS[:INTRADAY_PICKS_STOCK_COUNT]
    results = []
    with ThreadPoolExecutor(max_workers=INTRADAY_PICKS_WORKERS) as executor:
        future_to_sym = {executor.submit(_score_stock_for_intraday, sym): sym for sym in symbols}
        for future in as_completed(future_to_sym, timeout=75):
            sym = future_to_sym[future]
            try:
                results.append(future.result())
            except Exception:
                results.append({"symbol": sym, "score": 0.0, "tags": ["Error"], "prediction": "NEUTRAL"})
    # If as_completed timed out, add placeholders for any missing symbols
    got = {r.get("symbol") for r in results}
    for sym in symbols:
        if sym not in got:
            results.append({"symbol": sym, "score": 0.0, "tags": ["Timeout"], "prediction": "NEUTRAL"})
    results.sort(key=lambda x: -(x.get("score") or 0))
    picks = results[:15]
    ai_suggestion = _get_ai_trade_suggestion(picks)
    payload = {
        "picks": picks,
        "ai_suggestion": ai_suggestion,
        "cached_at": now.isoformat(),
    }
    _intraday_picks_cache = payload
    _intraday_picks_cache_time = now
    return jsonify(payload)


def _classify_signal_type(pick: dict) -> str:
    """Classify into Bullish Momentum / Oversold Bounce / News Breakout for display."""
    pred = (pick.get("prediction") or "NEUTRAL").upper()
    tags = pick.get("tags") or []
    tags_str = " ".join(tags).upper()
    if "SENTIMENT" in tags_str or "NEWS" in tags_str:
        return "News Breakout"
    if "RSI" in tags_str and ("BEARISH" in tags_str or "BULLISH" in tags_str):
        return "Oversold Bounce"
    return "Bullish Momentum" if pred == "BULLISH" else "Bearish Momentum"


def _volume_strength(pick: dict) -> str:
    """Infer volume strength from factors (Normal / High / Spike)."""
    tags = pick.get("tags") or []
    tags_str = " ".join(tags).upper()
    if "VOLUME" in tags_str or "SPIKE" in tags_str or "DEPTH" in tags_str:
        return "Spike"
    if "VWAP" in tags_str or "15M" in tags_str:
        return "High"
    return "Normal"


# Timeout for intraday scoring in AI trade signals (keep lower for faster page load)
INTRADAY_SIGNALS_TIMEOUT = 20


def _refresh_intraday_picks_cache_sync(timeout_sec: int = INTRADAY_SIGNALS_TIMEOUT) -> None:
    """Populate _intraday_picks_cache (symbols + ETFs). Call with lower timeout for API responsiveness."""
    global _intraday_picks_cache, _intraday_picks_cache_time
    now = datetime.now()
    symbols = LIQUID_FNO_STOCKS[:INTRADAY_PICKS_STOCK_COUNT]
    results = []
    with ThreadPoolExecutor(max_workers=INTRADAY_PICKS_WORKERS) as executor:
        future_to_sym = {executor.submit(_score_stock_for_intraday, sym): sym for sym in symbols}
        for future in as_completed(future_to_sym, timeout=timeout_sec):
            sym = future_to_sym[future]
            try:
                results.append(future.result())
            except Exception:
                results.append({"symbol": sym, "score": 0.0, "tags": ["Error"], "prediction": "NEUTRAL"})
    got = {r.get("symbol") for r in results}
    for sym in symbols:
        if sym not in got:
            results.append({"symbol": sym, "score": 0.0, "tags": ["Timeout"], "prediction": "NEUTRAL"})
    results.sort(key=lambda x: -(x.get("score") or 0))
    picks = results[:15]
    _intraday_picks_cache = {"picks": picks, "ai_suggestion": _get_ai_trade_suggestion(picks), "cached_at": now.isoformat()}
    _intraday_picks_cache_time = now


def _build_ai_trade_signals() -> dict:
    """Build momentum, reversal, news lists (top 3 each) for AI Trading Agent. Uses cached intraday picks when fresh; stale-while-revalidate when expired."""
    global _intraday_picks_cache, _intraday_picks_cache_time
    now = datetime.now()
    cache_fresh = (
        _intraday_picks_cache is not None
        and _intraday_picks_cache_time is not None
        and (now - _intraday_picks_cache_time) < INTRADAY_PICKS_CACHE_TTL
    )
    if not cache_fresh:
        if _intraday_picks_cache is not None and _intraday_picks_cache.get("picks"):
            # Stale-while-revalidate: return stale immediately, refresh in background
            Thread(target=_refresh_intraday_picks_cache_sync, kwargs={"timeout_sec": 45}).start()
            picks = _intraday_picks_cache.get("picks", [])
        else:
            _refresh_intraday_picks_cache_sync(timeout_sec=INTRADAY_SIGNALS_TIMEOUT)
            picks = _intraday_picks_cache.get("picks", []) if _intraday_picks_cache else []
    else:
        picks = _intraday_picks_cache.get("picks", [])

    def to_card(p: dict) -> dict:
        score_raw = (p.get("score") or 0) * 50 + 50
        score = max(0, min(100, int(score_raw)))
        return {
            "stock": p.get("symbol", ""),
            "score": score,
            "trend": "up" if (p.get("prediction") or "").upper() == "BULLISH" else "down",
            "volumeSignal": _volume_strength(p),
            "signalSummary": _classify_signal_type(p),
        }

    momentum, reversal, news = [], [], []
    for p in picks:
        card = to_card(p)
        tags = p.get("tags") or []
        tags_str = " ".join(tags).upper()
        if "SENTIMENT" in tags_str:
            news.append(card)
        elif "RSI" in tags_str:
            reversal.append(card)
        else:
            momentum.append(card)
    # Fill each category to 3 from remaining cards (by score) if needed
    used = set()
    def take(category_list: list, n: int) -> list:
        out = []
        for c in category_list:
            if c["stock"] not in used and len(out) < n:
                out.append(c)
                used.add(c["stock"])
        return out

    all_cards = sorted(
        [to_card(p) for p in picks],
        key=lambda c: -c["score"]
    )
    m_out = take(momentum, 3)
    for c in all_cards:
        if len(m_out) >= 3:
            break
        if c["stock"] not in used:
            m_out.append(c)
            used.add(c["stock"])
    r_out = take(reversal, 3)
    used_r = {x["stock"] for x in r_out}
    for c in all_cards:
        if len(r_out) >= 3:
            break
        if c["stock"] not in used_r:
            r_out.append(c)
            used_r.add(c["stock"])
    n_out = take(news, 3)
    used_n = {x["stock"] for x in n_out}
    for c in all_cards:
        if len(n_out) >= 3:
            break
        if c["stock"] not in used_n:
            n_out.append(c)
            used_n.add(c["stock"])
    # Gold & Silver ETF block: score ETFs separately and return top 3
    etf_picks = []
    for sym in GOLD_SILVER_ETFS:
        try:
            etf_picks.append(_score_stock_for_intraday(sym))
        except Exception:
            etf_picks.append({"symbol": sym, "score": 0.0, "tags": [], "prediction": "NEUTRAL"})
    etf_picks.sort(key=lambda x: -(x.get("score") or 0))
    etf_out = [to_card(p) for p in etf_picks[:3]]
    return {"momentum": m_out[:3], "reversal": r_out[:3], "news": n_out[:3], "etf": etf_out}


@app.route("/api/ai-trade-signals")
def api_ai_trade_signals():
    """GET /api/ai-trade-signals: momentum, reversal, news, etf (each top 3 for AI Trading Agent)."""
    try:
        raw = _build_ai_trade_signals()
        return jsonify({
            "momentum": raw.get("momentum", [])[:3],
            "reversal": raw.get("reversal", [])[:3],
            "news": raw.get("news", [])[:3],
            "etf": raw.get("etf", [])[:3],
        })
    except Exception as e:
        return jsonify({"momentum": [], "reversal": [], "news": [], "etf": [], "error": str(e)})


# --- Index Options AI Module (small capital: ₹3k–₹15k) ---
INDEX_CAPITAL_THRESHOLD = 15000  # Show index block when capital < this or no stock fits


def _compute_index_vwap_from_ohlc(df) -> float | None:
    """Compute VWAP from OHLC DataFrame (columns: Open, High, Low, Close, Volume). Returns None if insufficient data."""
    if df is None or df.empty or "Close" not in df.columns:
        return None
    if "Volume" not in df.columns:
        df = df.copy()
        df["Volume"] = 1
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    vol = df["Volume"]
    if vol.sum() == 0:
        return float(df["Close"].iloc[-1])
    return float((typical * vol).sum() / vol.sum())


# Cache for index market bias (short TTL to keep recommendations responsive)
_index_bias_cache: dict | None = None
_index_bias_cache_time: datetime | None = None
INDEX_BIAS_CACHE_TTL = timedelta(seconds=60)


def get_index_market_bias() -> dict:
    """
    AI market bias for NIFTY and BANKNIFTY. Uses live index, VIX, US close, optional 5m VWAP/trend.
    Returns: niftyBias, bankNiftyBias, confidence, reasons. Cached 60s for faster AI Agent load.
    """
    global _index_bias_cache, _index_bias_cache_time
    now = datetime.now()
    if _index_bias_cache is not None and _index_bias_cache_time is not None:
        if now - _index_bias_cache_time < INDEX_BIAS_CACHE_TTL:
            return _index_bias_cache
    reasons = []
    nifty_score = 0.0
    bank_nifty_score = 0.0

    nifty = fetch_nifty50_live()
    bank_nifty = fetch_bank_nifty_live()
    vix_data = fetch_india_vix()
    us_bias_data = _get_cached_us_bias()

    nifty_price = (nifty.get("price") or 0) or (nifty.get("open") or 0)
    nifty_open = nifty.get("open") or nifty_price
    nifty_pct = nifty.get("pct_change") or 0

    bn_price = (bank_nifty.get("price") or 0) or (bank_nifty.get("open") or 0)
    bn_open = bank_nifty.get("open") or bn_price
    bn_pct = bank_nifty.get("pct_change") or 0

    # Index vs VWAP proxy (price vs open)
    if nifty_price > 0 and nifty_open > 0:
        if nifty_price > nifty_open:
            nifty_score += 0.35
            reasons.append("Nifty above open (VWAP proxy)")
        else:
            nifty_score -= 0.35
            reasons.append("Nifty below open")

    if bn_price > 0 and bn_open > 0:
        if bn_price > bn_open:
            bank_nifty_score += 0.35
            if "Nifty above open" not in " ".join(reasons):
                reasons.append("Bank Nifty above open")
        else:
            bank_nifty_score -= 0.35

    # 5min trend (higher highs) – optional from OHLC
    try:
        df_nifty_5m = fetch_nse_ohlc("NIFTY 50", interval="5m", period="1d")
        if df_nifty_5m is not None and not df_nifty_5m.empty and len(df_nifty_5m) >= 2:
            last_c = float(df_nifty_5m["Close"].iloc[-1])
            prev_c = float(df_nifty_5m["Close"].iloc[-2])
            if last_c > prev_c:
                nifty_score += 0.2
                reasons.append("Nifty 5m higher close")
            else:
                nifty_score -= 0.2
        df_bn_5m = fetch_nse_ohlc("NIFTY BANK", interval="5m", period="1d")
        if df_bn_5m is not None and not df_bn_5m.empty and len(df_bn_5m) >= 2:
            last_c = float(df_bn_5m["Close"].iloc[-1])
            prev_c = float(df_bn_5m["Close"].iloc[-2])
            if last_c > prev_c:
                bank_nifty_score += 0.2
            else:
                bank_nifty_score -= 0.2
    except Exception:
        pass

    # Market breadth proxy: index green
    if nifty_pct and nifty_pct > 0:
        nifty_score += 0.2
        if "Strong breadth" not in " ".join(reasons):
            reasons.append("Strong breadth (index green)")
    elif nifty_pct is not None and nifty_pct < 0:
        nifty_score -= 0.2

    if bn_pct and bn_pct > 0:
        bank_nifty_score += 0.2
    elif bn_pct is not None and bn_pct < 0:
        bank_nifty_score -= 0.2

    # Bank Nifty vs Nifty relative strength
    if nifty_pct is not None and bn_pct is not None and bn_pct > nifty_pct:
        bank_nifty_score += 0.25
        reasons.append("Banks leading")
    elif nifty_pct is not None and bn_pct is not None and bn_pct < nifty_pct:
        bank_nifty_score -= 0.2

    # US market previous close
    us_pct = us_bias_data.get("sp500_pct_change")
    if us_pct is not None:
        if us_pct > 0:
            nifty_score += 0.15
            bank_nifty_score += 0.15
            reasons.append("Positive global cues")
        elif us_pct < -0.5:
            nifty_score -= 0.15
            bank_nifty_score -= 0.15

    # India VIX: rising/high = breakout chance (slight bullish bias for momentum)
    vix_val = vix_data.get("vix_value")
    if vix_val is not None:
        if vix_val > 18:
            reasons.append("Elevated VIX (breakout potential)")
        if vix_val < 12:
            reasons.append("Low VIX (range-bound)")

    def to_bias(score: float) -> str:
        if score > 0.2:
            return "BULLISH"
        if score < -0.2:
            return "BEARISH"
        return "NEUTRAL"

    nifty_bias = to_bias(nifty_score)
    bank_nifty_bias = to_bias(bank_nifty_score)

    # Safety: do not show trade if both NEUTRAL and VIX very low + flat
    if vix_val is not None and vix_val < 11 and nifty_bias == "NEUTRAL" and bank_nifty_bias == "NEUTRAL":
        reasons.append("Market lacks clear direction. Wait for better setup.")

    confidence = min(100, max(0, int(50 + (abs(nifty_score) + abs(bank_nifty_score)) * 25)))
    if not reasons:
        reasons.append("Index vs open and trend")

    out = {
        "niftyBias": nifty_bias,
        "bankNiftyBias": bank_nifty_bias,
        "confidence": confidence,
        "reasons": reasons[:6],
        "niftyScore": round(nifty_score, 2),
        "bankNiftyScore": round(bank_nifty_score, 2),
        "vixValue": vix_val,
    }
    _index_bias_cache = out
    _index_bias_cache_time = now
    return out


def get_affordable_index_options(
    index_name: str,
    bias: str,
    max_risk_per_trade: float,
    confidence: int | None = None,
) -> tuple[list, dict, bool]:
    """
    Get 2–3 affordable weekly index options (ATM, 1 OTM, 2 OTM) filtered by max_risk_per_trade.
    Returns (options_list, ai_recommendation, safe_to_show).
    """
    index_name = (index_name or "").upper().replace(" ", "")
    if index_name not in ("NIFTY", "BANKNIFTY", "NIFTY50", "BANKNIFTY50"):
        if "BANK" in index_name:
            index_name = "BANKNIFTY"
        else:
            index_name = "NIFTY"

    if bias == "NEUTRAL":
        return [], {}, False

    # Index config: strike step, lot size, symbol for quote
    if index_name == "BANKNIFTY":
        strike_step = 100
        lot_size = 15
        quote_symbol = "NIFTY BANK"
    else:
        strike_step = 50
        lot_size = 25
        quote_symbol = "NIFTY 50"

    try:
        if quote_symbol == "NIFTY 50":
            live = fetch_nifty50_live()
        else:
            live = fetch_bank_nifty_live()
        spot = float(live.get("price") or live.get("open") or 0)
    except Exception:
        spot = 24500.0 if index_name == "NIFTY" else 52000.0

    if spot <= 0:
        spot = 24500.0 if index_name == "NIFTY" else 52000.0

    base_strike = round(spot / strike_step) * strike_step
    use_ce = bias == "BULLISH"

    # ATM, 1 OTM, 2 OTM (for CE: OTM = strike > spot; for PE: OTM = strike < spot)
    strikes = []
    if use_ce:
        strikes = [base_strike, base_strike + strike_step, base_strike + 2 * strike_step]
    else:
        strikes = [base_strike, base_strike - strike_step, base_strike - 2 * strike_step]

    # Mock premiums (index options: typically tens to low hundreds)
    # Budget check: total_cost = premium * lot_size (user pays this); compare total_cost <= budget
    options = []
    for i, strike in enumerate(strikes):
        if use_ce:
            prem = max(50, 80 - (strike - spot) / 2 + (30 if i == 0 else 0))
        else:
            prem = max(50, 80 + (spot - strike) / 2 + (30 if i == 0 else 0))
        prem = round(prem, 2)
        total_cost = prem * lot_size
        within_budget = total_cost <= max_risk_per_trade
        options.append({
            "type": "CE" if use_ce else "PE",
            "strike": strike,
            "premium": prem,
            "lotSize": lot_size,
            "lotCost": total_cost,
            "totalCost": round(total_cost, 2),
            "distanceFromATM": i,
            "status": "Affordable" if within_budget else "Over Budget",
            "canTrade": within_budget,
        })

    # Sort by closest to ATM, then by premium; return all (frontend shows status per row)
    options.sort(key=lambda x: (x["distanceFromATM"], x["premium"]))
    top = options[:3]

    # AI recommendation text
    direction = "BUY CE" if use_ce else "BUY PE"
    move_type = "Momentum" if bias == "BULLISH" else "Reversal"
    if bias == "BEARISH":
        move_type = "Momentum"
    summary = (
        f"{'NIFTY' if index_name == 'NIFTY' else 'Bank Nifty'} is trading "
        f"{'above' if bias == 'BULLISH' else 'below'} open with {bias.lower()} intraday bias. "
        "Suitable for small-capital weekly options."
    )

    rec = {
        "direction": direction,
        "confidence": confidence if confidence is not None else 65,
        "expectedMoveType": move_type,
        "holdingTime": "20-90 min",
        "summary": summary,
    }

    # Safe to show only if bias is clear
    safe = bias != "NEUTRAL" and (float(max_risk_per_trade) > 0)
    return top, rec, safe


# --- AI Trade Recommendation + Session-Based Continuous Strategy Automation ---
# Execution modes: LIVE (Zerodha), PAPER (simulated balance), BACKTEST (historical)
INTRADAY_CUTOFF_TIME = time(15, 15)  # 3:15 PM IST
# DEPRECATED: No longer used - replaced by dynamic hourly frequency
# MAX_TRADES_PER_SESSION = 10
SESSION_ENGINE_INTERVAL_SEC = 60
_SESSIONS_DIR = Path(__file__).resolve().parent / "data"
_SESSIONS_FILE = _SESSIONS_DIR / "trade_sessions.json"
_sessions_lock = Lock()
_trade_sessions: list[dict] = []
# Engine state: running = tick runs; last_tick = timestamp of last successful tick (for UI)
engine_state: dict = {"running": True, "last_tick": None}
_backtest_progress: dict = {}  # Storage for live backtest progress updates
_last_session_engine_tick_time: datetime | None = None  # For next-scan countdown (set each tick)


def is_market_open(now: datetime | None = None) -> bool:
    """True if NSE market hours (weekday 9:15–15:30 IST). Saturday=5, Sunday=6 => closed."""
    now = now or datetime.now(ZoneInfo("Asia/Kolkata"))
    if now.weekday() >= 5:  # Saturday, Sunday
        return False
    market_open = time(9, 15)
    market_close = time(15, 30)
    return market_open <= now.time() <= market_close


def _load_trade_sessions() -> None:
    """Load persisted sessions from JSON (called at startup)."""
    global _trade_sessions
    with _sessions_lock:
        if not _SESSIONS_FILE.exists():
            _trade_sessions = []
            return
        try:
            with open(_SESSIONS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            _trade_sessions = data.get("sessions") or []
            
            # Backward compatibility: Initialize new frequency fields for old sessions
            now = datetime.now(ZoneInfo("Asia/Kolkata"))
            for session in _trade_sessions:
                if "current_hour_block" not in session:
                    session["current_hour_block"] = now.hour
                if "hourly_trade_count" not in session:
                    session["hourly_trade_count"] = 0
                if "frequency_mode" not in session:
                    session["frequency_mode"] = "NORMAL"
            
        except Exception as e:
            logger.exception("Load trade sessions error: %s", str(e))
            _trade_sessions = []


def _save_trade_sessions() -> None:
    """Persist sessions to JSON."""
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    with _sessions_lock:
        try:
            with open(_SESSIONS_FILE, "w", encoding="utf-8") as f:
                json.dump({"sessions": _trade_sessions, "updatedAt": datetime.now().isoformat()}, f, indent=2)
        except Exception as e:
            logger.exception("Save trade sessions error: %s", str(e))


# Load persisted sessions on startup (after first request may have created data dir)
_load_trade_sessions()


def _session_date(session: dict) -> date | None:
    """Return session's calendar date (from createdAt)."""
    created = session.get("createdAt")
    if not created:
        return None
    try:
        if isinstance(created, str):
            return datetime.fromisoformat(created.replace("Z", "+00:00")).date()
        return None
    except Exception:
        return None


def _build_ai_trade_recommendation_stock(
    stock: str, capital: float, risk_pct: float
) -> dict[str, Any]:
    """Build a single AI trade recommendation for a stock. No strike selection by user."""
    risk_per_trade = capital * (risk_pct / 100.0) if capital and risk_pct else 0
    options, rec, pred = _mock_option_chain(stock.upper())
    stock_indicators = {
        "score": pred.get("score"),
        "prediction": pred.get("prediction"),
        "rsi": pred.get("rsi"),
        "sentiment_score": pred.get("sentiment_score"),
    }
    market_indicators = {"vix_high": pred.get("vix_high", False)}
    suggested_ids = get_suggested_algos(stock_indicators, market_indicators, top_n=1)
    algo = get_algo_by_id(suggested_ids[0]) if suggested_ids else None
    direction = (rec.get("direction") or "CE").replace("BUY ", "")
    # Pick best strike: ATM (first matching CE/PE in options)
    best_opt = next((o for o in options if o.get("type") == direction), options[0] if options else {})
    strike = best_opt.get("strike", 0)
    lot_size = best_opt.get("lotSize", 1)
    premium = best_opt.get("premium", 0)
    total_cost = premium * lot_size
    lots = max(1, int(risk_per_trade / total_cost)) if total_cost else 1
    market_bias = (pred.get("prediction") or "NEUTRAL").capitalize()
    pred_dir = (pred.get("prediction") or "").upper()
    detected_market = ["TRENDING", "DIRECTIONAL"] if pred_dir in ("BULLISH", "BEARISH") else ["RANGE_BOUND"]
    factors_str = " ".join(pred.get("factors") or [])
    if "volume" in factors_str.lower() or "Volume" in factors_str:
        detected_market.append("HIGH_VOLUME")
    groups_meta = {g["id"]: g["name"] for g in load_strategy_groups()}
    selected_group_id = get_primary_group(algo) if algo else ""
    return {
        "instrumentType": "stock",
        "instrument": stock.upper(),
        "symbol": stock.upper(),
        "marketBias": market_bias,
        "strategyId": algo.get("id") if algo else "",
        "strategyName": algo.get("name") if algo else "Momentum Breakout",
        "tradeType": "CALL" if direction == "CE" else "PUT",
        "suggestedStrike": str(strike) + " " + direction,
        "strike": strike,
        "optionType": direction,
        "entryCondition": (algo.get("entryLogic") or rec.get("reason") or "Break above day high / trend confirmation"),
        "stopLossLogic": (algo.get("stopLogic") if algo else None) or "Previous swing low / VWAP break",
        "riskPerTrade": round(risk_per_trade, 2),
        "positionSizeLots": lots,
        "rewardLogic": (algo.get("exitLogic") if algo else None) or "Trail stop / target 1.5R / structure exit",
        "confidence": rec.get("confidence", 50),
        "totalCost": round(total_cost * lots, 2),
        "detectedMarket": detected_market,
        "suggestedAlgos": [{"id": aid, "name": (get_algo_by_id(aid) or {}).get("name", aid)} for aid in get_suggested_algos(stock_indicators, market_indicators, top_n=3)],
        "selectedAlgoName": algo.get("name") if algo else None,
        "selectedAlgoGroup": groups_meta.get(selected_group_id, ""),
    }


def _build_ai_trade_recommendation_index(
    index_label: str, capital: float, bias_data: dict | None = None
) -> dict[str, Any] | None:
    """Build a single AI trade recommendation for NIFTY or BANKNIFTY. Optional bias_data avoids re-fetch."""
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
    
    options, ai_rec, _ = get_affordable_index_options(label, bias, capital, confidence=bias_data.get("confidence"))
    if not options:
        return None
    best = options[0]
    opt_type = best.get("type", "CE")
    strike = best.get("strike", 0)
    lot_size = best.get("lotSize", 25)
    premium = best.get("premium", 0)
    
    # Use centralized position sizing
    lots, total_cost, can_afford = calculate_fo_position_size(capital, premium, lot_size)
    
    # Only recommend if we can afford at least 1 lot
    if not can_afford or lots < 1:
        logger.info(f"[F&O] Insufficient capital for {label}. Recommended 0 lots.")
        return None
    
    risk_per_trade = min(capital * 0.02, total_cost)  # cap at 2% of capital
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
        "rewardLogic": "Trail or 20–90 min holding time",
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


@app.route("/api/ai-trade-recommendation")
def api_ai_trade_recommendation():
    """GET /api/ai-trade-recommendation?instrument=RELIANCE|NIFTY|BANKNIFTY. Returns one AI recommendation card (no strike selection)."""
    instrument = (request.args.get("instrument") or "").strip().upper()
    if not instrument:
        return jsonify({"error": "Missing instrument"}), 400
    capital = request.args.get("capital", type=float) or 100000.0
    risk_pct = request.args.get("risk_pct", type=float) or 2.0
    try:
        if instrument in ("NIFTY", "BANKNIFTY"):
            rec = _build_ai_trade_recommendation_index(instrument, capital)
        else:
            rec = _build_ai_trade_recommendation_stock(instrument, capital, risk_pct)
        if rec is None:
            return jsonify({"error": "No recommendation (e.g. neutral bias)", "recommendation": None})
        return jsonify({"recommendation": rec})
    except Exception as e:
        return jsonify({"error": str(e), "recommendation": None}), 500


@app.route("/api/ai-trade-recommendations-index")
def api_ai_trade_recommendations_index():
    """GET /api/ai-trade-recommendations-index?capital=... Returns NIFTY and BANKNIFTY in one response (one bias fetch)."""
    capital = request.args.get("capital", type=float) or 100000.0
    try:
        bias_data = get_index_market_bias()
        nifty_rec = _build_ai_trade_recommendation_index("NIFTY", capital, bias_data=bias_data)
        bank_rec = _build_ai_trade_recommendation_index("BANKNIFTY", capital, bias_data=bias_data)
        return jsonify({"nifty": nifty_rec, "banknifty": bank_rec})
    except Exception as e:
        return jsonify({"nifty": None, "banknifty": None, "error": str(e)})


@app.route("/api/approve-trade", methods=["POST"])
def api_approve_trade():
    """POST /api/approve-trade: create ACTIVE trade session. execution_mode: LIVE | PAPER | BACKTEST."""
    global _trade_sessions
    data = request.get_json() or {}
    rec = data.get("recommendation") or data
    if not rec or not rec.get("instrument"):
        return jsonify({"ok": False, "error": "Missing recommendation"}), 400
    instrument = (rec.get("instrument") or "").strip().upper()
    execution_mode = (data.get("execution_mode") or rec.get("execution_mode") or "PAPER").upper()
    if execution_mode not in ("LIVE", "PAPER", "BACKTEST"):
        execution_mode = "PAPER"
    virtual_balance = data.get("virtual_balance")
    if execution_mode in ("PAPER", "BACKTEST"):
        try:
            virtual_balance = float(virtual_balance) if virtual_balance is not None else 100000.0
        except (TypeError, ValueError):
            virtual_balance = 100000.0
    else:
        virtual_balance = None
    session_id = f"ts_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(_trade_sessions)}"
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    
    # Calculate daily loss limit from capital (virtual_balance) and settings
    from engine.trade_frequency import calculate_max_daily_loss_limit
    capital_for_loss_calc = virtual_balance if virtual_balance is not None else 100000.0
    daily_loss_limit = calculate_max_daily_loss_limit(capital_for_loss_calc)
    logger.info(f"[SESSION] Auto-calculated daily loss limit: Rs.{daily_loss_limit:.2f} for capital Rs.{capital_for_loss_calc:.2f}")
    
    tradingsymbol = rec.get("tradingsymbol") or instrument
    exchange = rec.get("exchange") or "NSE"
    lot_size = int(rec.get("lot_size") or rec.get("lotSize") or 1)
    
    # AI Auto-Switching configuration (enabled by default)
    ai_auto_switching_enabled = data.get("ai_auto_switching_enabled", True)  # Default: AI ON
    ai_check_interval = data.get("ai_check_interval_minutes", 5)  # Default: 5 min
    
    session = {
        "sessionId": session_id,
        "instrument": instrument,
        "mode": "INTRADAY",
        "status": "ACTIVE",
        "execution_mode": execution_mode,
        "virtual_balance": virtual_balance,
        "trades_taken_today": 0,
        "daily_pnl": 0.0,
        "daily_loss_limit": daily_loss_limit,
        "cutoff_time": "15:15",
        "current_trade_id": None,
        "current_trade": None,
        "recommendation": rec,
        "tradingsymbol": tradingsymbol,
        "exchange": exchange,
        "lot_size": lot_size,
        "createdAt": now.isoformat(),
        # AI Strategy Auto-Switching (enabled by default)
        "ai_auto_switching_enabled": ai_auto_switching_enabled,
        "ai_check_interval_minutes": ai_check_interval,
        "last_ai_strategy_check": None,
        "last_ai_recommendation": None,
        "ai_strategy_switches": 0,
        # Dynamic Trade Frequency (hourly tracking)
        "current_hour_block": now.hour,
        "hourly_trade_count": 0,
        "frequency_mode": "NORMAL",
    }
    _trade_sessions.append(session)
    _save_trade_sessions()
    return jsonify({
        "ok": True,
        "sessionId": session_id,
        "execution_mode": execution_mode,
        "message": "Session active (%s). Engine will trade up to %d times until cutoff." % (execution_mode, max_trades),
    })


def _pick_best_strategy(instrument: str, session: dict | None = None) -> tuple[str, str]:
    """
    Return (strategy_id, strategy_name) for current market.
    If session has AI auto-switching enabled, uses the current AI-selected strategy.
    Otherwise uses rule-based strategy selection.
    """
    # Note: AI auto-switching now happens in _run_session_engine_tick()
    # This function just returns the currently assigned strategy
    
    # Fallback to rule-based strategy selection
    instrument = (instrument or "").strip().upper()
    if instrument in ("NIFTY", "BANKNIFTY"):
        return "index_lead_stock_lag", "Index Momentum"
    try:
        pred = _get_cached_prediction(instrument)
        stock_indicators = {
            "score": pred.get("score"),
            "prediction": pred.get("prediction"),
            "rsi": pred.get("rsi"),
            "sentiment_score": pred.get("sentiment_score"),
        }
        market_indicators = {"vix_high": pred.get("vix_high", False)}
        ids = get_suggested_algos(stock_indicators, market_indicators, top_n=1)
        if ids:
            algo = get_algo_by_id(ids[0])
            return ids[0], (algo.get("name") if algo else "Momentum Breakout")
        return "momentum_breakout", "Momentum Breakout"
    except Exception:
        return "momentum_breakout", "Momentum Breakout"


def _get_ai_recommended_strategy(session: dict) -> tuple[str, str] | None:
    """
    Use AI to recommend best strategy based on current market conditions.
    Caches recommendation for AI_STRATEGY_CHECK_INTERVAL_MINUTES.
    Returns (strategy_id, strategy_name) or None.
    """
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    
    # Check if we need to refresh AI recommendation
    last_check = session.get("ai_last_check_time")
    check_interval_minutes = session.get("ai_check_interval_minutes", 15)  # Default 15 min
    
    if last_check:
        last_check_dt = datetime.fromisoformat(last_check)
        elapsed_minutes = (now - last_check_dt).total_seconds() / 60
        if elapsed_minutes < check_interval_minutes:
            # Use cached recommendation
            cached_strategy = session.get("ai_recommended_strategy")
            if cached_strategy:
                logger.info(f"[AI MODE] Using cached strategy: {cached_strategy}")
                return (cached_strategy.lower().replace(" ", "_"), cached_strategy)
    
    # Fetch current market data
    try:
        nifty_data = fetch_nifty50_live()
        banknifty_data = fetch_bank_nifty_live()
        vix = fetch_india_vix()
        
        # Get recent candles for the session's instrument
        instrument = session.get("instrument", "NIFTY")
        from strategies import data_provider as strategy_data_provider
        candles = strategy_data_provider.get_recent_candles(instrument, interval="5m", count=10, period="1d")
        
        # Build market context
        context = get_market_context(
            nifty_price=nifty_data.get("price"),
            nifty_change_pct=nifty_data.get("change_percent"),
            banknifty_price=banknifty_data.get("price"),
            banknifty_change_pct=banknifty_data.get("change_percent"),
            vix=vix,
            current_time=now.strftime("%Y-%m-%d %H:%M:%S"),
            recent_candles=candles,
        )
        
        # Get current strategy name
        current_strategy = (session.get("recommendation") or {}).get("strategyName")
        
        # Get AI recommendation
        logger.info(f"[AI MODE] Requesting strategy recommendation for {instrument}...")
        recommendation = get_ai_strategy_recommendation(context, current_strategy)
        
        if recommendation:
            recommended_strategy = recommendation.get("recommended_strategy")
            confidence = recommendation.get("confidence", "medium")
            reasoning = recommendation.get("reasoning", "")
            
            # Store in session
            session["ai_last_check_time"] = now.isoformat()
            session["ai_recommended_strategy"] = recommended_strategy
            session["ai_recommendation_confidence"] = confidence
            session["ai_recommendation_reasoning"] = reasoning
            session["ai_last_recommendation"] = recommendation
            
            logger.info(
                f"[AI MODE] New recommendation: {recommended_strategy} "
                f"(Confidence: {confidence})"
            )
            logger.info(f"[AI MODE] Reasoning: {reasoning}")
            
            # Convert strategy name to ID format
            strategy_id = recommended_strategy.lower().replace(" ", "_")
            return (strategy_id, recommended_strategy)
        else:
            logger.warning("[AI MODE] No AI recommendation received, using fallback")
            return None
            
    except Exception as e:
        logger.exception(f"[AI MODE] Error getting AI recommendation: {e}")
        return None


def _fetch_session_ltp(session: dict) -> float | None:
    """Fetch current LTP: NFO sessions use tradingsymbol only; NSE use instrument. Hard-enforce symbol+exchange."""
    instrument = session.get("instrument")
    tradingsymbol = session.get("tradingsymbol")
    exchange = (session.get("exchange") or "NSE").strip().upper()
    ltp = None
    try:
        if exchange == "NFO" and tradingsymbol:
            q = strategy_data_provider.get_quote(tradingsymbol, exchange="NFO")
            ltp = float(q.get("last", 0) or q.get("last_price", 0)) or None
        else:
            if instrument:
                ltp = strategy_data_provider.get_ltp(instrument)
    except Exception as e:
        logger.error(
            "LTP FETCH FAILED | instrument=%s | tradingsymbol=%s | exchange=%s | error=%s",
            instrument,
            tradingsymbol,
            exchange,
            str(e),
        )
        ltp = None
    return ltp


def _check_entry_real(session: dict, strategy_name_override: str | None = None) -> tuple[bool, float | None]:
    """
    UNIFIED ENTRY CHECK - Uses shared logic with backtest.
    """
    from engine.unified_entry import should_enter_trade
    
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    strategy_name = strategy_name_override or (session.get("recommendation") or {}).get("strategyName") or "Momentum Breakout"
    instrument = session.get("instrument") or "—"
    ltp = _fetch_session_ltp(session)
    execution_mode = session.get("execution_mode", "PAPER")
    
    if ltp is None or ltp <= 0:
        logger.warning(f"ENTRY CHECK | {instrument} | Invalid LTP={ltp}")
        session["entry_diagnostics"] = {
            "last_check": now.isoformat(),
            "strategy": strategy_name,
            "ltp": ltp,
            "entry_price": None,
            "can_enter": False,
            "blocked_reason": "Invalid price",
            "conditions": {},
        }
        return False, None
    
    # Get recent candles for analysis
    recent_candles = None
    try:
        from engine.data_fetcher import get_ohlc_for_date
        today = now.date()
        recent_candles = get_ohlc_for_date(instrument, today, interval="5m")
        if recent_candles and len(recent_candles) > 10:
            recent_candles = recent_candles[-10:]  # Last 10 candles
    except Exception as e:
        logger.debug(f"Could not get recent candles for {instrument}: {e}")
    
    # USE UNIFIED ENTRY LOGIC (same as backtest) WITH AI VALIDATION
    ai_enabled = session.get("ai_auto_switching_enabled", False)  # Check if AI is enabled for this session
    
    should_enter, reason = should_enter_trade(
        mode=execution_mode,
        current_price=ltp,
        recent_candles=recent_candles,
        strategy_name=strategy_name,
        frequency_check_passed=True,  # Frequency checked separately
        instrument=instrument,  # Pass instrument for AI context
        use_ai=ai_enabled,  # Enable AI validation if session has AI enabled
    )
    
    # Store diagnostics
    diag = {
        "last_check": now.isoformat(),
        "strategy": strategy_name,
        "ltp": ltp,
        "entry_price": ltp if should_enter else None,
        "can_enter": should_enter,
        "blocked_reason": None if should_enter else reason,
        "conditions": {"unified_entry": True, "same_as_backtest": True},
    }
    session["entry_diagnostics"] = diag
    
    logger.info(
        "ENTRY CHECK | %s | Strategy=%s | LTP=%s | can_enter=%s | reason=%s",
        instrument, strategy_name, ltp, should_enter, reason
    )
    
    return should_enter, ltp if should_enter else None


def _manage_trade_real(session: dict) -> bool:
    """Use strategy check_exit (same strategy that opened the trade); if exit reason, call execute_exit."""
    trade = session.get("current_trade")
    if not trade:
        return False
    try:
        strategy_name = trade.get("strategy_name")
        strategy = get_strategy_for_session(session, strategy_data_provider, strategy_name_override=strategy_name)
        if not strategy:
            return False
        exit_reason = strategy.check_exit(trade)
        if not exit_reason:
            return False
        execute_exit(session)
        return True
    except Exception as e:
        logger.exception("Manage trade exit error: %s", str(e))
        return False


def _run_session_engine_tick() -> None:
    """Background tick: for each ACTIVE session, apply guard rails, manage open trade or scan for entry."""
    global _last_session_engine_tick_time
    if not engine_state.get("running", True):
        return
    if not is_market_open():
        return
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    _last_session_engine_tick_time = now
    active_count = sum(1 for s in _trade_sessions if s.get("status") == "ACTIVE")
    logger.info("ENGINE TICK | active_sessions=%s", active_count)
    for s in _trade_sessions:
        if s.get("status") == "ACTIVE":
            logger.info(
                "ENGINE TICK | instrument=%s | exchange=%s | tradingsymbol=%s",
                s.get("instrument"),
                s.get("exchange"),
                s.get("tradingsymbol"),
            )
    today = now.date()
    try:
        cutoff = INTRADAY_CUTOFF_TIME
        if now.time() >= cutoff:
            for s in _trade_sessions:
                if s.get("status") == "ACTIVE":
                    s["status"] = "STOPPED"
            _save_trade_sessions()
            engine_state["last_tick"] = now.isoformat()
            return
    except Exception as e:
        logger.exception("Engine tick cutoff error: %s", str(e))
        return
    for session in _trade_sessions:
        if session.get("status") != "ACTIVE":
            continue
        if (session.get("execution_mode") or "").upper() == "BACKTEST":
            continue
        session_date = _session_date(session)
        if session_date is not None and session_date < today:
            session["status"] = "STOPPED"
            continue
        
        # Reset hourly trade count if hour changed
        current_hour = now.hour
        if session.get("current_hour_block") != current_hour:
            session["current_hour_block"] = current_hour
            session["hourly_trade_count"] = 0
            logger.info(f"[FREQ] Hour changed to {current_hour}, resetting hourly count for {session.get('instrument')}")
        
        daily_limit = session.get("daily_loss_limit")
        if daily_limit is not None and (session.get("daily_pnl") or 0) <= -float(daily_limit):
            session["status"] = "STOPPED"
            continue
        if session.get("current_trade_id"):
            try:
                if _manage_trade_real(session):
                    _save_trade_sessions()
            except Exception as e:
                logger.exception("Engine tick manage trade error: %s", str(e))
            continue
        
        # AI Strategy Auto-Switching (if enabled)
        if session.get("ai_auto_switching_enabled", False):
            last_ai_check = session.get("last_ai_strategy_check")
            ai_check_interval_minutes = session.get("ai_check_interval_minutes", 5)  # Default: check every 5 min
            should_run_ai = True
            if last_ai_check:
                try:
                    last_check_dt = datetime.fromisoformat(last_ai_check)
                    minutes_since = (now - last_check_dt).total_seconds() / 60
                    should_run_ai = minutes_since >= ai_check_interval_minutes
                except Exception:
                    pass
            
            if should_run_ai:
                try:
                    # Gather market context
                    nifty = fetch_nifty50_live()
                    banknifty = fetch_bank_nifty_live()
                    vix = fetch_india_vix()
                    
                    # Get recent candles for price action analysis
                    instrument = session.get("instrument", "")
                    recent_candles = None
                    try:
                        candles_df = strategy_data_provider.get_recent_candles(instrument, interval="5m", count=10, period="1d")
                        if candles_df:
                            recent_candles = [
                                {
                                    "high": c.get("high", 0),
                                    "low": c.get("low", 0),
                                    "close": c.get("close", 0),
                                    "volume": c.get("volume", 0),
                                }
                                for c in candles_df
                            ]
                    except Exception:
                        pass
                    
                    context = get_market_context(
                        nifty_price=nifty.get("last_price") if nifty else None,
                        nifty_change_pct=nifty.get("change_percent") if nifty else None,
                        banknifty_price=banknifty.get("last_price") if banknifty else None,
                        banknifty_change_pct=banknifty.get("change_percent") if banknifty else None,
                        vix=vix,
                        current_time=now.strftime("%Y-%m-%d %H:%M:%S"),
                        recent_candles=recent_candles,
                    )
                    
                    current_strategy = (session.get("recommendation") or {}).get("strategyName")
                    
                    # === ENHANCED AI DECISION LOGGING ===
                    logger.info(
                        "╔══════════════════════════════════════════════════════════════╗\n"
                        "║ AI STRATEGY EVALUATION                                       ║\n"
                        "╠══════════════════════════════════════════════════════════════╣"
                    )
                    logger.info(f"║ Instrument: {session.get('instrument', 'Unknown'):<48} ║")
                    logger.info(f"║ Current Strategy: {current_strategy or 'None':<42} ║")
                    logger.info(f"║ NIFTY: {context.get('nifty_price', 'N/A'):<10} | Change: {context.get('nifty_change_pct', 0):.2f}%{' '*19} ║")
                    vix_value = context.get('vix', 'N/A')
                    vix_str = str(vix_value) if not isinstance(vix_value, dict) else str(vix_value.get('value', 'N/A'))
                    logger.info(f"║ VIX: {vix_str:<10}{' '*43} ║")
                    logger.info("╠══════════════════════════════════════════════════════════════╣")
                    
                    ai_recommendation = get_ai_strategy_recommendation(context, current_strategy)
                    
                    session["last_ai_strategy_check"] = now.isoformat()
                    session["last_ai_recommendation"] = ai_recommendation
                    
                    if ai_recommendation:
                        recommended_strategy = ai_recommendation.get("recommended_strategy", "N/A")
                        confidence = ai_recommendation.get("confidence", "N/A")
                        reasoning = ai_recommendation.get("reasoning", "No reasoning provided")
                        market_condition = ai_recommendation.get("market_condition", "N/A")
                        
                        logger.info(f"║ GPT Recommended: {recommended_strategy:<43} ║")
                        logger.info(f"║ Confidence: {confidence:<48} ║")
                        logger.info(f"║ Market Condition: {market_condition:<44} ║")
                        logger.info("╠══════════════════════════════════════════════════════════════╣")
                        logger.info(f"║ GPT Reasoning:")
                        for line in reasoning.split('. '):
                            if line.strip():
                                logger.info(f"║   • {line.strip()[:58]:<58} ║")
                        logger.info("╠══════════════════════════════════════════════════════════════╣")
                        
                        should_switch, new_strategy = should_switch_strategy(
                            ai_recommendation,
                            current_strategy,
                            min_confidence="medium",
                        )
                        
                        if should_switch and new_strategy:
                            logger.info(
                                f"║ DECISION: SWITCH TO {new_strategy:<39} ║\n"
                                f"║ Reason: Confidence threshold met ({confidence})         ║\n"
                                "╚══════════════════════════════════════════════════════════════╝"
                            )
                            # Update session strategy
                            if "recommendation" not in session:
                                session["recommendation"] = {}
                            session["recommendation"]["strategyName"] = new_strategy
                            session["ai_strategy_switches"] = session.get("ai_strategy_switches", 0) + 1
                            _save_trade_sessions()
                        else:
                            logger.info(
                                f"║ DECISION: KEEP {current_strategy or 'current strategy':<42} ║\n"
                                f"║ Reason: {'Low confidence' if not should_switch else 'Same strategy recommended':<51} ║\n"
                                "╚══════════════════════════════════════════════════════════════╝"
                            )
                    else:
                        logger.info(
                            "║ GPT Response: NOT AVAILABLE (check API key/config)          ║\n"
                            f"║ DECISION: KEEP {current_strategy or 'current strategy':<42} ║\n"
                            "╚══════════════════════════════════════════════════════════════╝"
                        )
                except Exception as e:
                    logger.exception("[AI ADVISOR] Error during strategy evaluation: %s", str(e))
        
        # Check dynamic hourly trade frequency
        capital = session.get("virtual_balance") or 100000
        if (session.get("execution_mode") or "PAPER").upper() == "LIVE":
            live_capital, _ = get_balance()
            if live_capital and live_capital > 0:
                capital = live_capital
        
        daily_pnl = session.get("daily_pnl", 0)
        max_trades_this_hour, freq_mode = calculate_max_trades_per_hour(capital, daily_pnl)
        session["frequency_mode"] = freq_mode
        
        trades_this_hour = session.get("hourly_trade_count", 0)
        
        # Block if hourly limit reached
        if trades_this_hour >= max_trades_this_hour:
            logger.info(
                f"[FREQ] Hourly limit reached for {session.get('instrument')} | "
                f"{trades_this_hour}/{max_trades_this_hour} | Mode: {freq_mode}"
            )
            continue
        
        instrument = session.get("instrument", "")
        strategy_id, strategy_name = _pick_best_strategy(instrument, session=session)
        can_enter, entry_price = _check_entry_real(session, strategy_name_override=strategy_name)
        # Entry diagnostics for Manual Mode: always record last check (timestamp, strategy, can_enter, risk result)
        block_reason: str | None = None
        if not can_enter:
            block_reason = "Condition not met"
            logger.info("Entry not met | %s | %s", session.get("instrument", "—"), block_reason)
        elif entry_price is None:
            block_reason = "Entry price None"
        session["last_entry_check"] = {
            "timestamp": now.isoformat(),
            "strategy": strategy_name,
            "can_enter": bool(can_enter),
            "entry_price": entry_price,
            "block_reason": block_reason,
            "risk_approved": None,
            "risk_reason": None,
            "calculated_lots": None,
            "max_trades_this_hour": max_trades_this_hour,
            "trades_this_hour": trades_this_hour,
            "frequency_mode": freq_mode,
        }
        if can_enter and entry_price is not None:
            try:
                # === ENHANCED ORDER PLACEMENT LOGGING ===
                logger.info(
                    "\n"
                    "╔══════════════════════════════════════════════════════════════╗\n"
                    "║ ORDER PLACEMENT CHECK                                        ║\n"
                    "╠══════════════════════════════════════════════════════════════╣"
                )
                logger.info(f"║ Instrument: {session.get('instrument', 'Unknown'):<48} ║")
                logger.info(f"║ Strategy: {strategy_name:<50} ║")
                logger.info(f"║ Entry Signal: YES | Entry Price: ₹{entry_price:<23.2f} ║")
                logger.info("╠══════════════════════════════════════════════════════════════╣")
                
                strategy = get_strategy_for_session(session, strategy_data_provider, strategy_name_override=strategy_name)
                rec = session.get("recommendation") or {}
                symbol = session.get("instrument", "")
                side = "BUY"
                lot_size = int(session.get("lot_size") or rec.get("lotSize") or 1)
                if lot_size <= 0:
                    lot_size = 1
                is_nfo = (session.get("exchange") or "").upper() == "NFO"
                if is_nfo and session.get("tradingsymbol"):
                    from engine.zerodha_client import get_quote as kite_get_quote
                    opt_quote = kite_get_quote(session["tradingsymbol"], exchange="NFO")
                    entry_price = float(opt_quote.get("last", 0) or opt_quote.get("last_price", 0)) or entry_price
                    stop_loss = round(entry_price * 0.995, 2)
                    target = round(entry_price * 1.015, 2)
                    logger.info(f"║ Option Type: F&O ({session.get('tradingsymbol')}){' '*(60-len(session.get('tradingsymbol', '')))} ║")
                else:
                    # Use F&O-aware stop/target for options (wider stops, realistic targets)
                    if strategy:
                        if hasattr(strategy, 'get_stop_loss_fo_aware'):
                            stop_loss = strategy.get_stop_loss_fo_aware(entry_price, session)
                            target = strategy.get_target_fo_aware(entry_price, session)
                        else:
                            stop_loss = strategy.get_stop_loss(entry_price)
                            target = strategy.get_target(entry_price)
                    else:
                        stop_loss = None
                        target = None
                    logger.info(f"║ Instrument Type: Equity/Index{' '*35} ║")
                
                logger.info(f"║ Stop Loss: ₹{stop_loss:<46.2f} ║")
                logger.info(f"║ Target: ₹{target:<49.2f} ║")
                risk_reward = ((target - entry_price) / (entry_price - stop_loss)) if stop_loss and stop_loss < entry_price else 0
                logger.info(f"║ Risk/Reward Ratio: 1:{risk_reward:<36.2f} ║")
                logger.info("╠══════════════════════════════════════════════════════════════╣")
                capital = session.get("virtual_balance")
                execution_mode = (session.get("execution_mode") or "PAPER").upper()
                if execution_mode == "LIVE":
                    capital, _ = get_balance()
                    capital = capital or 0
                if capital is None or capital <= 0:
                    capital = 100000.0
                
                logger.info(f"║ Execution Mode: {execution_mode:<44} ║")
                logger.info(f"║ Capital Available: ₹{capital:<41.2f} ║")
                logger.info("╠══════════════════════════════════════════════════════════════╣")
                
                risk_config = RiskConfig(
                    capital=float(capital),
                    risk_percent_per_trade=float(rec.get("risk_percent_per_trade") or 1.0),
                    max_daily_loss_percent=float(rec.get("max_daily_loss_percent") or 3.0),
                    max_trades=100,  # No longer used - dynamic hourly frequency controls this
                )
                logger.info(f"║ Risk Per Trade: {risk_config.risk_percent_per_trade:.1f}%{' '*40} ║")
                logger.info(f"║ Max Daily Loss: {risk_config.max_daily_loss_percent:.1f}%{' '*40} ║")
                
                risk_mgr = RiskManager(risk_config)
                premium = rec.get("premium")
                if premium is not None:
                    premium = float(premium)
                elif is_nfo:
                    premium = entry_price
                stop_for_risk = stop_loss if stop_loss is not None and stop_loss != entry_price else entry_price * 0.995
                approved, reason, lots = risk_mgr.validate_trade(
                    session, entry_price, stop_for_risk, lot_size, premium=premium
                )
                # Update diagnostics with risk result
                session["last_entry_check"]["risk_approved"] = approved
                session["last_entry_check"]["risk_reason"] = reason
                session["last_entry_check"]["calculated_lots"] = lots
                
                logger.info("╠══════════════════════════════════════════════════════════════╣")
                logger.info(f"║ Risk Check Result: {('APPROVED' if approved else 'REJECTED'):<43} ║")
                if approved:
                    logger.info(f"║ Lot Size: {lot_size:<50} ║")
                    logger.info(f"║ Lots Calculated: {lots:<45} ║")
                    qty = lots * lot_size
                    logger.info(f"║ Total Quantity: {qty:<46} ║")
                    risk_amount = abs(entry_price - stop_for_risk) * qty
                    logger.info(f"║ Risk Amount: ₹{risk_amount:<45.2f} ║")
                    logger.info("╠══════════════════════════════════════════════════════════════╣")
                    logger.info(f"║ ACTION: PLACING ORDER{' '*39} ║")
                    logger.info("╚══════════════════════════════════════════════════════════════╝\n")
                else:
                    logger.info(f"║ Reason: {reason:<52} ║")
                    logger.info("╠══════════════════════════════════════════════════════════════╣")
                    logger.info(f"║ ACTION: ORDER REJECTED{' '*37} ║")
                    logger.info("╚══════════════════════════════════════════════════════════════╝\n")
                    
                if not approved or lots < 1:
                    session["last_entry_check"]["block_reason"] = reason or "Insufficient capital for position"
                    continue
                qty = lots * lot_size
                
                # Log pre-execution state
                logger.info(f"[ORDER EXECUTION] Calling execute_entry for {symbol} | Mode: {execution_mode}")
                
                execute_entry(
                    session, symbol, side, qty,
                    price=entry_price,
                    strategy_name=strategy_name,
                    stop_loss=stop_loss,
                    target=target,
                )
                
                # Log post-execution
                logger.info(
                    f"[ORDER SUCCESS] Trade executed | {symbol} | Qty: {qty} | "
                    f"Entry: ₹{entry_price:.2f} | SL: ₹{stop_loss:.2f} | Target: ₹{target:.2f}"
                )
                
                # Increment hourly trade count after successful entry
                session["hourly_trade_count"] = session.get("hourly_trade_count", 0) + 1
                logger.info(
                    f"[FREQ] Trade executed for {session.get('instrument')} | "
                    f"Hour: {session.get('current_hour_block')} | "
                    f"Count: {session['hourly_trade_count']}/{max_trades_this_hour}"
                )
                _save_trade_sessions()
            except Exception as e:
                logger.exception(f"[ORDER ERROR] Entry execution failed: {str(e)}")
                logger.error(
                    "╔══════════════════════════════════════════════════════════════╗\n"
                    f"║ ERROR DURING ORDER PLACEMENT{' '*32} ║\n"
                    f"║ {str(e)[:59]:<59} ║\n"
                    "╚══════════════════════════════════════════════════════════════╝\n"
                )
                session["last_entry_check"]["block_reason"] = f"Error: {e!s}"
                session["last_entry_check"]["risk_approved"] = False
    engine_state["last_tick"] = now.isoformat()
    _save_trade_sessions()


def _engine_status_for_api() -> dict:
    """Engine fields for API responses (running, last_tick, next_scan)."""
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    next_scan = None
    if _last_session_engine_tick_time:
        elapsed = (now - _last_session_engine_tick_time).total_seconds()
        next_scan = max(0, int(SESSION_ENGINE_INTERVAL_SEC - elapsed))
    last_tick = engine_state.get("last_tick") or (_last_session_engine_tick_time.isoformat() if _last_session_engine_tick_time else None)
    return {
        "engine_running": engine_state.get("running", True),
        "last_tick": last_tick,
        "next_scan": next_scan,
    }


@app.route("/api/trade-sessions")
def api_trade_sessions():
    """GET /api/trade-sessions: list all trade sessions (active and stopped) for UI; includes engine state and current_ltp."""
    sessions_with_ltp = [
        {**s, "current_ltp": (s.get("entry_diagnostics") or {}).get("ltp")}
        for s in _trade_sessions
    ]
    payload = {"sessions": sessions_with_ltp, **_engine_status_for_api()}
    return jsonify(payload)


def _session_status_display(session: dict) -> str:
    """Return WAITING_FOR_ENTRY | IN_TRADE | STOPPED for UI."""
    if session.get("status") != "ACTIVE":
        return "STOPPED"
    return "IN_TRADE" if session.get("current_trade") else "WAITING_FOR_ENTRY"


@app.route("/api/trade-sessions/active")
def api_trade_sessions_active():
    """GET /api/trade-sessions/active: only ACTIVE sessions with full live state for terminal UI."""
    active = [s for s in _trade_sessions if s.get("status") == "ACTIVE"]
    out = []
    for s in active:
        rec = s.get("recommendation") or {}
        strategy_name = rec.get("strategyName") or rec.get("strategy_name")
        if not strategy_name:
            try:
                _, strategy_name = _pick_best_strategy(s.get("instrument") or "")
            except Exception:
                strategy_name = "—"
        # Get frequency status for this session
        freq_status = get_frequency_status(s)
        
        out.append({
            "session_id": s.get("sessionId"),
            "instrument": s.get("instrument"),
            "tradingsymbol": s.get("tradingsymbol"),
            "exchange": s.get("exchange"),
            "execution_mode": s.get("execution_mode"),
            "status": s.get("status"),
            "strategy_name": strategy_name or "—",
            "session_status": _session_status_display(s),
            "trades_taken_today": s.get("trades_taken_today"),
            "daily_pnl": s.get("daily_pnl"),
            "cutoff_time": s.get("cutoff_time"),
            "current_trade": s.get("current_trade"),
            "last_scan": _last_session_engine_tick_time.isoformat() if _last_session_engine_tick_time else None,
            "last_entry_check": s.get("last_entry_check"),
            "entry_diagnostics": s.get("entry_diagnostics"),
            "current_ltp": (s.get("entry_diagnostics") or {}).get("ltp"),
            # Dynamic trade frequency info
            "frequency_mode": freq_status.get("frequency_mode"),
            "max_trades_this_hour": freq_status.get("max_trades_per_hour"),
            "hourly_trade_count": s.get("hourly_trade_count", 0),
            "current_hour_block": s.get("current_hour_block"),
        })
    last_scan = _last_session_engine_tick_time.isoformat() if _last_session_engine_tick_time else None
    payload = {"sessions": out, "last_scan": last_scan, **_engine_status_for_api()}
    return jsonify(payload)


@app.route("/api/trade-sessions/<session_id>/kill", methods=["POST"])
def api_trade_session_kill(session_id: str):
    """POST: close open trade immediately, set session STOPPED, persist. No further trading."""
    global _trade_sessions
    session = next((s for s in _trade_sessions if s.get("sessionId") == session_id), None)
    if not session:
        return jsonify({"ok": False, "error": "Session not found"}), 404
    if session.get("current_trade"):
        try:
            execute_exit(session)
        except Exception:
            pass
    session["status"] = "STOPPED"
    _save_trade_sessions()
    return jsonify({"ok": True})


@app.route("/api/trade-sessions/<session_id>/resume", methods=["POST"])
def api_trade_session_resume(session_id: str):
    """POST: resume a STOPPED session, setting status to ACTIVE. Engine will start monitoring entry/exit again."""
    global _trade_sessions
    session = next((s for s in _trade_sessions if s.get("sessionId") == session_id), None)
    if not session:
        return jsonify({"ok": False, "error": "Session not found"}), 404
    if session.get("status") != "STOPPED":
        return jsonify({"ok": False, "error": "Session is not stopped (current status: {})".format(session.get("status"))}), 400
    # Check if cutoff time has passed
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    cutoff_str = session.get("cutoff_time") or "15:15"
    try:
        cutoff_h, cutoff_m = map(int, cutoff_str.split(":"))
        cutoff = now.replace(hour=cutoff_h, minute=cutoff_m, second=0, microsecond=0)
        if now >= cutoff:
            return jsonify({"ok": False, "error": "Cannot resume: cutoff time ({}) has passed".format(cutoff_str)}), 400
    except Exception:
        pass  # If cutoff parsing fails, allow resume
    session["status"] = "ACTIVE"
    session["resumed_at"] = now.isoformat()
    # Reset session to today if it's from a previous day (otherwise engine will auto-stop it)
    session_date = _session_date(session)
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if session_date is not None and session_date < today:
        session["createdAt"] = now.isoformat()
        session["trades_taken_today"] = 0
        session["daily_pnl"] = 0.0
        logger.info("Session %s resumed - reset to today (was from %s)", session_id, session_date)
    # Reset hourly tracking
    session["current_hour_block"] = now.hour
    session["hourly_trade_count"] = 0
    session["frequency_mode"] = "NORMAL"
    # Clear any stale diagnostics from previous run
    session.pop("entry_diagnostics", None)
    session.pop("last_entry_check", None)
    _save_trade_sessions()
    logger.info("Session %s resumed by user", session_id)
    return jsonify({"ok": True, "session_id": session_id})


@app.route("/api/trade-sessions/<session_id>/delete", methods=["POST"])
def api_trade_session_delete(session_id: str):
    """POST: permanently delete a session. Can only delete STOPPED sessions."""
    global _trade_sessions
    session = next((s for s in _trade_sessions if s.get("sessionId") == session_id), None)
    if not session:
        return jsonify({"ok": False, "error": "Session not found"}), 404
    if session.get("status") != "STOPPED":
        return jsonify({"ok": False, "error": "Can only delete stopped sessions. Stop the session first."}), 400
    if session.get("current_trade"):
        return jsonify({"ok": False, "error": "Session has an open trade. Close it first."}), 400
    # Remove session from list
    _trade_sessions = [s for s in _trade_sessions if s.get("sessionId") != session_id]
    _save_trade_sessions()
    logger.info("Session %s deleted by user", session_id)
    return jsonify({"ok": True, "session_id": session_id})


@app.route("/api/trade-sessions/<session_id>/ai-mode", methods=["POST"])
def api_trade_session_ai_mode(session_id: str):
    """POST: toggle AI strategy selection mode for a session."""
    global _trade_sessions
    data = request.get_json() or {}
    
    session = next((s for s in _trade_sessions if s.get("sessionId") == session_id), None)
    if not session:
        return jsonify({"ok": False, "error": "Session not found"}), 404
    
    ai_enabled = data.get("enabled", True)
    ai_interval = data.get("interval_minutes", 5)  # Default 5 minutes
    
    session["ai_auto_switching_enabled"] = ai_enabled
    session["ai_check_interval_minutes"] = ai_interval
    
    # Reset AI state when toggling
    if ai_enabled:
        session["last_ai_strategy_check"] = None
        session["last_ai_recommendation"] = None
        session["ai_strategy_switches"] = 0
        logger.info(f"[AI MODE] Enabled for session {session_id}, interval: {ai_interval} min")
    else:
        logger.info(f"[AI MODE] Disabled for session {session_id}")
    
    _save_trade_sessions()
    
    return jsonify({
        "ok": True,
        "ai_auto_switching_enabled": ai_enabled,
        "ai_check_interval_minutes": ai_interval,
        "message": f"AI auto-switching {'enabled' if ai_enabled else 'disabled'}"
    })


@app.route("/api/engine/kill", methods=["POST"])
def api_engine_kill():
    """POST: global kill switch — pause engine (engine tick does nothing). Kept for backward compat."""
    engine_state["running"] = False
    return jsonify({"ok": True, "engine_enabled": False, "running": False})


@app.route("/api/engine/start", methods=["POST"])
def api_engine_start():
    """POST: resume engine. Kept for backward compat."""
    engine_state["running"] = True
    return jsonify({"ok": True, "engine_enabled": True, "running": True})


@app.route("/api/engine/pause", methods=["POST"])
def api_engine_pause():
    """POST: pause engine — no LIVE/PAPER entries or management until resumed."""
    engine_state["running"] = False
    return jsonify({"ok": True, "running": False})


@app.route("/api/engine/resume", methods=["POST"])
def api_engine_resume():
    """POST: resume engine — allow LIVE/PAPER trading again."""
    engine_state["running"] = True
    return jsonify({"ok": True, "running": True})


@app.route("/api/engine/status")
def api_engine_status():
    """GET: engine state (running, last_tick, next_scan), market open, active session count (for terminal UI)."""
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    next_scan_sec = None
    if _last_session_engine_tick_time:
        elapsed = (now - _last_session_engine_tick_time).total_seconds()
        next_scan_sec = max(0, int(SESSION_ENGINE_INTERVAL_SEC - elapsed))
    active_count = sum(1 for s in _trade_sessions if s.get("status") == "ACTIVE")
    last_tick = engine_state.get("last_tick") or (_last_session_engine_tick_time.isoformat() if _last_session_engine_tick_time else None)
    return jsonify({
        "running": engine_state.get("running", True),
        "engine_enabled": engine_state.get("running", True),
        "last_tick": last_tick,
        "next_scan_sec": next_scan_sec,
        "next_scan_in_seconds": next_scan_sec,
        "market_open": is_market_open(now),
        "active_session_count": active_count,
        "last_scan": _last_session_engine_tick_time.isoformat() if _last_session_engine_tick_time else None,
    })


@app.route("/api/logs")
def api_get_logs():
    """GET /api/logs?mode=live|paper|backtest&lines=100: Fetch recent logs for specified mode."""
    mode = request.args.get("mode", "all").lower()
    max_lines = int(request.args.get("lines", 200))
    
    # Build log filter instructions
    logs = []
    
    try:
        from datetime import datetime as dt
        from zoneinfo import ZoneInfo as ZI
        
        logs.append({
            "timestamp": dt.now(ZI("Asia/Kolkata")).isoformat(),
            "level": "INFO",
            "message": "Real-time log viewing: Check your terminal/console for detailed logs.",
            "mode": mode
        })
        
        # Add filter instructions
        if mode == "live":
            logs.append({"level": "INFO", "message": "Filter logs with: [LIVE] or ENGINE TICK", "mode": mode})
        elif mode == "paper":
            logs.append({"level": "INFO", "message": "Filter logs with: [PAPER] or ENGINE TICK", "mode": mode})
        elif mode == "backtest":
            logs.append({"level": "INFO", "message": "Filter logs with: [AI BACKTEST]", "mode": mode})
        
        # Add note about AI decision logs
        logs.append({"level": "INFO", "message": "AI Decisions: Look for [AI STRATEGY EVAL] in logs", "mode": mode})
        logs.append({"level": "INFO", "message": "Order Execution: Look for [ORDER PLACEMENT] in logs", "mode": mode})
        logs.append({"level": "INFO", "message": "Trailing Stops: Look for [TRAILING STOP] in logs", "mode": mode})
        
        return jsonify({
            "ok": True,
            "mode": mode,
            "logs": logs,
            "total": len(logs),
            "note": "Logs are printed to console/terminal. Configure file logging in app.py for persistent logs."
        })
    
    except Exception as e:
        logger.exception("Failed to fetch logs")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/quote")
def api_quote():
    """GET /api/quote?symbol=...&exchange=NSE|NFO. Returns LTP for terminal UI (e.g. unrealized PnL)."""
    symbol = (request.args.get("symbol") or "").strip()
    exchange = (request.args.get("exchange") or "NSE").strip().upper()
    if not symbol:
        return jsonify({"error": "Missing symbol", "last": 0.0}), 400
    try:
        from engine.zerodha_client import get_quote as kite_get_quote
        q = kite_get_quote(symbol, exchange=exchange)
        return jsonify({
            "symbol": symbol,
            "exchange": exchange,
            "last": float(q.get("last", 0) or q.get("last_price", 0)),
            "last_price": float(q.get("last", 0) or q.get("last_price", 0)),
            "open": float(q.get("open", 0)),
            "high": float(q.get("high", 0)),
            "low": float(q.get("low", 0)),
        })
    except Exception as e:
        return jsonify({"symbol": symbol, "last": 0.0, "error": str(e)})


@app.route("/api/debug/ltp")
def api_debug_ltp():
    """GET /api/debug/ltp?symbol=XXX&exchange=NSE|NFO. Test price fetch (same path as entry diagnostics)."""
    symbol = (request.args.get("symbol") or "").strip()
    exchange = (request.args.get("exchange") or "NSE").strip().upper()
    if not symbol:
        return jsonify({"symbol": "", "exchange": exchange, "ltp": None, "error": "Missing symbol"})
    err = None
    ltp = None
    try:
        if exchange == "NFO":
            q = strategy_data_provider.get_quote(symbol, exchange="NFO")
            ltp = float(q.get("last", 0) or q.get("last_price", 0)) or None
        else:
            ltp = strategy_data_provider.get_ltp(symbol)
    except Exception as e:
        err = str(e)
        ltp = None
    return jsonify({"symbol": symbol, "exchange": exchange, "ltp": ltp, "error": err})


@app.route("/api/account-balance")
def api_account_balance():
    """GET /api/account-balance?mode=LIVE|PAPER|BACKTEST. Returns balance for that mode."""
    mode = (request.args.get("mode") or "LIVE").upper()
    if mode not in ("LIVE", "PAPER", "BACKTEST"):
        mode = "LIVE"
    balance, resolved_mode = get_balance_for_mode(mode, _trade_sessions)
    return jsonify({"mode": resolved_mode, "balance": round(balance, 2)})


@app.route("/api/trade-history")
def api_trade_history():
    """GET /api/trade-history?mode=LIVE|PAPER|BACKTEST&session_id=... Optional filters."""
    mode = request.args.get("mode")
    session_id = request.args.get("session_id")
    trades = get_stored_trade_history(mode=mode, session_id=session_id)
    return jsonify({"trades": trades})


# --- Backtest (separate from session engine: offline historical replay) ---
@app.route("/api/backtest/run", methods=["POST"])
def api_backtest_run():
    """POST /api/backtest/run: run backtest on historical data. Body: instrument, strategy, from_date, to_date, timeframe, initial_capital, risk_percent_per_trade."""
    from backtest.backtest_engine import run_backtest_engine, save_backtest_result
    data = request.get_json() or {}
    instrument = (data.get("instrument") or "").strip().upper() or "RELIANCE"
    strategy = data.get("strategy") or "Momentum Breakout"
    from_date = data.get("from_date") or (date.today() - timedelta(days=30)).isoformat()
    to_date = data.get("to_date") or date.today().isoformat()
    timeframe = data.get("timeframe") or "5minute"
    initial_capital = float(data.get("initial_capital") or 100000)
    risk_pct = float(data.get("risk_percent_per_trade") or 1.0)
    max_daily_loss = float(data.get("max_daily_loss_percent") or 3.0)
    max_trades = int(data.get("max_trades") or 20)
    try:
        result = run_backtest_engine(
            instrument=instrument,
            strategy_name=strategy,
            from_date=from_date,
            to_date=to_date,
            timeframe=timeframe,
            initial_capital=initial_capital,
            risk_percent_per_trade=risk_pct,
            max_daily_loss_percent=max_daily_loss,
            max_trades=max_trades,
        )
        if result.get("error"):
            return jsonify({"ok": False, "error": result["error"]}), 400
        save_backtest_result(result)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/backtest/results")
def api_backtest_results():
    """GET /api/backtest/results: list all backtest runs (summary + trades)."""
    from backtest.backtest_engine import load_backtest_results
    runs = load_backtest_results()
    return jsonify({"runs": runs})


@app.route("/api/backtest/run-ai", methods=["POST"])
def api_backtest_run_ai():
    """
    POST /api/backtest/run-ai: AI-powered backtest with strategy auto-switching.
    Simulates intraday trading day by day with AI evaluating and switching strategies every N minutes.
    Returns streaming progress updates.
    """
    data = request.get_json() or {}
    
    # Extract parameters
    instrument = (data.get("instrument") or "").strip().upper() or "NIFTY"
    from_date_str = data.get("from_date") or (date.today() - timedelta(days=5)).isoformat()
    to_date_str = data.get("to_date") or date.today().isoformat()
    timeframe = data.get("timeframe") or "5minute"
    initial_capital = float(data.get("initial_capital") or 10000)
    risk_percent = float(data.get("risk_percent_per_trade") or 2.0)
    ai_enabled = data.get("ai_enabled", True)
    ai_check_interval = int(data.get("ai_check_interval_minutes") or 5)
    
    try:
        from datetime import datetime as dt
        from_date = dt.fromisoformat(from_date_str).date()
        to_date = dt.fromisoformat(to_date_str).date()
    except:
        return jsonify({"ok": False, "error": "Invalid date format"}), 400
    
    logger.info(f"[AI BACKTEST] Starting: {instrument} from {from_date} to {to_date}, AI={ai_enabled}")
    
    def generate_progress():
        """Generator function for streaming progress updates"""
        import json
        import threading
        import queue
        
        # Create a queue for thread-safe communication
        progress_queue = queue.Queue()
        result_container = {"result": None, "error": None}
        
        def progress_callback(data):
            """Callback to send progress updates to queue"""
            progress_queue.put(data)
        
        def run_backtest_thread():
            """Run backtest in separate thread"""
            try:
                result = _run_ai_backtest(
                    instrument=instrument,
                    from_date=from_date,
                    to_date=to_date,
                    timeframe=timeframe,
                    initial_capital=initial_capital,
                    risk_percent=risk_percent,
                    ai_enabled=ai_enabled,
                    ai_check_interval=ai_check_interval,
                    progress_callback=progress_callback
                )
                result_container["result"] = result
            except Exception as e:
                logger.exception(f"[AI BACKTEST] Error: {str(e)}")
                result_container["error"] = str(e)
            finally:
                progress_queue.put({"type": "done"})
        
        # Start backtest in background thread
        thread = threading.Thread(target=run_backtest_thread)
        thread.daemon = True
        thread.start()
        
        # Send initial progress
        yield f"data: {json.dumps({'type': 'start', 'message': 'Starting backtest...', 'progress': 0})}\n\n"
        
        # Stream progress updates
        while True:
            try:
                data = progress_queue.get(timeout=1)
                
                if data.get("type") == "done":
                    # Backtest completed
                    if result_container["error"]:
                        yield f"data: {json.dumps({'type': 'error', 'error': result_container['error']})}\n\n"
                    elif result_container["result"]:
                        result = result_container["result"]
                        if result.get("error"):
                            yield f"data: {json.dumps({'type': 'error', 'error': result['error']})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'complete', 'result': result})}\n\n"
                    break
                else:
                    # Send progress update
                    yield f"data: {json.dumps(data)}\n\n"
                    
            except queue.Empty:
                # Send keep-alive ping
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
            except Exception as e:
                logger.exception(f"[AI BACKTEST] Stream error: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                break
    
    return Response(generate_progress(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })


@app.route("/api/backtest/run-ai-sync", methods=["POST"])
def api_backtest_run_ai_sync():
    """
    POST /api/backtest/run-ai-sync: Non-streaming version (returns all at once).
    Use this for simple requests without progress updates.
    """
    data = request.get_json() or {}
    
    # Extract parameters
    instrument = (data.get("instrument") or "").strip().upper() or "NIFTY"
    from_date_str = data.get("from_date") or (date.today() - timedelta(days=5)).isoformat()
    to_date_str = data.get("to_date") or date.today().isoformat()
    timeframe = data.get("timeframe") or "5minute"
    initial_capital = float(data.get("initial_capital") or 10000)
    risk_percent = float(data.get("risk_percent_per_trade") or 2.0)
    ai_enabled = data.get("ai_enabled", True)
    ai_check_interval = int(data.get("ai_check_interval_minutes") or 5)
    
    try:
        from datetime import datetime as dt
        from_date = dt.fromisoformat(from_date_str).date()
        to_date = dt.fromisoformat(to_date_str).date()
    except:
        return jsonify({"ok": False, "error": "Invalid date format"}), 400
    
    logger.info(f"[AI BACKTEST STREAM] Starting: {instrument} from {from_date} to {to_date}, AI={ai_enabled}")
    
    def generate_progress():
        """Generator function to stream results LIVE as each day completes"""
        import json
        
        collected_updates = []
        
        def callback(update):
            """Callback to collect updates"""
            collected_updates.append(update)
        
        try:
            # Run backtest with callback
            result = _run_ai_backtest(
                instrument=instrument,
                from_date=from_date,
                to_date=to_date,
                timeframe=timeframe,
                initial_capital=initial_capital,
                risk_percent=risk_percent,
                ai_enabled=ai_enabled,
                ai_check_interval=ai_check_interval,
                progress_callback=callback,
            )
            
            # Stream all collected updates
            for update in collected_updates:
                yield f"data: {json.dumps(update)}\n\n"
            
            # Send final result
            if result.get("success"):
                yield f"data: {json.dumps({'type': 'complete', 'result': result})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'error': result.get('error', 'Unknown error')})}\n\n"
                
        except Exception as e:
            logger.exception(f"[AI BACKTEST STREAM] Error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return Response(generate_progress(), mimetype='text/event-stream')


def _run_ai_backtest(
    instrument: str,
    from_date: date,
    to_date: date,
    timeframe: str,
    initial_capital: float,
    risk_percent: float,
    ai_enabled: bool,
    ai_check_interval: int,
    progress_callback=None,
) -> dict:
    """
    Run AI-powered backtest simulating intraday trading with strategy auto-switching.
    Uses dynamic trade frequency from Settings → Trade Frequency (same as Paper/Live).
    Max loss limit is auto-calculated from capital and configured loss percent.
    Returns comprehensive report with daily breakdown.
    """
    from engine.trade_frequency import calculate_max_daily_loss_limit
    
    # Calculate max loss limit from capital and settings
    max_loss_limit = calculate_max_daily_loss_limit(initial_capital)
    logger.info(f"[AI BACKTEST] Max loss limit: Rs.{max_loss_limit:.2f} for capital Rs.{initial_capital:.2f}")
    
    import yfinance as yf
    from strategies.strategy_registry import get_strategy_for_session, STRATEGY_MAP
    from strategies import data_provider as strategy_data_provider
    from engine.ai_strategy_advisor import get_market_context, get_ai_strategy_recommendation, should_switch_strategy
    
    # Fetch all historical data at once using yfinance
    try:
        ticker_symbol = instrument
        # Convert Indian symbols to yfinance format
        if instrument in ["NIFTY 50", "NIFTY", "NIFTY50"]:
            ticker_symbol = "^NSEI"
        elif instrument in ["BANKNIFTY", "NIFTY BANK", "BANK NIFTY"]:
            ticker_symbol = "^NSEBANK"
        elif not ticker_symbol.endswith(".NS"):
            ticker_symbol = f"{instrument}.NS"
        
        logger.info(f"[AI BACKTEST] Fetching historical data for {ticker_symbol} from {from_date} to {to_date}")
        
        # Fetch intraday data (5 minute candles)
        interval_map = {"5minute": "5m", "15minute": "15m", "1hour": "1h"}
        yf_interval = interval_map.get(timeframe, "5m")
        
        ticker = yf.Ticker(ticker_symbol)
        all_data = ticker.history(start=from_date, end=to_date + timedelta(days=1), interval=yf_interval)
        
        if all_data.empty:
            return {"success": False, "error": f"No historical data available for {instrument}"}
        
        logger.info(f"[AI BACKTEST] Fetched {len(all_data)} candles")
        
    except Exception as e:
        logger.exception(f"[AI BACKTEST] Failed to fetch historical data: {e}")
        return {"success": False, "error": f"Failed to fetch data: {str(e)}"}
    
    # Results tracking
    all_trades = []
    daily_breakdown = []
    current_capital = initial_capital
    cumulative_pnl = 0
    total_ai_switches = 0
    
    # Calculate total days for progress percentage
    total_days = (to_date - from_date).days + 1
    
    # Iterate through each trading day
    current_date = from_date
    day_count = 0
    
    while current_date <= to_date:
        day_count += 1
        progress_pct = int((day_count / total_days) * 100)
        
        # Store progress for streaming API
        if progress_callback:
            progress_callback({
                "type": "progress",
                "day": day_count,
                "total_days": total_days,
                "progress": progress_pct,
                "date": current_date.isoformat(),
                "capital": current_capital,
                "cumulative_pnl": cumulative_pnl
            })
        
        logger.info(f"[AI BACKTEST] Processing day {day_count}/{total_days}: {current_date} ({progress_pct}%)")
        
        # Filter candles for this specific day
        try:
            day_data = all_data[all_data.index.date == current_date]
            
            if day_data.empty or len(day_data) < 5:
                logger.info(f"[AI BACKTEST] Skipping {current_date}: Insufficient data ({len(day_data)} candles)")
                current_date += timedelta(days=1)
                continue
            
            # Convert to list of dicts for compatibility (use lowercase keys)
            candles = []
            for idx, row in day_data.iterrows():
                candles.append({
                    "timestamp": idx.isoformat(),  # Convert Timestamp to ISO string
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"])
                })
                
        except Exception as e:
            logger.warning(f"[AI BACKTEST] Failed to process data for {current_date}: {e}")
            current_date += timedelta(days=1)
            continue
        
        # Simulate trading for this day (WITH FRESH CAPITAL EACH DAY)
        day_result = _simulate_trading_day(
            instrument=instrument,
            trade_date=current_date,
            candles=candles,
            current_capital=initial_capital,  # RESET TO INITIAL CAPITAL EACH DAY
            risk_percent=risk_percent,
            ai_enabled=ai_enabled,
            ai_check_interval=ai_check_interval,
        )
        
        # Update tracking
        all_trades.extend(day_result["trades"])
        daily_pnl = day_result["daily_pnl"]  # This day's P&L
        cumulative_pnl += daily_pnl  # Track cumulative for reporting
        day_result["daily_summary"]["cumulative_pnl"] = cumulative_pnl
        daily_breakdown.append(day_result["daily_summary"])
        
        # IMPORTANT: Keep current_capital = initial_capital for next day
        # Each day starts fresh with same capital
        current_capital = initial_capital
        
        total_ai_switches += day_result["ai_switches"]
        
        # Send day completion update
        if progress_callback:
            progress_callback({
                "type": "day_complete",
                "date": current_date.isoformat(),
                "trades": len(day_result["trades"]),
                "daily_pnl": daily_pnl,
                "cumulative_pnl": cumulative_pnl,
                "capital": initial_capital,  # Report initial capital (reset each day)
                "strategies": day_result["daily_summary"].get("strategies", []),
                "ai_switches": day_result["ai_switches"]
            })
        
        logger.info(f"[AI BACKTEST] Day {current_date} complete: {len(day_result['trades'])} trades, Daily P&L: ₹{daily_pnl:.2f}, Cumulative: ₹{cumulative_pnl:.2f}")
        
        # Check if THIS DAY exceeded daily loss limit (not cumulative)
        if daily_pnl <= -max_loss_limit:
            logger.warning(f"[AI BACKTEST] Day {current_date}: Daily loss limit exceeded (₹{daily_pnl:.2f} <= -₹{max_loss_limit:.2f}), but continuing to next day with fresh capital")
            # Continue to next day (don't break) - each day is independent
        
        current_date += timedelta(days=1)
    
    # Calculate summary metrics
    wins = sum(1 for t in all_trades if t.get("net_pnl", t.get("pnl", 0)) > 0)
    losses = sum(1 for t in all_trades if t.get("net_pnl", t.get("pnl", 0)) < 0)
    total_trades = len(all_trades)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    # Calculate total charges
    from engine.brokerage_calculator import get_charges_summary
    charges_summary = get_charges_summary(all_trades)
    total_charges = charges_summary.get("total_charges", 0)
    
    # Calculate gross vs net P&L
    gross_pnl = sum(t.get("pnl", 0) for t in all_trades)
    net_pnl_calculated = sum(t.get("net_pnl", t.get("pnl", 0)) for t in all_trades)
    
    # Best and worst days (use net P&L)
    day_pnls = [d["pnl"] for d in daily_breakdown]
    best_day_pnl = max(day_pnls) if day_pnls else 0
    worst_day_pnl = min(day_pnls) if day_pnls else 0
    
    # Return comprehensive report
    return {
        "success": True,
        "instrument": instrument,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "initial_capital": initial_capital,
        "ending_capital": current_capital,
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl_calculated,
        "total_charges": total_charges,
        "charges_breakdown": charges_summary,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "best_day_pnl": best_day_pnl,
        "worst_day_pnl": worst_day_pnl,
        "ai_enabled": ai_enabled,
        "ai_switches": total_ai_switches,
        "trades": all_trades,
        "daily_breakdown": daily_breakdown,
        "summary": {
            "total_trades": total_trades,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": win_rate,
            "gross_pnl": gross_pnl,
            "total_charges": total_charges,
            "net_pnl": net_pnl_calculated,
            "ending_capital": current_capital,
            "return_pct": ((current_capital - initial_capital) / initial_capital * 100) if initial_capital > 0 else 0,
        },
        "daily_results": [{"daily_summary": d} for d in daily_breakdown],
    }


def _simulate_trading_day(
    instrument: str,
    trade_date: date,
    candles: list[dict],
    current_capital: float,
    risk_percent: float,
    ai_enabled: bool,
    ai_check_interval: int,
) -> dict:
    """
    Simulate a single trading day with F&O options (just like live/paper trading).
    - Calls GPT to analyze market and recommend F&O option
    - Trades the recommended option for the day
    - Uses dynamic hourly frequency from Settings
    - Same logic as Paper/Live for consistency
    Returns day summary with trades and P&L.
    """
    from strategies.strategy_registry import get_strategy_for_session, STRATEGY_MAP
    from strategies import data_provider as strategy_data_provider
    from engine.trade_frequency import calculate_max_trades_per_hour, get_trade_frequency_config
    from engine.position_sizing import calculate_fo_position_size
    from engine.brokerage_calculator import calculate_fo_charges, calculate_net_pnl
    
    # F&O options approach - use GPT recommendation for daily option selection
    # This allows us to trade F&O options (same as Live/Paper)
    is_index = instrument.upper() in ["NIFTY", "NIFTY 50", "NIFTY50", "BANKNIFTY", "BANK NIFTY", "NIFTY BANK"]
    
    # Default values (will be set by F&O logic below)
    simulate_as_option = False
    lot_size = 1
    
    logger.info(f"[AI BACKTEST] Simulating {instrument} with REAL strategy logic and F&O options")
    
    # === STEP 1: Get GPT F&O Recommendation for the day (just like live/paper) ===
    logger.info(f"[AI BACKTEST F&O] {trade_date}: Getting GPT recommendation for index options...")
    
    # Determine if NIFTY or BANKNIFTY
    index_name = "NIFTY"
    if "BANK" in instrument.upper():
        index_name = "BANKNIFTY"
    
    # Get market bias using historical data (first few candles of the day)
    try:
        # Get first 15 candles for market context (better sample)
        opening_sample = min(15, len(candles))
        opening_candles = candles[:opening_sample]
        
        # Improved bias detection: Look at overall trend + volatility
        open_price = candles[0]["open"]
        current_price = candles[opening_sample-1]["close"]
        price_trend = ((current_price - open_price) / open_price) * 100
        
        # Calculate volatility (price range in opening)
        high_prices = [c["high"] for c in opening_candles]
        low_prices = [c["low"] for c in opening_candles]
        volatility = ((max(high_prices) - min(low_prices)) / open_price) * 100
        
        # More aggressive bias detection (trade even on slight bias)
        # Lower threshold to 0.15% so we don't skip days
        if price_trend > 0.15:
            bias = "BULLISH"
        elif price_trend < -0.15:
            bias = "BEARISH"
        else:
            # Instead of skipping NEUTRAL days, pick direction based on volatility
            # If volatile, trade based on last few candles momentum
            recent_momentum = ((candles[opening_sample-1]["close"] - candles[max(0, opening_sample-5)]["close"]) / 
                             candles[max(0, opening_sample-5)]["close"]) * 100
            bias = "BULLISH" if recent_momentum > 0 else "BEARISH"
        
        logger.info(f"[AI BACKTEST F&O] {trade_date}: Market bias = {bias} (trend: {price_trend:.2f}%, vol: {volatility:.2f}%)")
        
        # === STEP 2: Select F&O option based on bias and capital ===
        spot_price = candles[0]["open"]
        
        # Determine lot size
        if index_name == "BANKNIFTY":
            lot_size = 15
            strike_step = 100
        else:  # NIFTY
            lot_size = 25
            strike_step = 50
        
        # Select option type based on bias
        option_type = "CE" if bias == "BULLISH" else "PE"
        
        # Calculate ATM strike
        atm_strike = round(spot_price / strike_step) * strike_step
        
        # Select slightly OTM strike for better risk/reward
        if option_type == "CE":
            selected_strike = atm_strike + strike_step  # 1 strike OTM
        else:
            selected_strike = atm_strike - strike_step  # 1 strike OTM
        
        # Base premium estimation (realistic values)
        base_premium = 120 if index_name == "NIFTY" else 150
        premium_per_contract = base_premium
        
        # Calculate max lots we can afford
        from engine.position_sizing import calculate_fo_position_size
        max_lots, total_cost, can_afford = calculate_fo_position_size(
            capital=current_capital,
            premium=premium_per_contract,
            lot_size=lot_size
        )
        
        if not can_afford or max_lots < 1:
            logger.info(f"[AI BACKTEST F&O] {trade_date}: Insufficient capital for {index_name} options. Skipping day.")
            return {
                "trades": [],
                "daily_pnl": 0,
                "ending_capital": current_capital,
                "ai_switches": 0,
                "frequency_mode": "NORMAL",
                "hourly_breakdown": {},
                "daily_summary": {
                    "date": trade_date.isoformat(),
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "pnl": 0,
                    "cumulative_pnl": 0,
                    "strategies": [],
                    "ai_switches": 0,
                    "frequency_mode": "NORMAL",
                }
            }
        
        logger.info(f"[AI BACKTEST F&O] {trade_date}: Trading {index_name} {selected_strike} {option_type}")
        logger.info(f"[AI BACKTEST] Capital: Rs.{current_capital:.0f}, Premium: Rs.{premium_per_contract:.2f}, "
                   f"Lot size: {lot_size}, Max lots: {max_lots}, Total cost: Rs.{total_cost:.2f}")
        
        # Trade F&O options
        simulate_as_option = True
        
    except Exception as e:
        logger.exception(f"[AI BACKTEST F&O] {trade_date}: Failed to get F&O recommendation: {e}")
        # Skip day if can't get recommendation
        return {
            "trades": [],
            "daily_pnl": 0,
            "ending_capital": current_capital,
            "ai_switches": 0,
            "strategies_used": [],
            "frequency_mode": "NORMAL",
            "hourly_breakdown": {},
            "daily_summary": {
                "date": trade_date.isoformat(),
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "pnl": 0,
                "cumulative_pnl": 0,
                "strategies": [],
                "frequency_mode": "NORMAL",
                "hourly_breakdown": {},
                "total_trades_attempted": 0,
                "ai_switches": 0,
            },
        }
    
    # Day tracking
    day_trades = []
    day_pnl = 0
    current_position = None
    strategies_used = set()
    ai_switches_today = 0
    current_strategy_name = "Momentum Breakout"  # Default starting strategy
    
    # Track last AI check time
    last_ai_check_idx = 0
    
    # Dynamic frequency tracking
    hourly_trade_counts = {}  # hour -> trade_count
    frequency_mode = "NORMAL"
    
    # Log candle data for debugging
    logger.info(f"[AI BACKTEST] Day {trade_date}: Starting with {len(candles)} candles")
    if len(candles) < 5:
        logger.warning(f"[AI BACKTEST] Day {trade_date}: Insufficient candles ({len(candles)}), skipping day")
        return {
            "trades": [],
            "daily_pnl": 0,
            "ending_capital": current_capital,
            "ai_switches": 0,
            "strategies_used": [],
            "frequency_mode": "NORMAL",
            "hourly_breakdown": {},
            "daily_summary": {
                "date": trade_date.isoformat(),
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "pnl": 0,
                "cumulative_pnl": 0,
                "strategies": [],
                "frequency_mode": "NORMAL",
                "hourly_breakdown": {},
                "total_trades_attempted": 0,
                "ai_switches": 0,
            },
        }
    
    candles_processed = 0
    candles_skipped_hours = 0
    entry_checks = 0
    entries_triggered = 0
    
    # Simulate each candle (5-minute intervals)
    for idx, candle in enumerate(candles):
        candle_time = candle.get("timestamp") or candle.get("date")
        ltp = candle.get("close")
        
        # Skip if outside market hours (9:15 - 15:15)
        current_hour = 9  # Default
        if candle_time:
            try:
                candle_dt = datetime.fromisoformat(str(candle_time))
                candle_time_obj = candle_dt.time()
                current_hour = candle_dt.hour
                if candle_time_obj < time(9, 15) or candle_time_obj > time(15, 15):
                    candles_skipped_hours += 1
                    continue
            except:
                pass
        
        candles_processed += 1
        
        # Initialize hourly counter
        if current_hour not in hourly_trade_counts:
            hourly_trade_counts[current_hour] = 0
        
        # AI strategy evaluation (every N candles) - CHECK MORE FREQUENTLY
        candles_since_check = idx - last_ai_check_idx
        # Check every 6 candles (30 min for 5min candles) OR every 12 candles if we have a position
        check_interval = 12 if current_position else 6  # More frequent when no position
        
        if candles_since_check >= check_interval:
            # Try AI first if enabled
            if ai_enabled:
                # Get market context for REAL AI
                recent_candles = candles[max(0, idx-20):idx+1]
                
                try:
                    # Build market context FOR AI (needs proper format)
                    # AI expects: nifty, banknifty, vix, timestamp
                    context = {
                        "instrument": instrument,
                        "current_price": ltp,
                        "timestamp": str(candle_time),
                        "nifty": {
                            "price": ltp if is_index else candles[0].get("close", ltp),  # Use first candle as reference
                            "change_pct": 0.0  # Not available in backtest
                        },
                        "banknifty": {
                            "price": 0.0,  # Not available in backtest
                            "change_pct": 0.0
                        },
                        "vix": 15.0,  # Assume moderate volatility
                        "recent_candles": recent_candles[-10:],  # Last 10 candles
                    }
                    
                    # Call REAL GPT API for strategy recommendation
                    ai_recommendation = get_ai_strategy_recommendation(context, current_strategy_name)
                    
                    if not ai_recommendation:
                        logger.info(f"[AI BACKTEST] GPT not available or returned no recommendation - keeping {current_strategy_name}")
                    
                    if ai_recommendation:
                        # Use GPT's recommendation with confidence threshold
                        should_switch, new_strategy = should_switch_strategy(
                            ai_recommendation,
                            current_strategy_name,
                            min_confidence="medium"  # Only switch if GPT is confident
                        )
                        
                        if should_switch and new_strategy:
                            current_strategy_name = new_strategy
                            ai_switches_today += 1
                            confidence = ai_recommendation.get("confidence", "")
                            reasoning = ai_recommendation.get("reasoning", "")
                            logger.info(f"[AI BACKTEST] {trade_date} {candle_time}: GPT switched to {new_strategy} (confidence: {confidence})")
                            logger.info(f"[AI BACKTEST] GPT reasoning: {reasoning[:100]}...")
                            
                except Exception as e:
                    logger.warning(f"[AI BACKTEST] GPT strategy check failed: {e}")
            else:
                # AI disabled - rotate strategies manually for diversity
                strategies_list = ["Momentum Breakout", "RSI Reversal Fade", "Pullback Continuation"]
                current_idx = strategies_list.index(current_strategy_name) if current_strategy_name in strategies_list else 0
                next_idx = (current_idx + 1) % len(strategies_list)
                new_strategy = strategies_list[next_idx]
                if new_strategy != current_strategy_name:
                    current_strategy_name = new_strategy
                    ai_switches_today += 1
                    logger.info(f"[AI BACKTEST] {trade_date} {candle_time}: Rotated to {new_strategy} (AI disabled - auto-rotation)")
            
            last_ai_check_idx = idx
        
        strategies_used.add(current_strategy_name)
        
        # Check if we have open position - manage exit (with F&O premium calculation)
        if current_position:
            # For F&O options, calculate current premium based on underlying movement
            if current_position.get("is_option"):
                underlying_move = ltp - current_position["index_price_at_entry"]
                delta_effect = 0.5 if option_type == "CE" else -0.5
                premium_change = underlying_move * abs(delta_effect)
                option_ltp = current_position["entry_price"] + premium_change
                option_ltp = max(10, option_ltp)  # Floor at Rs.10
                exit_price_check = option_ltp
            else:
                exit_price_check = ltp
            
            # Check stop loss (simple price comparison)
            if exit_price_check <= current_position["stop_loss"]:
                exit_pnl = (current_position["stop_loss"] - current_position["entry_price"]) * current_position["qty"]
                
                # Calculate brokerage & taxes
                from engine.brokerage_calculator import calculate_fo_charges, calculate_net_pnl
                charges = calculate_fo_charges(
                    entry_price=current_position["entry_price"],
                    exit_price=current_position["stop_loss"],
                    qty=current_position["qty"],
                    lot_size=current_position.get("lot_size", 50)
                )
                net_pnl = calculate_net_pnl(exit_pnl, charges)
                
                day_trades.append({
                    "date": trade_date.isoformat(),
                    "strategy": current_position["strategy"],
                    "entry_time": str(current_position["entry_time"]),
                    "exit_time": str(candle_time),
                    "entry_price": current_position["entry_price"],
                    "exit_price": current_position["stop_loss"],
                    "qty": current_position["qty"],
                    "pnl": exit_pnl,
                    "charges": charges,
                    "net_pnl": net_pnl,
                    "exit_reason": "STOP_LOSS",
                    "capital_used": current_position.get("capital_used", 0),
                    "capital_remaining": current_position.get("capital_remaining", 0),
                    "lots": current_position.get("lots", 1),
                    "price_per_lot": current_position.get("price_per_lot", 0)
                })
                day_pnl += net_pnl  # Use NET P&L for capital tracking
                logger.info(f"[AI BACKTEST] {trade_date} {candle_time}: EXIT STOP_LOSS @ Rs.{current_position['stop_loss']:.2f} | Gross P&L: Rs.{exit_pnl:.2f} | Charges: Rs.{charges['total_charges']:.2f} | Net P&L: Rs.{net_pnl:.2f}")
                current_position = None
                continue
            
            # Check target (simple price comparison)
            if exit_price_check >= current_position["target"]:
                exit_pnl = (current_position["target"] - current_position["entry_price"]) * current_position["qty"]
                
                # Calculate brokerage & taxes
                from engine.brokerage_calculator import calculate_fo_charges, calculate_net_pnl
                charges = calculate_fo_charges(
                    entry_price=current_position["entry_price"],
                    exit_price=current_position["target"],
                    qty=current_position["qty"],
                    lot_size=current_position.get("lot_size", 50)
                )
                net_pnl = calculate_net_pnl(exit_pnl, charges)
                
                day_trades.append({
                    "date": trade_date.isoformat(),
                    "strategy": current_position["strategy"],
                    "entry_time": str(current_position["entry_time"]),
                    "exit_time": str(candle_time),
                    "entry_price": current_position["entry_price"],
                    "exit_price": current_position["target"],
                    "qty": current_position["qty"],
                    "pnl": exit_pnl,
                    "charges": charges,
                    "net_pnl": net_pnl,
                    "exit_reason": "TARGET",
                    "capital_used": current_position.get("capital_used", 0),
                    "capital_remaining": current_position.get("capital_remaining", 0),
                    "lots": current_position.get("lots", 1),
                    "price_per_lot": current_position.get("price_per_lot", 0)
                })
                day_pnl += net_pnl  # Use NET P&L for capital tracking
                logger.info(f"[AI BACKTEST] {trade_date} {candle_time}: EXIT TARGET @ Rs.{current_position['target']:.2f} | Gross P&L: Rs.{exit_pnl:.2f} | Charges: Rs.{charges['total_charges']:.2f} | Net P&L: Rs.{net_pnl:.2f}")
                current_position = None
                continue
        
        # Entry logic - check dynamic hourly frequency
        if not current_position:
            entry_checks += 1
            
            # Calculate dynamic trades per hour based on capital and drawdown
            max_trades_this_hour, freq_mode = calculate_max_trades_per_hour(
                capital=current_capital + day_pnl,
                daily_pnl=day_pnl
            )
            frequency_mode = freq_mode
            
            # Check if frequency limiting is disabled in backtest (from Settings)
            freq_config = get_trade_frequency_config()
            backtest_disable_limit = freq_config.get("backtest_disable_frequency_limit", False)
            
            trades_this_hour = hourly_trade_counts.get(current_hour, 0)
            
            # Block if hourly limit reached (unless disabled for backtest)
            if not backtest_disable_limit and trades_this_hour >= max_trades_this_hour:
                logger.info(f"[AI BACKTEST] {trade_date} {candle_time}: Hourly limit reached ({trades_this_hour}/{max_trades_this_hour}) Mode: {freq_mode}")
                continue
            
            # Entry logic - USE UNIFIED FUNCTION (same as Live/Paper)
            should_enter = False
            entry_price = ltp
            entry_reason = ""
            
            # Use shared entry logic
            from engine.unified_entry import should_enter_trade
            
            should_enter, entry_reason = should_enter_trade(
                mode="BACKTEST",
                current_price=ltp,
                recent_candles=candles[max(0, idx-10):idx+1],  # Last 10 candles
                strategy_name=current_strategy_name,
                frequency_check_passed=True,  # Already checked above
                instrument=instrument,  # Pass instrument for AI context
                use_ai=ai_enabled,  # Use AI validation if enabled
            )
            
            if should_enter:
                # Load REAL strategy to get stop loss and target (same as Live/Paper)
                mock_session = {
                    "instrument": instrument,
                    "recommendation": {"strategyName": current_strategy_name},
                    "execution_mode": "BACKTEST",
                }
                
                try:
                    class MockDataProvider:
                        def get_recent_candles(self, *args, **kwargs):
                            return []
                        def get_ltp(self, *args, **kwargs):
                            return entry_price
                    
                    strategy = get_strategy_for_session(mock_session, MockDataProvider(), current_strategy_name)
                    
                    # For F&O options, calculate premium and use option-specific sizing
                    if simulate_as_option:
                        from engine.position_sizing import calculate_fo_position_size
                        
                        # Calculate current option premium based on underlying movement
                        underlying_move_from_spot = ltp - spot_price
                        delta_effect = 0.5 if option_type == "CE" else -0.5
                        premium_change = underlying_move_from_spot * abs(delta_effect)
                        option_premium = premium_per_contract + premium_change
                        option_premium = max(50, option_premium)  # Floor at Rs.50
                        
                        # Use centralized F&O position sizing (NO CAP - use full 80%)
                        lots, position_cost, can_afford = calculate_fo_position_size(
                            capital=current_capital,
                            premium=option_premium,
                            lot_size=lot_size
                        )
                        # REMOVED CAP: Use maximum affordable lots (80% of capital)
                        # lots = min(max_lots, lots)  # OLD: Artificial cap removed
                        
                        if not can_afford or lots < 1:
                            logger.debug(f"[AI BACKTEST] Cannot afford trade: Premium={option_premium:.2f}, Lots={lots}")
                            continue
                        
                        qty = lots * lot_size
                        entry_price = option_premium
                        
                        logger.info(f"[AI BACKTEST POSITION] Premium: Rs.{option_premium:.2f}, Affordable lots: {lots}, Total capital used: Rs.{position_cost:.2f} ({position_cost/current_capital*100:.1f}%)")
                        
                        # F&O-specific stop/target - RISK:REWARD = 1:1.5
                        # TIGHT STOP, BIGGER TARGET for profitable trades
                        stop_loss = option_premium * 0.92  # 8% stop (cut losses fast)
                        target = option_premium * 1.12  # 12% target (let winners run)
                        
                        logger.info(f"[AI BACKTEST F&O] {index_name} {selected_strike} {option_type}: "
                                  f"Premium={option_premium:.2f}, Lots={lots}, Qty={qty}, "
                                  f"Target=Rs.{target:.2f} (15% - quick exit for volume)")
                    else:
                        # Regular stock/index (fallback)
                        if strategy:
                            stop_loss = strategy.get_stop_loss(entry_price)
                            target = strategy.get_target(entry_price)
                        else:
                            stop_loss = entry_price * 0.985
                            target = entry_price * 1.03
                        
                        # Calculate position sizing
                        risk_amount = current_capital * risk_percent / 100
                        risk_per_share = abs(entry_price - stop_loss)
                        
                        if risk_per_share > 0:
                            qty_float = risk_amount / risk_per_share
                            qty = max(1, int(qty_float))
                        else:
                            qty = max(1, int(risk_amount / entry_price))
                        
                        logger.info(f"[AI BACKTEST] Position Sizing: Qty={qty}, Entry={entry_price:.2f}, SL={stop_loss:.2f}")
                    
                except Exception as e:
                    logger.warning(f"[AI BACKTEST] Failed to calculate position: {e}")
                    continue
                
                entries_triggered += 1
                
                if qty > 0:
                    # Calculate capital usage for this trade
                    capital_used = entry_price * qty
                    capital_remaining = current_capital - capital_used
                    lots_used = qty // lot_size if lot_size > 1 else 1
                    price_per_lot = entry_price * lot_size  # Cost of 1 lot
                    
                    current_position = {
                        "strategy": current_strategy_name,
                        "entry_time": candle_time,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "target": target,
                        "qty": qty,
                        "is_option": simulate_as_option,
                        "lot_size": lot_size,
                        "index_price_at_entry": ltp if simulate_as_option else None,
                        "capital_used": capital_used,
                        "capital_remaining": capital_remaining,
                        "lots": lots_used,
                        "price_per_lot": price_per_lot,
                    }
                    strategies_used.add(current_strategy_name)
                    
                    # Increment hourly counter
                    hourly_trade_counts[current_hour] = hourly_trade_counts.get(current_hour, 0) + 1
                    
                    logger.info(f"[AI BACKTEST] {trade_date} {candle_time}: ENTRY {current_strategy_name} @Rs.{entry_price:.2f} × {qty} (Lots:{lots_used} @ Rs.{price_per_lot:.2f}/lot) | SL:Rs.{stop_loss:.2f} Target:Rs.{target:.2f}")
                    logger.info(f"[AI BACKTEST] Capital Used: Rs.{capital_used:.2f} ({capital_used/current_capital*100:.1f}%) | Remaining: Rs.{capital_remaining:.2f} | {entry_reason}")
                else:
                    logger.warning(f"[AI BACKTEST] {trade_date} {candle_time}: Entry signal but qty=0")
    
    # Close any open position at end of day
    if current_position:
        # Calculate exit price based on position type
        if current_position.get("is_option"):
            # For F&O options, calculate final premium based on underlying movement
            underlying_move = candles[-1]["close"] - current_position["index_price_at_entry"]
            delta_effect = 0.5 if option_type == "CE" else -0.5
            premium_change = underlying_move * abs(delta_effect)
            exit_price = current_position["entry_price"] + premium_change
            exit_price = max(10, exit_price)  # Floor at Rs.10
            
            logger.info(f"[AI BACKTEST F&O] EOD: Index moved from {current_position['index_price_at_entry']:.2f} to {candles[-1]['close']:.2f}, "
                       f"Option premium: {current_position['entry_price']:.2f} → {exit_price:.2f}")
        else:
            exit_price = candles[-1]["close"]
        
        exit_pnl = (exit_price - current_position["entry_price"]) * current_position["qty"]
        
        # Calculate brokerage & taxes
        from engine.brokerage_calculator import calculate_fo_charges, calculate_net_pnl
        charges = calculate_fo_charges(
            entry_price=current_position["entry_price"],
            exit_price=exit_price,
            qty=current_position["qty"],
            lot_size=current_position.get("lot_size", 50)
        )
        net_pnl = calculate_net_pnl(exit_pnl, charges)
        
        day_trades.append({
            "date": trade_date.isoformat(),
            "strategy": current_position["strategy"],
            "entry_time": str(current_position["entry_time"]),
            "exit_time": str(candles[-1].get("timestamp", "")),
            "entry_price": current_position["entry_price"],
            "exit_price": exit_price,
            "qty": current_position["qty"],
            "pnl": exit_pnl,
            "charges": charges,
            "net_pnl": net_pnl,
            "exit_reason": "DAY_END",
            "capital_used": current_position.get("capital_used", 0),
            "capital_remaining": current_position.get("capital_remaining", 0),
            "lots": current_position.get("lots", 1),
            "price_per_lot": current_position.get("price_per_lot", 0)
        })
        day_pnl += net_pnl  # Use NET P&L for capital tracking
        logger.info(f"[AI BACKTEST] {trade_date} EOD: Closed position @ Rs.{exit_price:.2f} | Gross P&L: Rs.{exit_pnl:.2f} | Charges: Rs.{charges['total_charges']:.2f} | Net P&L: Rs.{net_pnl:.2f}")
        current_position = None
    
    # Log day statistics for debugging
    logger.info(f"[AI BACKTEST] Day {trade_date} Stats: Candles processed={candles_processed}, "
                f"Skipped (hours)={candles_skipped_hours}, Entry checks={entry_checks}, "
                f"Trades executed={len(day_trades)}, AI Switches={ai_switches_today}")
    
    # Day summary
    wins = sum(1 for t in day_trades if t["pnl"] > 0)
    losses = sum(1 for t in day_trades if t["pnl"] <= 0)
    total_trades_all_hours = sum(hourly_trade_counts.values())
    
    return {
        "trades": day_trades,
        "daily_pnl": day_pnl,
        "ending_capital": current_capital + day_pnl,
        "ai_switches": ai_switches_today,
        "frequency_mode": frequency_mode,
        "hourly_breakdown": dict(hourly_trade_counts),
        "daily_summary": {
            "date": trade_date.isoformat(),
            "trades": len(day_trades),
            "wins": wins,
            "losses": losses,
            "pnl": day_pnl,
            "cumulative_pnl": 0,  # Will be filled by caller
            "strategies": list(strategies_used),
            "ai_switches": ai_switches_today,
            "frequency_mode": frequency_mode,
            "total_trades_attempted": total_trades_all_hours,
        }
    }


@app.route("/api/settings/trade-frequency")
def api_get_trade_frequency():
    """GET /api/settings/trade-frequency: Get trade frequency configuration."""
    try:
        config = get_trade_frequency_config()
        return jsonify({"ok": True, "config": config})
    except Exception as e:
        logger.exception("Failed to get trade frequency config")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/settings/trade-frequency", methods=["POST"])
def api_save_trade_frequency():
    """POST /api/settings/trade-frequency: Save trade frequency configuration."""
    try:
        data = request.get_json() or {}
        config = data.get("config")
        
        if not config:
            return jsonify({"ok": False, "error": "No config provided"}), 400
        
        success = save_trade_frequency_config(config)
        
        if success:
            return jsonify({"ok": True, "message": "Trade frequency config saved"})
        else:
            return jsonify({"ok": False, "error": "Validation failed"}), 400
            
    except Exception as e:
        logger.exception("Failed to save trade frequency config")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/index-bias")
def api_index_bias():
    """GET /api/index-bias: NIFTY and BANKNIFTY bias, confidence, reasons."""
    try:
        data = get_index_market_bias()
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "niftyBias": "NEUTRAL",
            "bankNiftyBias": "NEUTRAL",
            "confidence": 0,
            "reasons": [f"Error: {str(e)}"],
        })


@app.route("/api/index-options/<index_name>")
def api_index_options(index_name: str):
    """GET /api/index-options/{index}: options + AI recommendation. Query: max_risk (= total capital for budget check; total_cost = premium * lot_size must be <= max_risk)."""
    max_risk = request.args.get("max_risk", type=float)
    if max_risk is None or max_risk <= 0:
        max_risk = 5000.0  # default budget (total capital) for small capital
    bias_data = get_index_market_bias()
    nifty_bias = bias_data.get("niftyBias", "NEUTRAL")
    bank_nifty_bias = bias_data.get("bankNiftyBias", "NEUTRAL")
    index_upper = (index_name or "").upper().replace(" ", "")
    if "BANK" in index_upper:
        bias = bank_nifty_bias
        label = "BANKNIFTY"
    else:
        bias = nifty_bias
        label = "NIFTY"
    options, ai_rec, safe = get_affordable_index_options(
        label, bias, max_risk, confidence=bias_data.get("confidence")
    )
    return jsonify({
        "index": label,
        "bias": bias,
        "aiRecommendation": ai_rec,
        "options": options,
        "safeToShow": safe,
    })


def _mock_option_chain(stock: str) -> tuple[list, dict, dict]:
    """Return (options list, aiRecommendation, prediction_dict) for a stock. Uses quote for ATM; mock CE/PE around it."""
    fallback_pred = {
        "prediction": "NEUTRAL", "score": 0.0, "rsi": None, "sentiment_score": 0, "vix_high": False,
    }
    try:
        quote = fetch_nse_quote(stock)
        spot = float(quote.get("last") or quote.get("close") or 0)
        if spot <= 0:
            spot = 500.0  # fallback
        step = 50 if spot < 2000 else 100
        base = round(spot / step) * step
        pred = _get_market_prediction(stock)
        direction = "CE" if (pred.get("prediction") or "").upper() == "BULLISH" else "PE"
        confidence = pred.get("confidence", 50) or 50
        factors = pred.get("factors", [])
        reason = " ".join(factors[:3]) if factors else "Trend + Volume + Sentiment"
        options = []
        for i in range(-2, 3):
            strike = base + i * step
            for typ in ["CE", "PE"]:
                if typ == "CE":
                    prem = max(5, 30 - (strike - spot) / 10 + (20 if i == 0 else 0))
                else:
                    prem = max(5, 30 + (strike - spot) / 10 + (20 if i == 0 else 0))
                prem = round(prem, 2)
                lot = 250 if spot < 3000 else (500 if spot < 8000 else 25)
                iv = 18 if abs(i) <= 1 else (22 if abs(i) == 2 else 25)
                options.append({"type": typ, "strike": strike, "premium": prem, "lotSize": lot, "iv": iv})
        rec = {
            "direction": direction,
            "strikePreference": "ATM",
            "confidence": confidence,
            "holdingTime": "30-90 min",
            "reason": reason[:120] + ("..." if len(reason) > 120 else ""),
        }
        return options, rec, pred
    except Exception:
        spot = 500.0
        base = 500
        return [
            {"type": "CE", "strike": base, "premium": 28, "lotSize": 250, "iv": 18},
            {"type": "PE", "strike": base, "premium": 30, "lotSize": 250, "iv": 18},
        ], {"direction": "CE", "strikePreference": "ATM", "confidence": 60, "holdingTime": "30-90 min", "reason": "Trend + Volume"}, fallback_pred


@app.route("/api/algos")
def api_algos_list():
    """GET /api/algos: list all algos (id, name, marketType, riskLevel, description)."""
    algos = load_algos()
    return jsonify([{
        "id": a.get("id"),
        "name": a.get("name"),
        "marketType": a.get("marketType"),
        "riskLevel": a.get("riskLevel"),
        "goodFor": a.get("goodFor", []),
        "description": a.get("description", "")[:200],
        "bestUseCase": a.get("bestUseCase"),
    } for a in algos])


@app.route("/api/algos/<algo_id>")
def api_algo_detail(algo_id: str):
    """GET /api/algos/<id>: full algo detail for detail page."""
    algo = get_algo_by_id(algo_id)
    if not algo:
        return jsonify({"error": "Not found"}), 404
    return jsonify(algo)


@app.route("/api/strategy-groups")
def api_strategy_groups():
    """GET /api/strategy-groups: groups with algo counts for Strategy Library (intraday only)."""
    groups_meta = sorted(load_strategy_groups(), key=lambda g: g.get("order", 99))
    grouped = get_algos_grouped()
    return jsonify([
        {"id": g["id"], "name": g["name"], "description": g.get("description"), "icon": g.get("icon"), "color": g.get("color"), "order": g.get("order"), "count": len(grouped.get(g["id"], []))}
        for g in groups_meta
        if grouped.get(g["id"], [])
    ])


@app.route("/api/options/<stock>")
def api_options(stock: str):
    """GET /api/options/{stock}: option chain + AI recommendation + suggested algos for budget filtering."""
    try:
        options, ai_recommendation, pred = _mock_option_chain(stock.upper())
        stock_indicators = {
            "score": pred.get("score"),
            "prediction": pred.get("prediction"),
            "rsi": pred.get("rsi"),
            "sentiment_score": pred.get("sentiment_score"),
        }
        market_indicators = {"vix_high": pred.get("vix_high", False)}
        suggested_ids = get_suggested_algos(stock_indicators, market_indicators, top_n=3)
        selected_algo = get_algo_by_id(suggested_ids[0]) if suggested_ids else None
        suggested_algos = [{"id": aid, "name": (get_algo_by_id(aid) or {}).get("name", aid)} for aid in suggested_ids]
        # Detected market for Manual mode: "TRENDING + HIGH VOLUME" etc.
        pred_dir = (pred.get("prediction") or "").upper()
        detected_market = ["TRENDING", "DIRECTIONAL"] if pred_dir in ("BULLISH", "BEARISH") else ["RANGE_BOUND"]
        factors_str = " ".join(pred.get("factors") or [])
        if "volume" in factors_str.lower() or "Volume" in factors_str:
            detected_market.append("HIGH_VOLUME")
        # Primary group name for selected algo (AI mode display)
        selected_group_id = get_primary_group(selected_algo) if selected_algo else ""
        groups_meta = {g["id"]: g["name"] for g in load_strategy_groups()}
        selected_algo_group = groups_meta.get(selected_group_id, "")
        return jsonify({
            "aiRecommendation": ai_recommendation,
            "options": options,
            "stock": stock.upper(),
            "suggestedAlgos": suggested_algos,
            "selectedAlgoName": selected_algo.get("name") if selected_algo else None,
            "selectedAlgoGroup": selected_algo_group,
            "detectedMarket": detected_market,
        })
    except Exception as e:
        return jsonify({"aiRecommendation": {}, "options": [], "stock": stock.upper(), "suggestedAlgos": [], "selectedAlgoName": None, "selectedAlgoGroup": "", "detectedMarket": [], "error": str(e)})


scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "Asia/Kolkata"))
scheduler.add_job(_do_auto_close, "interval", minutes=1, id="auto_close", replace_existing=True)
scheduler.add_job(
    _run_session_engine_tick,
    "interval",
    seconds=SESSION_ENGINE_INTERVAL_SEC,
    id="session_engine",
    replace_existing=True,
)
scheduler.start()
logger.info("Session engine scheduler started")


def main():
    is_dev = os.getenv("FLASK_ENV", "development").lower() == "development"
    app.run(
        host="0.0.0.0", 
        port=5000, 
        debug=is_dev,
        use_reloader=is_dev,  # Auto-reload on code changes
        use_debugger=is_dev   # Enable debugger
    )


if __name__ == "__main__":
    main()
