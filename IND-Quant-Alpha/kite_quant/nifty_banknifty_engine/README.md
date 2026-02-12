# NIFTY / BANKNIFTY Engine

All **index-only** logic for NIFTY 50 and BANK NIFTY lives here. This keeps index backtest, paper trade, and live trade isolated so that:

- **Stocks** can be added later with their own engine/path without touching this code.
- **Single place** for index symbol mapping, live data, bias, options, and AI recommendations.

## Contents

| Module | Purpose |
|--------|--------|
| `constants` | NIFTY/BANKNIFTY names, NSE symbols, strike steps, lot sizes, `nse_symbol()`, `is_index_instrument()` |
| `live_data` | `fetch_nifty50_live()`, `fetch_bank_nifty_live()` (Zerodha + yfinance fallback) |
| `bias` | `get_index_market_bias()` – index bias scoring, cached 60s |
| `options` | `get_index_option_candidates()`, `pick_best_index_option()`, `get_affordable_index_options()` |
| `ai_recommendation` | `build_ai_trade_recommendation_index()` for NIFTY/BANKNIFTY AI cards |
| `backtest` | `run_index_backtest()` – thin wrapper over shared backtest engine for index only |

## Usage

- **App / API**: Import from `nifty_banknifty_engine` (e.g. `get_index_market_bias`, `build_ai_trade_recommendation_index`).  
- **Backtest engine / strategies**: Use `nifty_banknifty_engine.constants.nse_symbol` for NIFTY/BANKNIFTY symbol resolution.  
- **Stocks**: Do not use this package; use a separate stock engine or data path.
