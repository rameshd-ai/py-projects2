# Manual Mode Functionality Audit

**Audit date:** Based on codebase state. **Last updated:** after index-option exit fix (BaseStrategy._get_exit_ltp + data_provider.get_quote).  
**Definition:** User approves once → session starts → AI selects best strategy → engine scans market → auto entry when conditions met → exit via SL/target/strategy rules → re-evaluate and possibly new strategy → repeat until max_trades / daily_loss_limit / cutoff (15:15). Same behavior for LIVE, PAPER, BACKTEST (except execution layer).

---

## 1. Item-by-item verification

### A. Session Lifecycle

| Requirement | Status | File / function |
|-------------|--------|------------------|
| Session created on `POST /api/approve-trade` | ✅ Implemented & working | `app.py`: `@app.route("/api/approve-trade", methods=["POST"])`, `api_approve_trade()` (2659–2712). Creates session with status ACTIVE, max_trades_allowed, daily_loss_limit, cutoff_time "15:15". |
| Session persisted and restored on restart | ✅ Implemented & working | `app.py`: `_SESSIONS_FILE = .../data/trade_sessions.json`, `_save_trade_sessions()` (2498–2506), `_load_trade_sessions()` (2483–2495). `_load_trade_sessions()` called at module load (2510). Save called after approve (2707), after tick updates (2779, 2804, 2862, 2865). |
| Session runs automatically without further user action | ✅ Implemented & working | `app.py`: `BackgroundScheduler` runs `_run_session_engine_tick` every `SESSION_ENGINE_INTERVAL_SEC` (60) (3098–3101). |
| Session stops on max_trades_allowed | ✅ Implemented & working | `app.py`: `_run_session_engine_tick()` (2792–2795): `taken >= max_trades` → `session["status"] = "STOPPED"`. |
| Session stops on daily_loss_limit | ✅ Implemented & working | `app.py`: `_run_session_engine_tick()` (2797–2800): `daily_pnl <= -float(daily_limit)` → `session["status"] = "STOPPED"`. |
| Session stops on cutoff_time (15:15) | ✅ Implemented & working | `app.py`: `INTRADAY_CUTOFF_TIME = time(15, 15)` (2475). In `_run_session_engine_tick()` (2774–2781): `now.time() >= cutoff` → all ACTIVE sessions set to STOPPED. |

---

### B. Algo Library Usage

| Requirement | Status | File / function |
|-------------|--------|------------------|
| All strategies as classes in `kite_quant/strategies` | ✅ Implemented & working | `strategies/`: `base_strategy.py`, `momentum_breakout.py`, `orb_breakout.py`, `rsi_reversal.py`, `vwap_trend.py`. |
| Strategy selector dynamically chooses from library | ✅ Implemented & working | `app.py`: `_pick_best_strategy(instrument)` (2714–2735) uses `get_suggested_algos(stock_indicators, market_indicators, top_n=1)` and `get_algo_by_id(ids[0])`; for NIFTY/BANKNIFTY returns "Index Momentum". |
| Session engine loads strategy via registry (not hardcoded) | ✅ Implemented & working | `app.py`: `get_strategy_for_session(session, strategy_data_provider, strategy_name_override)` (2741, 2757, 2813). `strategies/strategy_registry.py`: `STRATEGY_MAP` maps names/ids to classes; `get_strategy_for_session()` returns `StrategyClass(instrument, data_provider)`. |
| Multiple strategies can be used in same session across the day | ✅ Implemented & working | Each tick re-picks strategy: `_pick_best_strategy(instrument)` then `_check_entry_real(session, strategy_name_override=strategy_name)` (2809–2810). After exit, next tick picks again (no re-approval). |

---

### C. Entry Logic (CRITICAL)

