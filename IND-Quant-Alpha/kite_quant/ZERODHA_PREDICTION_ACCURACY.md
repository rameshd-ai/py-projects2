# Using Zerodha API for More Accurate Day Predictions

With Zerodha connected, the app can use **exchange-quality data** and **live indices** to improve daily direction (BULLISH/BEARISH/NEUTRAL). Here’s what is in place and what you can do next.

---

## How today’s market prediction is calculated

Today’s prediction (BULLISH / BEARISH / NEUTRAL) is a **single score** from many factors. All of the below are used when available:

| # | Factor | Weight / Effect | When used |
|---|--------|-----------------|-----------|
| 1 | **US market bias** | 40% | Always. S&P 500 previous close: up >1% → bullish, down >0.5% → bearish, else neutral. |
| 2 | **News / sentiment** | 30% | Always. Headlines for the stock are fetched (News API), then scored (FinBERT/TextBlob). Positive → +0.3, negative → -0.3, else neutral. |
| 3 | **Technicals (RSI + EMA)** | 30% | Always. 60-day OHLC from Zerodha (or yfinance). RSI >60 → +0.15, &lt;40 → -0.15; EMA 9/15 cross up/down → ±0.15. |
| 4 | **Nifty & Bank Nifty** | ~5% | Always (live). Both up >0.3% → +0.05; both down >0.3% → -0.05. |
| 5 | **India VIX** | Modifier | Always. If VIX > 18: “High VIX: cautious” factor and **confidence capped at 72**. |
| 6 | **Price vs today’s open** | ~3% | **Only when Indian market is open.** Current price vs stored open: above → +0.03, below → -0.03. |
| 7 | **Market depth (bid–ask)** | ~2% | **Only when Indian market is open.** Zerodha depth: bid bias → +0.02, ask bias → -0.02. |
| 8 | **First 15 min Indian trend** | ~2% | **Only when Indian market is open.** Zerodha 15m candle: first 15m close vs open; up >0.15% → +0.02, down → -0.02. |

- **Score** is the sum of these contributions. If **score > 0.2** → BULLISH, **&lt; -0.2** → BEARISH, else NEUTRAL.
- **Confidence** is derived from the score; it is then **capped at 72** when VIX is high.

So yes: **first 15 min Indian trend + news/sentiment + US bias** (plus technicals, indices, VIX, price vs open, and depth) are all used. The 15m and other intraday factors apply only **during market hours** (9:15 AM–3:30 PM IST).

---

## What’s Already Implemented

### 1. **Zerodha historical data for technicals**
- When Zerodha is connected, the prediction engine uses **Zerodha’s historical OHLC** (60 days, daily) for RSI and EMA instead of only yfinance.
- Zerodha data is from the exchange, so it’s more reliable for Indian names and avoids yfinance delays/mismatches.
- If Zerodha fails or isn’t connected, it falls back to yfinance (60 days) so technicals still run.

### 2. **Index alignment factor**
- **Nifty 50** and **Bank Nifty** live % change are used as an extra factor.
- If both indices are up (>0.3%), a small **bullish** bias is added; if both are down (<-0.3%), a small **bearish** bias is added.
- This aligns the stock prediction with broad market direction.

### 3. **Live quote for prices**
- Your dashboard and accuracy logic already use **Zerodha live quote** (when connected) for the selected stock’s LTP and today’s OHLC via `fetch_nse_quote` → `zerodha_client.get_quote`.
- So “actual” direction and P&L use live Zerodha prices when available.

---

## Prediction Weights (Summary)

| Factor            | Weight | Data source when Zerodha connected      |
|-------------------|--------|-----------------------------------------|
| US market bias    | 40%    | yfinance (S&P 500)                      |
| Sentiment         | 30%    | Sentiment engine                       |
| Technicals (RSI/EMA) | 30% | **Zerodha historical** (60d) or yfinance |
| Nifty + Bank Nifty| ~5%    | yfinance (live indices)                |

---

## Implemented Accuracy Improvements

1. **Pre-market / opening range (Zerodha)** ✅  
   - **Today’s open** is stored in `opening_range.json` when the first quote is received after 9:15 AM.  
   - During the day, **“price vs open”** is used as an intraday factor: above open → small bullish bias (+0.03), below → small bearish bias (-0.03).

2. **Zerodha for index quotes** ✅  
   - Nifty 50 and Bank Nifty already use Zerodha first (`NSE:NIFTY 50`, `NSE:NIFTY BANK`) when connected; yfinance is fallback.

3. **India VIX in model** ✅  
   - **High VIX** (>18): a “High VIX: cautious” factor is added and **confidence is capped at 72** so the prediction is treated as less reliable.

4. **Market depth** ✅  
   - Zerodha quote returns **buy_quantity** and **sell_quantity** (from depth).  
   - **Bid–ask imbalance** is used: bid bias → +0.02, ask bias → -0.02 (when imbalance > 10%).

5. **Intraday 15m trend (Zerodha)** ✅  
   - When the market is open, Zerodha **15m candles** for the day are fetched.  
   - **First 15m candle** close vs open: if up >0.15% → “Intraday 15m: bullish” (+0.02), if down → “Intraday 15m: bearish” (-0.02).

6. **Consistent token**  
   - Generate the Zerodha token daily (or use the in-app flow). Predictions and live data are more accurate when the API is connected and not expired.

---

## Quick checklist

- [x] Zerodha historical used for RSI/EMA when connected  
- [x] 60-day history so technicals (e.g. RSI 14) are valid  
- [x] Nifty & Bank Nifty alignment factor (Zerodha-first)  
- [x] Live quote from Zerodha for selected stock (price/accuracy)  
- [x] Opening range stored; price-vs-open intraday factor  
- [x] India VIX in model (high VIX → cautious, confidence cap)  
- [x] Market depth (bid-ask imbalance) from Zerodha quote  
- [x] Intraday 15m trend factor from Zerodha
