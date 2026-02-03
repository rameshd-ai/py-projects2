"""
Flask server: login, dashboard, Start/Stop trading, 2:30 scheduler, /api/live, Kill Switch, Settings.
"""
from __future__ import annotations

import os
from threading import Lock

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

from engine.config_store import CONFIG_KEYS, apply_config_to_env, load_config, save_config
apply_config_to_env()

from engine.strategy import compute_us_bias
from engine.data_fetcher import fetch_nse_quote, get_historical_for_backtest
from engine.sentiment_engine import get_sentiment_for_symbol
from engine.session_manager import get_session_manager, SessionStatus
from engine.backtest import run_backtest
from engine.indstocks_client import get_positions, kill_switch

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production")
login_manager = LoginManager(app)
login_manager.login_view = "login"

# In-memory user for demo (replace with DB in production)
class User(UserMixin):
    def __init__(self, id_: str):
        self.id = id_

USERS = {"admin": "admin"}  # demo only
_user_lock = Lock()

@login_manager.user_loader
def load_user(user_id):
    with _user_lock:
        if user_id in USERS:
            return User(user_id)
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        with _user_lock:
            if USERS.get(username) == password:
                login_user(User(username))
                return redirect(url_for("dashboard"))
        return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
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
@login_required
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
@login_required
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
@login_required
def start_trading():
    sm = get_session_manager()
    if sm.is_past_auto_close():
        return {"ok": False, "error": "Past auto-close time (2:30 PM IST)"}, 400
    sm.start_trading()
    return {"ok": True, "status": sm.get_status()}


@app.route("/api/stop", methods=["POST"])
@login_required
def stop_trading():
    get_session_manager().stop_trading()
    return {"ok": True, "status": get_session_manager().get_status()}


@app.route("/api/kill", methods=["POST"])
@login_required
def panic_kill():
    results = kill_switch()
    get_session_manager().stop_trading()
    return {"ok": True, "closed": len(results), "results": results}


@app.route("/api/live")
@login_required
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
        "positions": positions,
        "pnl": pnl,
        "trade_count_today": sm.trade_count_today(),
        "minutes_until_auto_close": minutes_left,
        "auto_close_time": os.getenv("AUTO_CLOSE_TIME", "14:30"),
    }


@app.route("/api/backtest", methods=["POST"])
@login_required
def api_backtest():
    data = request.get_json() or {}
    symbol = data.get("symbol", "RELIANCE")
    days = int(data.get("days", 60))
    results = run_backtest(symbol=symbol, days=days)
    return {"ok": True, "count": len(results), "results": results[:50]}


def _do_auto_close():
    sm = get_session_manager()
    if sm.is_trading_on() and sm.is_past_auto_close():
        sm.auto_close()


scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "Asia/Kolkata"))
scheduler.add_job(_do_auto_close, "interval", minutes=1)
scheduler.start()


def main():
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_ENV") == "development")


if __name__ == "__main__":
    main()