| Requirement | Status | File / function |
|-------------|--------|------------------|
| `_check_entry_stub` fully replaced | ✅ Implemented & working | No stub; engine uses `_check_entry_real(session, strategy_name_override=strategy_name)` (2739–2746) which calls `strategy.check_entry()`. |
| Entry conditions are real (price/volume/indicator) | ✅ Implemented & working | e.g. `strategies/momentum_breakout.py`: `check_entry()` uses `get_recent_candles()`, high break, volume spike (10–22). Similar real logic in orb_breakout, rsi_reversal, vwap_trend. |
| Engine can automatically enter without manual clicks | ✅ Implemented & working | `_run_session_engine_tick()` (2810–2860): when no current trade, `_check_entry_real()`; if `can_enter` and `entry_price`, risk validation then `execute_entry()`. |
| Works for stocks | ✅ Implemented & working | Session instrument = equity symbol; strategy uses NSE candles/LTP; executor uses NSE. |
| Works for index options | ✅ Implemented & working | Entry: engine uses `session["tradingsymbol"]` and `exchange="NFO"` for quote (2820–2824), passes symbol to `execute_entry`. PAPER executor uses NFO symbol/exchange for entry/exit (paper_executor.py). LIVE uses tradingsymbol/exchange (live_executor.py). |

---

### D. Exit Logic

| Requirement | Status | File / function |
|-------------|--------|------------------|
| Exit is NOT time-based stub | ✅ Implemented & working | `_manage_trade_real(session)` (2749–2766) calls `strategy.check_exit(trade)`; exit reasons are strategy-defined (e.g. STOP_LOSS, TARGET). |
| Exit uses stop loss | ✅ Implemented & working | e.g. `momentum_breakout.check_exit()` (30–39): compares `ltp` to `trade.get("stop_loss")`. |
| Exit uses target | ✅ Implemented & working | Same: compares `ltp` to `trade.get("target")`. |
| Exit uses strategy-specific rules | ✅ Implemented & working | Base and all strategies implement `check_exit(trade)` (base_strategy.py 22–27; momentum_breakout, orb_breakout, rsi_reversal, vwap_trend). |
| Exit triggers correct order (LIVE) or simulation (PAPER/BACKTEST) | ✅ Implemented & working | `execute_exit(session)` in `execution/executor.py` (39–51) routes to live_executor, paper_executor, or backtest_executor by `session["execution_mode"]`. |
| **Index options: exit LTP source** | ✅ Implemented & working | `strategies/base_strategy.py`: `_get_exit_ltp(trade)` uses `trade["symbol"]` + `exchange="NFO"` via `self.data.get_quote(..., exchange="NFO")` when `trade.get("exchange") == "NFO"`, else `self.data.get_ltp(self.instrument)`. `strategies/data_provider.py`: `get_quote(symbol, exchange="NSE")` (68–70) calls Zerodha. All strategies (momentum_breakout, orb_breakout, rsi_reversal, vwap_trend) use `_get_exit_ltp(trade)` in `check_exit`. NFO SL/target now evaluated against option premium. |

---

### E. Continuous Trading (ALL DAY LOOP)

| Requirement | Status | File / function |
|-------------|--------|------------------|
| After exit, engine re-evaluates market | ✅ Implemented & working | Next tick has no `current_trade_id`; loop falls through to `_pick_best_strategy` and `_check_entry_real` (2808–2810). |
| After exit, re-selects best strategy | ✅ Implemented & working | `strategy_id, strategy_name = _pick_best_strategy(instrument)` every tick when no open trade (2809). |
| Waits for next valid entry | ✅ Implemented & working | Same tick loop; entry only when `can_enter and entry_price` and risk approved (2810–2855). |
| No re-approval after first approval | ✅ Implemented & working | Single `POST /api/approve-trade` creates session; scheduler drives all subsequent entries/exits. |
| daily_trade_count increments correctly | ✅ Implemented & working | Trade count updates are centralized in `engine/risk_engine.py::evaluate_post_exit/register_trade_result` for live/paper/backtest flows. |

---

### F. Risk Manager Integration

