"""
Flask server: dashboard, Start/Stop trading, 2:30 scheduler, /api/live, Kill Switch, Settings.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

from engine.config_store import CONFIG_KEYS, apply_config_to_env, load_config, save_config
apply_config_to_env()

from engine.strategy import compute_us_bias, suggest_min_trades, consensus_signal, compute_technicals
from engine.data_fetcher import fetch_nse_quote, get_historical_for_backtest, fetch_nse_ohlc
from engine.sentiment_engine import get_sentiment_for_symbol
from engine.session_manager import get_session_manager, SessionStatus
from engine.backtest import run_backtest
from engine.zerodha_client import get_positions, kill_switch
import json
from pathlib import Path
from datetime import datetime, date, timedelta, time
from functools import lru_cache
from threading import Lock
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    from backports.zoneinfo import ZoneInfo

# Cache for news and predictions
_news_cache: dict[str, tuple[list, datetime]] = {}
_prediction_cache: dict[str, tuple[dict, datetime]] = {}
_us_bias_cache: tuple[Any, datetime] | None = None
_cache_lock = Lock()
NEWS_CACHE_TTL = timedelta(minutes=10)  # Cache news for 10 minutes
PREDICTION_CACHE_TTL = timedelta(minutes=5)  # Cache prediction for 5 minutes
US_BIAS_CACHE_TTL = timedelta(hours=12)  # Cache US bias for 12 hours (constant during Indian session)
US_BIAS_ERROR_CACHE_TTL = timedelta(minutes=1)  # Retry quickly if fetch failed

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production")
# Enable auto-reload for templates and code
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # Disable caching for development

# Disable caching in development mode
@app.after_request
def after_request(response):
    if os.getenv("FLASK_ENV", "development").lower() == "development":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


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
    payload = {k: str(v).strip() for k, v in data.items() if k in CONFIG_KEYS and v}
    if not payload:
        return {"ok": False, "error": "No valid settings to save"}, 400
    try:
        save_config(payload)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


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
            # Use shorter cache during market hours (5 min), longer after close
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


@app.route("/api/live")
def api_live():
    """Current price(s), signal, positions, P&L, status. Poll every 5–10 s."""
    # Clear old caches at start of new day
    global _accuracy_cache, _prediction_cache
    today = date.today().isoformat()
    with _cache_lock:
        # Clear accuracy cache if it contains old data
        to_delete = []
        for key, (data, cached_time) in _accuracy_cache.items():
            if cached_time.date().isoformat() != today:
                to_delete.append(key)
        for key in to_delete:
            del _accuracy_cache[key]
    
    sm = get_session_manager()
    symbol = request.args.get("symbol", "RELIANCE")
    mode = request.args.get("mode", "backtest")

    # Use cached US bias for faster response
    us_market_status = _get_cached_us_bias()
    us_bias_obj = us_market_status["us_bias_obj"]
    
    # Fetch live US futures (not cached as it changes fast)
    from engine.data_fetcher import fetch_us_futures
    us_futures = fetch_us_futures()
    
    # Use cached news and prediction for faster response
    headlines = _get_cached_news(symbol)
    sent = get_sentiment_for_symbol(symbol)
    # Update sentiment but use cached headlines
    sent["headlines"] = headlines
    
    quote = fetch_nse_quote(symbol)
    if quote.get("last", 0) == 0 and mode == "live":
        quote = {"symbol": symbol, "last": 0, "open": 0, "high": 0, "low": 0}

    positions = []
    if mode == "live":
        positions = get_positions()
        sm.set_positions(positions)
    else:
        positions = sm.get_positions()

    pnl = 0.0
    for p in positions:
        pnl += float(p.get("pnl", p.get("unrealized", 0)))

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
    
    if _is_after_market_close():
        # Market closed - can show actual data
        actual_direction = accuracy_data.get("today_actual")
        price_change = accuracy_data.get("price_change_pct", 0)
        accuracy = accuracy_data.get("today_accuracy")
    # else: leave as None (market still open or not started yet)
    
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
        "sentiment_score": sent.get("score", 0),
        "sentiment_blacklist": sent.get("blacklist_24h", False),
        "news_headlines": sent.get("headlines", []),
        "positions": positions,
        "pnl": pnl,
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
    }


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    data = request.get_json() or {}
    symbol = data.get("symbol", "RELIANCE")
    days = int(data.get("days", 60))
    results = run_backtest(symbol=symbol, days=days)
    return {"ok": True, "count": len(results), "results": results[:50]}


def _get_predictions_file() -> Path:
    """Get path to predictions storage file."""
    return Path(__file__).resolve().parent / "predictions.json"


def _load_predictions() -> dict:
    """Load predictions history."""
    path = _get_predictions_file()
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


def _get_market_prediction(symbol: str = "RELIANCE") -> dict[str, Any]:
    """Predict today's market direction (bullish/bearish) based on multiple factors."""
    try:
        us_bias = compute_us_bias()
        
        # Get sentiment (this is fast, no need to cache separately)
        sent = get_sentiment_for_symbol(symbol)
        
        # Get recent data for technical analysis - use yfinance directly for speed
        # Skip Zerodha API call for prediction to speed things up
        df = get_historical_for_backtest(symbol, days=5)
        
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
        
        # Technical indicators (30% weight)
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
    """Check if Indian stock market (NSE) is currently open."""
    ist = ZoneInfo('Asia/Kolkata')
    now_ist = datetime.now(ist)
    current_time = now_ist.time()
    market_open = time(9, 15)  # 9:15 AM IST
    market_close = time(15, 30)  # 3:30 PM IST
    
    # Market is open between 9:15 AM and 3:30 PM IST on weekdays
    if now_ist.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
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
        is_frozen = predictions[today].get("frozen_at") is not None or _is_after_market_close()
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
        
        # If actual is already frozen (calculated after market close), return it
        if today in predictions and predictions[today].get("actual") is not None:
            if _is_after_market_close() or predictions[today].get("actual_frozen"):
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
        
        # Only calculate actual if market is closed
        if not _is_after_market_close():
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
            if pred_data.get("symbol", "RELIANCE").upper() == symbol.upper():
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
                })
        
        # Add today's incomplete record if not already present
        if not any(h["date"] == today for h in history):
            # Get today's prediction (might be WAITING)
            today_pred = _get_or_create_todays_prediction(symbol)
            history.append({
                "date": today,
                "prediction": today_pred.get("prediction", "—"),
                "confidence": today_pred.get("confidence", 0),
                "usa_bias": today_pred.get("usa_bias", "—"),
                "usa_bias_value": today_pred.get("usa_bias_value", 0),
                "actual": None,
                "accuracy": None,
                "price_change_pct": 0,
                "analysis": "⏳ In progress...",
                "factors": today_pred.get("factors", []),
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


def _do_auto_close():
    sm = get_session_manager()
    if sm.is_trading_on() and sm.is_past_auto_close():
        sm.auto_close()


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
