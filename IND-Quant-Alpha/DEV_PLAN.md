# IND-Quant-Alpha — Final Development Plan

**High-Conviction Intraday Automation Engine (INDmoney API + Python)**

---

## 1. Project Summary

A multi-factor algorithmic trading bot for NSE (Indian market) that **only trades when all of these align**:

| Pillar | Source | Role |
|--------|--------|------|
| **Technical** | NSE (INDstocks) | RSI, VWAP/EMA, EMA 9/15 cross |
| **Global bias** | S&P 500 (yfinance) | US close → bias for Indian open |
| **News sentiment** | News API + FinBERT/VADER | Filter/blacklist on bad news |

**Platform:** INDmoney (INDstocks API) — ₹5 per order.  
**Safety:** Backtest vs Live mode, max **3 trades/day**, **Kill Switch**, 1.5% SL / 3% TP.

---

## 2. Session & Live UX (Must-Have)

| Requirement | Behaviour |
|-------------|-----------|
| **Login** | User must log in to access the dashboard; no auto-start. |
| **Start trading** | Trading runs **only after** user clicks **"Start Trading"** (explicit opt-in each session). |
| **Real-time when live** | While trading is on: live prices, current signal, active positions, P&L, and status update every few seconds (polling or WebSocket). |
| **Auto-close** | System **automatically stops** trading and squares off (or stops new entries) by **2:30 PM IST** every day. |

- **Flow:** Login → Dashboard → Click **"Start Trading"** → Bot runs; dashboard shows **live** prices, signals, trades.  
- **By 2:30 PM IST:** Stop new trades, close/square off open positions (configurable), mark session ended.  
- **Next day:** User logs in again and clicks **"Start Trading"** to begin a new session.

---

## 3. System Architecture

```
User: Login → Click "Start Trading"
                    │
Global Data (S&P 500 / NASDAQ)  ──┐
Domestic Data (NSE / INDstocks) ──┼──► Strategy Engine ──► Backtest (CSV) or Live (INDstocks API)
News + Sentiment (FinBERT/VADER) ─┘                              │
                                                                  ▼
                    ◄──── Real-time updates (poll/WS) ──── Flask Dashboard + Telegram Alerts
                                                                  │
                    Auto-close at 2:30 PM IST ─────────────────────┘
```

---

## 4. Tech Stack (Unified)

| Layer | Technology |
|-------|------------|
| **Package manager** | **Poetry** (pyproject.toml, poetry.lock) |
| Web | Flask |
| US market | yfinance (^GSPC, $SPY) |
| India market / orders | INDstocks SDK (or REST) |
| Technicals | Pandas, TA-Lib |
| Sentiment | FinBERT (transformers) or VADER; TextBlob as fallback |
| Config | python-dotenv, `.env` |
| Real-time UI | Polling (e.g. every 5–10 s) or Flask-SocketIO (WebSocket) |
| Auth | Flask-Login or session-based login |

---

## 5. Directory Structure

```
ind_quant/                     # (renamed from kite/)
├── app.py                     # Flask server, routes, auth, Start/Stop, 2:30 scheduler, Settings
├── pyproject.toml             # Poetry: deps, scripts, Python version
├── poetry.lock                 # Lock file (commit)
├── .env                       # API keys (optional; can set in Dashboard → Settings)
├── config.json                 # Dashboard-saved API keys (do not commit)
├── engine/
│   ├── strategy.py            # Shared logic: consensus rules, signals
│   ├── data_fetcher.py        # yfinance (US), INDstocks (NSE)
│   ├── sentiment_engine.py    # News fetch + FinBERT/VADER scoring
│   ├── session_manager.py     # Trading on/off, 2:30 PM auto-close, trade count
│   └── config_store.py        # Load/save API keys from Settings
├── templates/
│   ├── login.html
│   ├── dashboard.html         # Start button, Settings link, real-time pane, mode, US bias, trades
│   └── settings.html          # API keys and app config form
└── (optional) alerts/         # Telegram notifier
```

---

## 6. Decision Engine (High-Conviction Rules)