| Requirement | Status | File / function |
|-------------|--------|------------------|
| Risk manager runs before every trade | ✅ Implemented & working | `_run_session_engine_tick()` (2841–2852): `RiskManager(risk_config)`, `risk_mgr.validate_trade(...)`; only on `approved` does it call `execute_entry()`. |
| Position size calculated dynamically | ✅ Implemented & working | `risk/risk_manager.py`: `calculate_position_size()`, `validate_trade()` returns `(approved, reason, lots)`; engine uses `qty = max(1, lots * lot_size)` (2852–2854). |
| Trades rejected if risk too high / capital insufficient / daily loss limit | ✅ Implemented & working | `RiskManager.can_trade_today()` (42–50): daily loss limit and max trades; `can_afford_trade()` (52–55); `validate_trade()` (57–82) returns not approved and 0 lots. |
| Same logic for LIVE, PAPER, BACKTEST | ✅ Implemented & working | Risk run in app engine before `execute_entry()` for LIVE/PAPER; backtest_engine uses same `RiskManager` and `validate_trade` (backtest_engine.py 106–114, 160–161). |

---

### G. Execution Modes

| Requirement | Status | File / function |
|-------------|--------|------------------|
| LIVE places real Zerodha orders | ✅ Implemented & working | `execution/executor.execute_entry` / `execute_exit` route to `live_executor.place_live_order` / `exit_live_trade`; `engine.zerodha_client.place_order`, `get_quote(tradingsymbol, exchange=exchange)`. |
| PAPER simulates with virtual balance | ✅ Implemented & working | `paper_executor.place_paper_trade`, `exit_paper_trade`; NFO uses `session["tradingsymbol"]` and `exchange="NFO"` for quotes; updates `session["virtual_balance"]` and risk-engine state including `daily_trade_count`. |
| BACKTEST simulates on historical candles | ✅ Implemented & working | BACKTEST sessions skipped in `_run_session_engine_tick` (2784–2786). Backtest via separate API/flow: `backtest/backtest_engine.run_backtest_engine()` with `BacktestDataProvider`, same strategy + RiskManager. |
| Mode switching does not change strategy logic | ✅ Implemented & working | Same `_check_entry_real`, `_manage_trade_real`, risk flow; only `execute_entry`/`execute_exit` branch by `session["execution_mode"]` (executor.py 28–35, 46–51). |

---

### H. Trade History & Alerts

| Requirement | Status | File / function |
|-------------|--------|------------------|
| Every closed trade written to trade_history | ✅ Implemented & working | `execution/trade_history_store.append_trade(record)` called from `paper_executor.exit_paper_trade` (102), `live_executor.exit_live_trade` (110). Backtest writes to backtest_results.json, not trade_history. |
| Records include strategy name, entry/exit price, PnL, mode | ✅ Implemented & working | e.g. paper_executor (90–101): `session_id`, `mode`, `symbol`, `strategy`, `entry_time`, `exit_time`, `entry_price`, `exit_price`, `qty`, `pnl`. live_executor same shape. |
| Alert/log when trade closes | ✅ Implemented & working | `logger.info("TRADE CLOSED | %s | P&L: %s", symbol, pnl)` in paper_executor (107), live_executor (115). |

---

## 2. Final verdict

### 1. Is Manual Mode production-ready?

**YES** — all items implemented. Index options exit now uses option premium (NFO LTP) for SL/target via `BaseStrategy._get_exit_ltp(trade)` and `data_provider.get_quote(symbol, exchange)`.

### 2. Blocking issues

- **None.** Previous blocker (NFO exit LTP) fixed in `base_strategy._get_exit_ltp` + strategy `check_exit` using it.

### 3. Non-blocking improvements

- Persisted sessions: consider filtering or expiring very old sessions on load so the list does not grow indefinitely.
- BACKTEST: currently not part of the “approve once, run all day” loop; it’s a separate run. Document that BACKTEST is on-demand only.
- Optional: add explicit “session stopped” log when cutoff_time or daily_loss_limit stops the session.

### 4. Realistic limitations (post–production-ready)

- Data latency (NSE/Zerodha), broker dependency (Zerodha), market hours.
- Strategy logic correctness (e.g. MomentumBreakout assumptions) and parameter tuning.

---

## 3. Summary

Manual Mode is **production-ready** for equity and index options in LIVE and PAPER. Session lifecycle, algo library, entry/exit (including NFO option premium for exit), continuous loop, risk manager, execution modes, and trade history are implemented and aligned with the design. BACKTEST remains on-demand only; no blocking issues.
