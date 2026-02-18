# Pending List — IND-Quant-Alpha

Items not yet done. No blocking issues; Manual Mode is production-ready.

---

## 1. Non-blocking improvements (from audit)

| # | Item | Notes |
|---|------|--------|
| 1 | **Session persistence** | Filter or expire very old sessions on load so `trade_sessions.json` / UI list does not grow indefinitely. |
| 2 | **BACKTEST documentation** | Document that BACKTEST is on-demand only (not part of the 60s “approve once, run all day” loop). |
| 3 | **Session stopped log** | Optional: add explicit log when a session is stopped by cutoff_time (15:15) or daily_loss_limit. |

---

## 2. Strategy / Algo logic

| # | Item | Notes |
|---|------|--------|
| 4 | **Implement remaining algos** | Only **5** algos have executable logic (momentum_breakout, vwap_trend_ride, rsi_reversal_fade, orb_opening_range_breakout, index_lead_stock_lag). **35** in `config/algos.json` have no strategy class; they fall back to Momentum Breakout. Add real `check_entry` / `check_exit` / SL/target for high-priority algos (e.g. pullback_continuation, bollinger_mean_reversion, liquidity_sweep_reversal, etc.). |

---

## 3. UX / Docs

| # | Item | Notes |
|---|------|--------|
| 5 | **Execution mode hint** | Consider making Paper vs Live more prominent (e.g. banner when Live is selected). |
| 6 | **Market hours in UI** | Show “Market open” / “Market closed” and engine status (Running/Stopped) in one place. |
| 7 | **Trade history filters** | Already have mode/session_id; optional: date range, instrument, strategy name. |

---

## 4. Operational / Nice-to-have

| # | Item | Notes |
|---|------|--------|
| 8 | **NSE holiday in is_market_open** | `is_market_open()` currently uses weekday + time only. Optional: use NSE holiday calendar (e.g. `_is_nse_trading_day`) so engine does nothing on exchange holidays. |
| 9 | **Telegram / alerts** | DEV_PLAN mentioned Telegram; optional: notify on session start/stop, trade close, kill switch. |
| 10 | **Backtest from session** | Optional: “Run backtest with this instrument/strategy” from the same screen as Manual Mode. |

---

## 5. Known limitations (no fix planned here)

- Data latency (NSE/Zerodha), broker dependency (Zerodha), market hours.
- Strategy logic and parameter tuning (e.g. MomentumBreakout thresholds).
- BACKTEST uses index/equity candles only; no NFO option backtest in current engine.

---

**Last updated:** From Manual Mode audit and codebase review. Revisit as items are completed.
