# Kite Quant

High-conviction intraday automation engine: Zerodha Kite Connect + Python.

## Setup

1. **Poetry**
   ```bash
   cd ind_quant
   poetry install
   ```

2. **Environment** (optional — you can set everything in the dashboard)
   ```bash
   cp .env.example .env
   # Or: log in → Dashboard → Settings → enter API keys and save
   ```

3. **Run**
   ```bash
   poetry run python app.py
   ```
   Open http://localhost:5000 → Login (demo: `admin` / `admin`) → Dashboard → **Settings** to set API keys → **Start Trading**.

## Settings (Dashboard)

All API keys and app config can be set from the app:

- **Dashboard** → **Settings**
- Set: Zerodha API Key, Zerodha API Secret, Zerodha Access Token, News API Key, Flask Secret Key, Flask Env, Timezone, Auto-close time (HH:MM)
- Values are stored in `config.json` and override `.env`; leave a field blank to keep the current value.

## Features

- **Login** — No auto-start; user must log in and click **Start Trading**.
- **Real-time** — Dashboard polls `/api/live` every 8s: price, US bias, sentiment, positions, P&L, countdown to 2:30 PM IST.
- **Auto-close** — At 2:30 PM IST (or time set in Settings) trading stops; no new trades.
- **Kill Switch** — Closes all open positions (Live mode).
- **Backtest** — Historical run → `results.csv`; no real orders.
- **Guards** — Max 3 trades/day, 1.5% SL, 3% TP.

## Zerodha Kite Connect API

Use [Zerodha Kite Connect](https://kite.trade/) for live trading. Get API credentials from [Kite Connect Apps](https://kite.trade/apps/). The system uses `kiteconnect` Python library for all trading operations.