A trade is allowed only when **all** of the following pass:

1. **Global bias (US → India)**  
   - At 9:00–9:15 AM IST: fetch S&P 500 previous close.  
   - If S&P down > 0.5%: **block all Long** for the first hour.  
   - If S&P up > 1%: **Bullish bias +1** for Indian longs.

2. **News sentiment**  
   - Fetch latest ~10 headlines for the symbol (News API / Google News).  
   - Score with FinBERT (preferred) or VADER.  
   - **Buy:** sentiment > 0.7 (or > 0.2 if using milder threshold).  
   - **Blacklist:** On strong negative (e.g. bad earnings, legal): skip symbol for 24 hours.

3. **Technical filter**  
   - RSI not overbought/oversold (e.g. RSI in 40–60 for neutral bias).  
   - Price near VWAP or EMA cross.  
   - EMA 9/15 cross as entry trigger where applicable.

4. **Execution guardrails**  
   - Max **3 trades per day**.  
   - **Stop-loss:** 1.5%. **Take-profit:** 3% (1:2 risk–reward).  
   - **Kill Switch:** Button/call to close all open positions immediately.  
   - **Auto-close:** No new trades after **2:30 PM IST**; square off or hold to SL/TP (configurable).

---

## 7. Implementation Phases

### Phase 1 — Environment & skeleton (Poetry)
- [ ] **Poetry:** `poetry init` (or existing `pyproject.toml`); set Python version (e.g. `^3.10`).
- [ ] **Dependencies** via `poetry add`: flask, pandas, yfinance, indstocks-sdk, ta-lib, python-dotenv, requests, transformers (FinBERT), vaderSentiment / textblob; dev: pytest, black (optional).
- [ ] **Run:** `poetry install` to create venv and install deps; use `poetry run python app.py` or `poetry shell` then `python app.py`.
- [ ] `.env.example`: `IND_API_KEY`, `IND_SECRET`, `STATIC_IP`, `NEWS_API_KEY`, `FLASK_ENV`, `TZ`, `AUTO_CLOSE_TIME`.
- [ ] Repo: no real `.env`, only template; document Static IP whitelist (ngrok/AWS EC2) for INDmoney.

**Poetry commands:** `poetry install` | `poetry add <pkg>` | `poetry run python app.py` | `poetry shell`

### Phase 2 — Data & global bias
- [ ] `engine/data_fetcher.py`:  
  - Fetch S&P 500 (e.g. ^GSPC) via yfinance.  
  - Fetch NSE OHLC/quote via INDstocks (or REST).
- [ ] In `engine/strategy.py`: compute **US bias** (e.g. +1 / 0 / -1) from S&P % change and expose for dashboard.

### Phase 3 — Sentiment engine
- [ ] `engine/sentiment_engine.py`:  
  - Fetch news (News API / Google News) for a given symbol.  
  - Score headlines with FinBERT or VADER.  
  - Return aggregate score and optional 24h blacklist flag.
- [ ] Integrate into strategy: skip or allow symbol based on sentiment and blacklist.

### Phase 4 — Strategy & signals
- [ ] In `engine/strategy.py`:  
  - Technical rules: RSI band, VWAP/EMA, EMA 9/15 cross.  
  - Combine US bias + sentiment + technicals → single BUY/SELL/HOLD.  
  - Enforce 3-trades-per-day and 1.5% SL / 3% TP in logic (and in execution layer later).

### Phase 5 — Backtest mode
- [ ] Historical 5-min (or 1-min) candles for selected symbol (e.g. RELIANCE, HDFCBANK).  
- [ ] Run strategy in backtest mode: log decisions to `results.csv` (no real orders).  
- [ ] Optional: simple metrics (win rate, max drawdown, Sharpe).

