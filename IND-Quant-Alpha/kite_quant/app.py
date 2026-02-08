"""
Flask server: dashboard, Start/Stop trading, 2:30 scheduler, /api/live, Kill Switch, Settings.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

from engine.config_store import CONFIG_KEYS, apply_config_to_env, load_config, save_config
apply_config_to_env()

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
from engine.zerodha_client import get_positions, get_balance, get_zerodha_profile_info, kill_switch, search_instruments, get_quotes_bulk
from engine.market_calendar import get_calendar_for_month
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta, time
from functools import lru_cache
from threading import Lock
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


@app.route("/dashboard/testing")
def dashboard_testing():
    return render_template("dashboard/testing.html", active_page="testing", page_title="Testing")


@app.route("/dashboard/live")
def dashboard_live():
    return render_template("dashboard/live.html", active_page="live", page_title="Live Trading")


@app.route("/dashboard/analytics")
def dashboard_analytics():
    return render_template("dashboard/analytics.html", active_page="analytics", page_title="Analytics")


@app.route("/dashboard/zerodha")
def dashboard_zerodha():
    return render_template("dashboard/zerodha.html", active_page="zerodha", page_title="My Zerodha")


@app.route("/dashboard/ai-agent")
def dashboard_ai_agent():
    return render_template("dashboard/ai_agent.html", active_page="ai_agent", page_title="AI Trading Agent")


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
    # Allow TRADING_AMOUNT even when empty or "0"
    payload = {}
    for k, v in data.items():
        if k not in CONFIG_KEYS:
            continue
        v_str = str(v).strip() if v is not None else ""
        if k == "TRADING_AMOUNT" or v_str:
            payload[k] = v_str
    if not payload:
        return {"ok": False, "error": "No valid settings to save"}, 400
    try:
        save_config(payload)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


@app.route("/api/trading-amount", methods=["GET", "POST"])
def api_trading_amount():
    """GET: return current trading amount from config. POST: save to config.json and return success."""
    if request.method == "GET":
        amount = load_config().get("TRADING_AMOUNT", "").strip()
        return jsonify({"ok": True, "trading_amount": amount})
    data = request.get_json()
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON or missing Content-Type: application/json"}), 400
    val = data.get("amount") if data.get("amount") is not None else data.get("TRADING_AMOUNT")
    val_str = str(val).strip() if val is not None else ""
    try:
        save_config({"TRADING_AMOUNT": val_str})
        return jsonify({"ok": True, "message": "Saved", "trading_amount": val_str})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
    
    # Fetch live Nifty 50 data only if Indian market is open
    nifty_live = {}
    bank_nifty_live = {}
    india_vix_data = {}
    market_status = {}
    
    if _is_indian_market_open():
        nifty_live = fetch_nifty50_live()
        # Fetch Bank Nifty, India VIX, and market status
        bank_nifty_live = fetch_bank_nifty_live()
        india_vix_data = fetch_india_vix()
        market_status = _determine_market_status(nifty_live)
    # If market is closed, all will be empty dicts
    
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
        "trade_count_today": sm.trade_count_today(),
        "max_trades_per_day": sm.get_max_trades_per_day(),
        "minutes_until_auto_close": minutes_left,
        "auto_close_time": os.getenv("AUTO_CLOSE_TIME", "14:30"),
        "market_prediction": prediction_data.get("prediction", "NEUTRAL"),
        "prediction_confidence": prediction_data.get("confidence", 50),
        "prediction_factors": prediction_data.get("factors", []),
        "prediction_accuracy": accuracy,
        "actual_direction": actual_direction,
        "overall_accuracy": accuracy_data.get("overall_accuracy", 0),
        "price_change_pct": price_change,
        "trading_amount": load_config().get("TRADING_AMOUNT", "").strip(),
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
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "score": round(score, 2),
            "factors": factors,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "prediction": "NEUTRAL",
            "confidence": 50,
            "score": 0.0,
            "factors": [f"Error: {str(e)}"],
            "timestamp": datetime.now().isoformat(),
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
        sm = get_session_manager()
        
        return {
            "ok": True,
            "symbol": symbol,
            "min_trades": suggestion["min_trades"],
            "suggested_max": suggestion["suggested_max"],
            "current_max": sm.get_max_trades_per_day(),
            "reasoning": suggestion["reasoning"],
            "factors": suggestion["factors"],
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
    """Search NSE equity symbols from Zerodha with live price, OHLC, change% (Kite-style)."""
    apply_config_to_env()
    q = (request.args.get("q") or "").strip()
    limit = min(30, max(5, int(request.args.get("limit", 20))))
    if len(q) < 2:
        return jsonify({"ok": True, "symbols": []})
    try:
        results = search_instruments(q, limit=limit)
        if not results:
            return jsonify({"ok": True, "symbols": []})
        nse_symbols = [r.get("symbol") or r.get("tradingsymbol", "") for r in results if (r.get("exchange") or "NSE") == "NSE" and (r.get("symbol") or r.get("tradingsymbol"))]
        quotes = get_quotes_bulk(nse_symbols)
        for r in results:
            sym = (r.get("symbol") or r.get("tradingsymbol") or "").strip().upper()
            r["exchange"] = r.get("exchange", "NSE")
            if sym and sym in quotes:
                r["last"] = quotes[sym].get("last")
                r["open"] = quotes[sym].get("open")
                r["high"] = quotes[sym].get("high")
                r["low"] = quotes[sym].get("low")
                r["change"] = quotes[sym].get("change")
                r["change_pct"] = quotes[sym].get("change_pct")
            else:
                r["last"] = r.get("last", 0)
                r["open"] = r.get("open", 0)
                r["high"] = r.get("high", 0)
                r["low"] = r.get("low", 0)
                r["change"] = r.get("change", 0)
                r["change_pct"] = r.get("change_pct", 0)
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


def _build_ai_trade_signals() -> dict:
    """Build momentum, reversal, news lists (top 3 each) for AI Trading Agent. Uses cached intraday picks when fresh."""
    global _intraday_picks_cache, _intraday_picks_cache_time
    now = datetime.now()
    if _intraday_picks_cache is None or _intraday_picks_cache_time is None or (now - _intraday_picks_cache_time) >= INTRADAY_PICKS_CACHE_TTL:
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
        got = {r.get("symbol") for r in results}
        for sym in symbols:
            if sym not in got:
                results.append({"symbol": sym, "score": 0.0, "tags": ["Timeout"], "prediction": "NEUTRAL"})
        results.sort(key=lambda x: -(x.get("score") or 0))
        picks = results[:15]
        _intraday_picks_cache = {"picks": picks, "ai_suggestion": _get_ai_trade_suggestion(picks), "cached_at": now.isoformat()}
        _intraday_picks_cache_time = now
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


def get_index_market_bias() -> dict:
    """
    AI market bias for NIFTY and BANKNIFTY. Uses live index, VIX, US close, optional 5m VWAP/trend.
    Returns: niftyBias, bankNiftyBias, confidence, reasons.
    """
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

    return {
        "niftyBias": nifty_bias,
        "bankNiftyBias": bank_nifty_bias,
        "confidence": confidence,
        "reasons": reasons[:6],
        "niftyScore": round(nifty_score, 2),
        "bankNiftyScore": round(bank_nifty_score, 2),
        "vixValue": vix_val,
    }


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
    options = []
    for i, strike in enumerate(strikes):
        if use_ce:
            prem = max(20, 80 - (strike - spot) / 2 + (30 if i == 0 else 0))
        else:
            prem = max(20, 80 + (spot - strike) / 2 + (30 if i == 0 else 0))
        prem = round(prem, 2)
        lot_cost = prem * lot_size
        options.append({
            "type": "CE" if use_ce else "PE",
            "strike": strike,
            "premium": prem,
            "lotSize": lot_size,
            "lotCost": lot_cost,
            "distanceFromATM": i,
        })

    # Filter by budget and sort by closest to ATM
    affordable = [o for o in options if o["lotCost"] <= max_risk_per_trade]
    affordable.sort(key=lambda x: (x["distanceFromATM"], x["premium"]))
    top = affordable[:3]
    if not top and options:
        top = options[:3]  # show anyway but frontend will mark Over Budget

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

    # Safe to show only if we have at least one affordable or bias is clear
    safe = bias != "NEUTRAL" and (float(max_risk_per_trade) > 0)
    return top if top else options[:3], rec, safe


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
    """GET /api/index-options/{index}: affordable options + AI recommendation. Query: max_risk (optional)."""
    max_risk = request.args.get("max_risk", type=float)
    if max_risk is None or max_risk <= 0:
        max_risk = 3000.0  # default for small capital
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


def _mock_option_chain(stock: str) -> tuple[list, dict]:
    """Return (options list, aiRecommendation) for a stock. Uses quote for ATM; mock CE/PE around it."""
    try:
        quote = fetch_nse_quote(stock)
        spot = float(quote.get("last") or quote.get("close") or 0)
        if spot <= 0:
            spot = 500.0  # fallback
        # Round to typical strike interval (e.g. 50 for mid-cap, 100 for large)
        step = 50 if spot < 2000 else 100
        base = round(spot / step) * step
        pred = _get_market_prediction(stock)
        direction = "CE" if (pred.get("prediction") or "").upper() == "BULLISH" else "PE"
        confidence = pred.get("confidence", 50) or 50
        factors = pred.get("factors", [])
        reason = " ".join(factors[:3]) if factors else "Trend + Volume + Sentiment"
        options = []
        for i in range(-2, 3):  # 5 strikes
            strike = base + i * step
            for typ in ["CE", "PE"]:
                # Mock premium: higher for OTM, lower for ITM
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
        return options, rec
    except Exception:
        spot = 500.0
        base = 500
        return [
            {"type": "CE", "strike": base, "premium": 28, "lotSize": 250, "iv": 18},
            {"type": "PE", "strike": base, "premium": 30, "lotSize": 250, "iv": 18},
        ], {"direction": "CE", "strikePreference": "ATM", "confidence": 60, "holdingTime": "30-90 min", "reason": "Trend + Volume"}


@app.route("/api/options/<stock>")
def api_options(stock: str):
    """GET /api/options/{stock}: option chain + AI recommendation for budget filtering."""
    try:
        options, ai_recommendation = _mock_option_chain(stock.upper())
        return jsonify({
            "aiRecommendation": ai_recommendation,
            "options": options,
            "stock": stock.upper(),
        })
    except Exception as e:
        return jsonify({"aiRecommendation": {}, "options": [], "stock": stock.upper(), "error": str(e)})


scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "Asia/Kolkata"))
scheduler.add_job(_do_auto_close, "interval", minutes=1)
scheduler.start()


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
