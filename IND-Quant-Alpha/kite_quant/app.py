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

from engine.strategy import compute_us_bias, suggest_min_trades
from engine.data_fetcher import fetch_nse_quote, get_historical_for_backtest, fetch_nse_ohlc
from engine.sentiment_engine import get_sentiment_for_symbol
from engine.session_manager import get_session_manager, SessionStatus
from engine.backtest import run_backtest
from engine.zerodha_client import get_positions, kill_switch

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
    }


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    data = request.get_json() or {}
    symbol = data.get("symbol", "RELIANCE")
    days = int(data.get("days", 60))
    results = run_backtest(symbol=symbol, days=days)
    return {"ok": True, "count": len(results), "results": results[:50]}


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
