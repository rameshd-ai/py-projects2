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
from datetime import datetime, date

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


@app.route("/api/live")
def api_live():
    """Current price(s), signal, positions, P&L, status. Poll every 5–10 s."""
    sm = get_session_manager()
    symbol = request.args.get("symbol", "RELIANCE")
    mode = request.args.get("mode", "backtest")

    us_bias = compute_us_bias()
    sent = get_sentiment_for_symbol(symbol)
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

    # Get market prediction
    prediction_data = _get_market_prediction(symbol)
    accuracy_data = _update_prediction_accuracy(symbol)
    
    return {
        "status": sm.get_status(),
        "trading_on": sm.is_trading_on(),
        "mode": mode,
        "symbol": symbol,
        "price": quote.get("last", 0),
        "us_bias": us_bias.bias,
        "us_bias_block_long": us_bias.block_long_first_hour,
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
        "prediction_accuracy": accuracy_data.get("today_accuracy"),
        "actual_direction": accuracy_data.get("today_actual"),
        "overall_accuracy": accuracy_data.get("overall_accuracy", 0),
        "price_change_pct": accuracy_data.get("price_change_pct", 0),
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
    """Save predictions history."""
    path = _get_predictions_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _get_market_prediction(symbol: str = "RELIANCE") -> dict[str, Any]:
    """Predict today's market direction (bullish/bearish) based on multiple factors."""
    try:
        us_bias = compute_us_bias()
        sent = get_sentiment_for_symbol(symbol)
        
        # Get recent data for technical analysis
        df = fetch_nse_ohlc(symbol, interval="1d", period="5d")
        if df.empty:
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


def _update_prediction_accuracy(symbol: str = "RELIANCE") -> dict[str, Any]:
    """Update prediction accuracy by comparing today's prediction with actual market movement."""
    try:
        predictions = _load_predictions()
        today = date.today().isoformat()
        
        # Get today's opening price
        quote = fetch_nse_quote(symbol)
        current_price = quote.get("last", 0)
        open_price = quote.get("open", 0)
        
        if not open_price or not current_price:
            return {"accuracy": None, "message": "Price data not available"}
        
        # Calculate actual movement
        price_change_pct = ((current_price - open_price) / open_price) * 100 if open_price else 0
        actual_direction = "BULLISH" if price_change_pct > 0.5 else ("BEARISH" if price_change_pct < -0.5 else "NEUTRAL")
        
        # Get today's prediction
        if today not in predictions:
            # Create prediction for today
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
        
        # Update actual result
        predictions[today]["actual"] = actual_direction
        predictions[today]["actual_change_pct"] = round(price_change_pct, 2)
        
        # Calculate accuracy
        predicted = predictions[today]["prediction"]
        if predicted == actual_direction:
            predictions[today]["accuracy"] = "CORRECT"
        elif predicted == "NEUTRAL" or actual_direction == "NEUTRAL":
            predictions[today]["accuracy"] = "PARTIAL"
        else:
            predictions[today]["accuracy"] = "INCORRECT"
        
        _save_predictions(predictions)
        
        # Calculate overall accuracy
        correct = sum(1 for p in predictions.values() if p.get("accuracy") == "CORRECT")
        total = sum(1 for p in predictions.values() if p.get("accuracy") is not None)
        accuracy_pct = (correct / total * 100) if total > 0 else 0
        
        return {
            "today_prediction": predicted,
            "today_actual": actual_direction,
            "today_accuracy": predictions[today]["accuracy"],
            "price_change_pct": round(price_change_pct, 2),
            "overall_accuracy": round(accuracy_pct, 1),
            "correct_predictions": correct,
            "total_predictions": total,
        }
    except Exception as e:
        return {"accuracy": None, "error": str(e)}


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