### Phase 6 — Login, session & dashboard
- [ ] **Login:** `templates/login.html`; protect dashboard so only logged-in users see it.  
- [ ] **Start Trading:** One prominent **"Start Trading"** button; trading loop runs only after user clicks it (session-scoped).  
- [ ] **Real-time when trading:**  
  - API route (e.g. `/api/live`) returning: current price(s), latest signal, active positions, P&L, status (RUNNING / STOPPED / AUTO_CLOSED).  
  - Dashboard polls every 5–10 seconds (or WebSocket) and updates: live price ticker, signal, positions table, P&L, “Trading active until 2:30 PM” countdown.  
- [ ] **2:30 PM IST auto-close:**  
  - Scheduler (e.g. `APScheduler` or cron) checks time in IST; at 2:30 PM: stop strategy loop, optionally square off all positions via API, set status to AUTO_CLOSED, stop real-time updates.  
- [ ] `app.py`: routes for login, dashboard, Start/Stop, Kill Switch, `/api/live`; integrate scheduler.  
- [ ] `engine/session_manager.py`: trading on/off flag, 2:30 logic, trade count.  
- [ ] `templates/dashboard.html`:  
  - Current mode (Backtest / Live), US bias, sentiment, today’s trades.  
  - **Start Trading** button (disabled when already running).  
  - **Real-time pane:** live prices, signal, positions, P&L, countdown to 2:30 PM.  
  - Panic Kill Switch (Live only).

### Phase 7 — Live execution (after backtest is validated)
- [ ] INDstocks order placement (e.g. `/order/place`).  
- [ ] Apply 1.5% SL / 3% TP and 3-trades-per-day in execution layer.  
- [ ] Kill Switch: endpoint that closes all open positions via API.

### Phase 8 — Alerts & hardening
- [ ] Optional: Telegram alerts for signals and executions.  
- [ ] Logging, error handling, and basic monitoring.  
- [ ] Deploy on VPS (e.g. AWS EC2) with Static IP for INDmoney whitelist.

---

## 8. Configuration (.env)

```env
IND_API_KEY=your_indmoney_api_key
IND_SECRET=your_indmoney_secret
STATIC_IP=your_whitelisted_ip
NEWS_API_KEY=your_news_api_key
FLASK_ENV=development
TZ=Asia/Kolkata
AUTO_CLOSE_TIME=14:30
```

- **TZ:** Use `Asia/Kolkata` so 2:30 PM is correct IST.  
- **AUTO_CLOSE_TIME:** Time (HH:MM) to stop trading and auto-close; default `14:30`.  
- Keep `.env` out of version control; commit only `.env.example`.

---

## 9. Backtest vs Live

| Aspect | Backtest | Live |
|--------|----------|------|
| Goal | Validate logic & risk | Real execution |
| Data | Historical candles | Real-time feed |
| Execution | Log to CSV | INDstocks `/order/place` |
| Cost | None | ₹5/order + STT/charges |

---

## 10. Risk & Constraints

- **Slippage:** Backtest does not model order-book depth.  
- **Latency:** Use VPS + Static IP for production.  
- **Capital:** Do not risk more than 10% of capital on new/unproven logic.  
- **Compliance:** Ensure INDmoney API usage and algo trading comply with local regulations.

---

## 11. Suggested First Steps

1. **Phase 1:** Use **Poetry**: `pyproject.toml`, `poetry install`, `.env.example`, and folder structure.  
2. **Phase 2:** Implement `data_fetcher.py` and US bias in `strategy.py`.  
3. **Phase 3:** Implement `sentiment_engine.py` and wire into strategy.  
4. **Phase 4:** Complete strategy rules and 3-trade / SL–TP logic.  
5. **Phase 5:** Backtest on one liquid symbol (e.g. RELIANCE or HDFCBANK).  
6. **Phase 6:** Build Flask dashboard and Kill Switch.  
7. **Phase 7–8:** Only after backtest looks good: Live execution + Telegram + VPS.

---

## 12. Success Criteria (Non-goals)

- **Not** “100% win rate” — aim for **high conviction** and **risk-adjusted returns** (e.g. Sharpe).  
- **Goal:** Fewer, higher-quality trades (max 3/day) with clear technical + sentiment + global alignment.

---

*Next: start with Phase 1 (environment + skeleton) and Phase 2 (data fetcher + US bias).*
