"""
Backtest engine: candle-by-candle replay using same strategy classes and RiskManager.
Deterministic, offline. Does not use the real-time session engine.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.data_fetcher import fetch_nse_ohlc
from strategies.strategy_registry import STRATEGY_MAP
from risk.risk_manager import RiskConfig, RiskManager
from nifty_banknifty_engine.constants import nse_symbol as _nse_symbol


def _interval_kite(interval: str) -> str:
    if interval in ("5minute", "5min"):
        return "5m"
    if interval in ("15minute", "15min"):
        return "15m"
    return interval or "5m"


def _load_candles(instrument: str, from_date: str, to_date: str, timeframe: str) -> list[dict[str, Any]]:
    """Load historical candles for instrument and date range. Uses NIFTY/BANKNIFTY symbol mapping."""
    symbol = _nse_symbol(instrument)
    kite_interval = _interval_kite(timeframe)
    try:
        start = datetime.strptime(from_date[:10], "%Y-%m-%d")
        end = datetime.strptime(to_date[:10], "%Y-%m-%d")
        days = max(1, (end - start).days + 1)
        period = "60d" if days > 30 else ("30d" if days > 5 else "5d")
        df = fetch_nse_ohlc(symbol, interval=kite_interval, period=period)
        if df is None or df.empty or "Close" not in df.columns:
            return []
        out = []
        for _, row in df.iterrows():
            d = row.get("Datetime")
            if d is not None and hasattr(d, "date"):
                if not (start.date() <= d.date() <= end.date()):
                    continue
            c = {
                "date": d.isoformat() if d is not None and hasattr(d, "isoformat") else str(d),
                "open": float(row.get("Open", row.get("open", 0))),
                "high": float(row.get("High", row.get("high", 0))),
                "low": float(row.get("Low", row.get("low", 0))),
                "close": float(row.get("Close", row.get("close", 0))),
                "volume": float(row.get("Volume", row.get("volume", 0))),
            }
            out.append(c)
        if not out:
            for _, row in df.iterrows():
                d = row.get("Datetime")
                c = {
                    "date": d.isoformat() if d is not None and hasattr(d, "isoformat") else str(d),
                    "open": float(row.get("Open", row.get("open", 0))),
                    "high": float(row.get("High", row.get("high", 0))),
                    "low": float(row.get("Low", row.get("low", 0))),
                    "close": float(row.get("Close", row.get("close", 0))),
                    "volume": float(row.get("Volume", row.get("volume", 0))),
                }
                out.append(c)
        return out
    except Exception:
        return []


def run_backtest_engine(
    instrument: str,
    strategy_name: str,
    from_date: str,
    to_date: str,
    timeframe: str = "5minute",
    initial_capital: float = 100000.0,
    risk_percent_per_trade: float = 1.0,
    max_daily_loss_percent: float = 3.0,
    max_trades: int = 20,
) -> dict[str, Any]:
    """
    Run backtest: load candles, loop candle-by-candle, use strategy + RiskManager.
    Returns dict with trades, net_pnl, win_rate, max_drawdown, equity_curve.
    """
    candles = _load_candles(instrument, from_date, to_date, timeframe)
    if len(candles) < 10:
        return {
            "error": "Insufficient candle data",
            "trades": [],
            "net_pnl": 0,
            "win_rate": 0,
            "max_drawdown": 0,
            "equity_curve": [],
        }
    StrategyClass = STRATEGY_MAP.get(strategy_name) or STRATEGY_MAP.get("Momentum Breakout")
    from backtest.backtest_data_provider import BacktestDataProvider
    provider = BacktestDataProvider(candles)
    strategy = StrategyClass(instrument, provider)
    config = RiskConfig(
        capital=initial_capital,
        risk_percent_per_trade=risk_percent_per_trade,
        max_daily_loss_percent=max_daily_loss_percent,
        max_trades=max_trades,
    )
    risk_mgr = RiskManager(config)
    session = {
        "daily_pnl": 0.0,
        "trades_taken_today": 0,
        "virtual_balance": initial_capital,
    }
    current_trade = None
    trades = []
    equity = initial_capital
    equity_curve = [{"index": 0, "equity": equity, "date": candles[0].get("date", "")}]
    peak = equity
    max_drawdown = 0.0
    for i in range(len(candles)):
        provider.set_index(i)
        candle = candles[i]
        if current_trade is not None:
            exit_reason = strategy.check_exit(current_trade)
            if exit_reason:
                exit_price = float(candle.get("close", 0))
                entry_price = current_trade["entry_price"]
                qty = current_trade["qty"]
                pnl = (exit_price - entry_price) * qty
                equity += pnl
                session["virtual_balance"] = equity
                session["daily_pnl"] = (session.get("daily_pnl") or 0) + pnl
                session["trades_taken_today"] = (session.get("trades_taken_today") or 0) + 1
                trades.append({
                    "entry_time": current_trade["entry_time"],
                    "exit_time": candle.get("date", ""),
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "qty": qty,
                    "pnl": round(pnl, 2),
                    "exit_reason": exit_reason,
                })
                current_trade = None
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0
                if dd > max_drawdown:
                    max_drawdown = dd
                equity_curve.append({"index": i, "equity": equity, "date": candle.get("date", "")})
        else:
            result = strategy.check_entry()
            if isinstance(result, dict):
                can_enter = result.get("can_enter", False)
                entry_price = result.get("entry_price")
            else:
                can_enter, entry_price = result
            if can_enter and entry_price is not None:
                # Use F&O-aware stop/target for options (wider stops, realistic targets)
                if hasattr(strategy, 'get_stop_loss_fo_aware'):
                    stop_loss = strategy.get_stop_loss_fo_aware(entry_price, session)
                    target = strategy.get_target_fo_aware(entry_price, session)
                else:
                    stop_loss = strategy.get_stop_loss(entry_price)
                    target = strategy.get_target(entry_price)
                stop_for_risk = stop_loss if stop_loss != entry_price else entry_price * 0.995
                approved, reason, lots = risk_mgr.validate_trade(session, entry_price, stop_for_risk, 1, premium=None)
                if approved and lots > 0:
                    qty = lots
                    current_trade = {
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "target": target,
                        "qty": qty,
                        "entry_time": candle.get("date", ""),
                        "strategy_name": strategy_name,
                    }
    wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
    total = len(trades)
    win_rate = (wins / total * 100) if total else 0
    net_pnl = equity - initial_capital
    return {
        "instrument": instrument,
        "strategy": strategy_name,
        "from_date": from_date,
        "to_date": to_date,
        "timeframe": timeframe,
        "initial_capital": initial_capital,
        "final_equity": round(equity, 2),
        "net_pnl": round(net_pnl, 2),
        "trades": trades,
        "total_trades": total,
        "win_rate": round(win_rate, 2),
        "max_drawdown": round(max_drawdown * 100, 2),
        "equity_curve": equity_curve,
    }


def save_backtest_result(result: dict[str, Any]) -> None:
    """Append backtest result to data/backtest_results.json."""
    base = Path(__file__).resolve().parent.parent
    path = base / "data" / "backtest_results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = {"runs": [], "updatedAt": datetime.now().isoformat()}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        runs = data.get("runs") or []
        result["run_id"] = f"bt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        runs.append(result)
        data["runs"] = runs[-100:]
        data["updatedAt"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def load_backtest_results() -> list[dict[str, Any]]:
    """Load all backtest runs from data/backtest_results.json."""
    base = Path(__file__).resolve().parent.parent
    path = base / "data" / "backtest_results.json"
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("runs") or []
    except Exception:
        return []
