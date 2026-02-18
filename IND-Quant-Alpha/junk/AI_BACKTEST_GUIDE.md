# 🤖 AI-Powered Backtesting System

**Status:** ✅ FULLY IMPLEMENTED  
**Last Updated:** 2026-02-09

---

## Overview

The AI-Powered Backtesting System simulates **real intraday trading** with **AI strategy auto-switching**. It replicates exactly how Manual Mode works - entering at 9:30 AM, evaluating strategies every 5 minutes, switching when AI recommends, and tracking daily P&L.

---

## ✨ Key Features

### 1. **Stock Search with Autocomplete** 
- Type to search from 18+ popular stocks
- Supports NIFTY 50, BANK NIFTY, and major NSE stocks
- Instant suggestions as you type

### 2. **Quick Time Period Selection**
- **1 Day** - Test single day performance
- **1 Week** (5 trading days) - Short-term validation
- **1 Month** (21 trading days) - Medium-term testing
- **3 Months** (63 days) - Quarter performance
- **6 Months** (126 days) - Half-year analysis
- **1 Year** (252 days) - Full year backtesting
- **Custom** - Select any date range

### 3. **AI Auto-Switching** 🤖
- **Enabled by default**
- AI analyzes market conditions every 5 minutes
- Automatically switches to optimal strategy
- Tracks and displays all strategy changes
- Shows which strategies were used each day

### 4. **Investment & Risk Controls**
- **Investment Amount**: Starting capital (₹10,000 default)
- **Max Loss Limit**: Auto-stop if loss exceeds this (₹2,000 default)
- **Max Trades Per Day**: Limits overtrading (10 default = 5 buy + 5 sell)
- **Risk Per Trade**: Percentage of capital risked per trade (2% default)

### 5. **Comprehensive Results**

#### Summary Metrics:
- Net P&L (profit/loss)
- Total trades executed
- Win rate percentage
- Best day profit
- Worst day loss
- Total AI strategy switches

#### Daily Breakdown Table:
- Date
- Number of trades
- Wins vs Losses
- Daily P&L
- Cumulative P&L
- Strategies used that day
- AI switches count

#### All Trades Table:
- Date and strategy
- Entry and exit times
- Entry and exit prices
- Quantity traded
- P&L per trade
- Exit reason (STOP_LOSS, TARGET, DAY_END)

### 6. **Export to CSV**
- Download complete trading history
- Includes all trades with full details
- Ready for Excel/Sheets analysis

---

## 🚀 How to Use

### Step 1: Configure Backtest

1. **Go to Backtesting page**
   - Navigate to Dashboard > Backtesting

2. **Select Stock**
   - Type stock name or symbol in search box
   - Example: "RELIANCE", "NIFTY", "HDFCBANK"

3. **Choose Time Period**
   - Click quick selector: 1 Day, 1 Week, 1 Month, etc.
   - OR click "Custom" for specific date range

4. **Set Investment Parameters**
   - Investment Amount: How much capital to start with
   - Max Loss Limit: Maximum loss before stopping
   - Max Trades Per Day: Trading frequency limit
   - Risk Per Trade %: Risk per position

5. **Enable/Disable AI** (Optional)
   - Toggle "Enable AI Auto-Switching"
   - When ON: AI picks strategies automatically
   - When OFF: Uses single fixed strategy

### Step 2: Run Backtest

1. Click **"Run AI-Powered Backtest"**
2. Wait for processing (may take 1-2 minutes)
3. Progress bar shows status

### Step 3: Review Results

1. **Check Summary Metrics**
   - Did you make profit?
   - What's the win rate?
   - Which was best/worst day?

2. **Review Daily Breakdown**
   - See P&L day by day
   - Track cumulative profit
   - Identify which strategies worked

3. **Analyze All Trades**
   - Review each trade's entry/exit
   - Understand exit reasons
   - Find patterns in wins/losses

4. **Export Data** (Optional)
   - Click "Export CSV"
   - Analyze in Excel/Google Sheets
   - Create custom charts

---

## 💡 Example Scenarios

### Scenario 1: Test NIFTY for 1 Week with AI

**Settings:**
- Stock: NIFTY
- Period: 1 Week (5 days)
- Investment: ₹10,000
- Max Loss: ₹2,000
- Max Trades/Day: 10
- AI: ON

**What Happens:**
1. **Day 1 (Monday):**
   - 9:30 AM: Market opens, AI selects "Momentum Breakout"
   - 9:45 AM: AI switches to "VWAP Trend Ride" (trend detected)
   - Trades: 3, P&L: +₹150

2. **Day 2 (Tuesday):**
   - 9:30 AM: Starts with last strategy "VWAP Trend Ride"
   - 10:15 AM: AI switches to "RSI Reversal" (ranging market)
   - Trades: 5, P&L: -₹80

3. **... continues for 5 days**

**Result:**
- Net P&L: +₹450
- Win Rate: 65%
- AI Switches: 8 times across 5 days
- Best Day: +₹200 (Wednesday)

### Scenario 2: Test RELIANCE for 1 Month (Fixed Strategy)

**Settings:**
- Stock: RELIANCE
- Period: 1 Month (21 days)
- Investment: ₹50,000
- Max Loss: ₹10,000
- Max Trades/Day: 10
- AI: OFF
- Strategy: Pullback Continuation

**What Happens:**
- Uses **only** "Pullback Continuation" for all 21 days
- No strategy switching
- Pure strategy performance test

**Result:**
- Net P&L: +₹2,350
- Win Rate: 58%
- Consistency test for single strategy

---

## 🎯 How It Works (Technical)

### Day-by-Day Simulation

For each trading day:

1. **Fetch Historical Data**
   - Gets 5-minute candles for that day
   - Covers 9:15 AM to 3:15 PM

2. **Simulate Market Open (9:30 AM)**
   - Initialize with starting strategy
   - Set daily trade limit
   - Reset AI check timer

3. **Every 5 Minutes (per candle):**
   - **AI Evaluation** (if enabled and interval reached):
     - Analyze last 10 candles
     - Evaluate trend, momentum, volatility
     - Decide if strategy switch needed
     - Track switch count
   
   - **Position Management** (if in trade):
     - Check if stop loss hit → Exit
     - Check if target hit → Exit
     - Calculate P&L
   
   - **Entry Signal** (if no position):
     - Check current strategy conditions
     - If conditions met → Enter trade
     - Calculate stop loss & target
     - Track position

4. **Market Close (3:15 PM)**
   - Force exit any open positions
   - Calculate day's P&L
   - Update capital
   - Record daily summary

5. **Risk Checks**
   - If max trades reached → Stop for day
   - If max loss exceeded → Stop backtest
   - Capital preserved

### AI Decision Logic

When AI is enabled:

```python
Every 5 minutes:
  1. Get last 10 candles
  2. Calculate trend (bullish/bearish/neutral)
  3. Calculate volatility (high/low)
  4. Determine optimal strategy:
     - Bullish trend → Momentum Breakout
     - Bearish trend → Pullback Continuation
     - Ranging → RSI Reversal
     - High volatility → News Volatility Burst
  5. If different from current → Switch
  6. Track switch count
```

### Entry/Exit Logic (Simplified for Backtest)

**Entry Conditions:**
- Last 3 candles are green (uptrend)
- Not exceeding max trades
- Have available capital

**Exit Conditions:**
- Stop Loss: -2% from entry
- Target: +4% from entry
- Day End: 3:15 PM force close

---

## 📊 Understanding Results

### Win Rate
- **> 60%**: Excellent strategy performance
- **50-60%**: Good, profitable if R:R is good
- **< 50%**: Strategy needs improvement

### Best/Worst Day
- Shows volatility of returns
- Large gaps indicate inconsistent strategy
- Smaller gaps = more stable performance

### AI Switches
- **0-5 switches/day**: Conservative, stable
- **5-10 switches/day**: Active adaptation
- **> 10 switches/day**: Over-switching, may indicate indecision

### Daily Breakdown Insights
- **Consistent green days**: Good strategy
- **Alternating green/red**: Market-dependent
- **Consecutive red days**: Strategy not suited for period

---

## ⚙️ Configuration Tips

### For Day Trading:
```
Investment: ₹10,000
Max Loss: ₹1,500 (15%)
Max Trades: 8-10
Risk %: 2%
Period: 1 Week
```

### For Swing Trading:
```
Investment: ₹50,000
Max Loss: ₹7,500 (15%)
Max Trades: 5-6
Risk %: 3%
Period: 1 Month+
```

### For Conservative Testing:
```
Investment: ₹25,000
Max Loss: ₹2,500 (10%)
Max Trades: 5
Risk %: 1.5%
Period: 2 Weeks
```

### For Aggressive Testing:
```
Investment: ₹10,000
Max Loss: ₹3,000 (30%)
Max Trades: 15
Risk %: 3%
Period: 1 Week
```

---

## 🚨 Important Notes

### 1. **Past Performance ≠ Future Results**
- Backtest shows historical performance
- Market conditions change
- Use as guidance, not guarantee

### 2. **Simplified Logic**
- Backtest uses simplified entry/exit rules
- Real trading has more complex conditions
- Results may vary in live trading

### 3. **Data Availability**
- Limited by historical data from Zerodha
- Older dates may have limited data
- Weekends/holidays are skipped

### 4. **Processing Time**
- 1 Day: ~5 seconds
- 1 Week: ~20 seconds
- 1 Month: ~1 minute
- 1 Year: ~5 minutes

### 5. **Max Loss Protection**
- Backtest stops if max loss hit
- Protects capital in simulation
- Same safety as live trading

---

## 📈 Next Steps After Backtesting

### If Results Are Positive:
1. ✅ Test with PAPER mode (simulated orders)
2. ✅ Verify AI switching behavior matches expectations
3. ✅ Start with small capital in LIVE mode
4. ✅ Monitor closely for first week
5. ✅ Scale up gradually

### If Results Are Negative:
1. ❌ Don't proceed to live trading
2. 🔄 Try different time period
3. 🔄 Test different stock
4. 🔄 Adjust risk parameters
5. 🔄 Consider disabling AI and using fixed strategy

---

## 🎓 Learning from Backtest

### Questions to Ask:
1. **Which strategies performed best?**
   - Look at daily breakdown
   - See which strategies had green days

2. **When did losses occur?**
   - Identify patterns
   - Certain times of day?
   - Specific market conditions?

3. **How many AI switches were optimal?**
   - Too many = indecision
   - Too few = missing opportunities
   - Find balance

4. **Is win rate consistent?**
   - Stable across days?
   - Or just 1-2 lucky days?

5. **Can I replicate this?**
   - Are conditions reproducible?
   - Or was it a unique market period?

---

## 🔧 Troubleshooting

### "Insufficient data" Error
- **Cause**: Selected dates have no trading data
- **Fix**: Choose more recent dates or different stock

### "Request failed" Error
- **Cause**: Server issue or network problem
- **Fix**: Refresh page and try again

### Backtest Takes Too Long
- **Cause**: Long time period (6+ months)
- **Fix**: Test shorter periods or be patient

### Results Show "0 trades"
- **Cause**: Entry conditions never met
- **Fix**: Check if stock had movement in that period

### Max Loss Hit Early
- **Cause**: Volatile period or tight max loss
- **Fix**: Increase max loss limit or test different period

---

## 📁 Files Modified

### Frontend:
- `templates/dashboard/backtest.html` - Complete UI redesign

### Backend:
- `app.py` - New `/api/backtest/run-ai` endpoint
- Added `_run_ai_backtest()` function
- Added `_simulate_trading_day()` function

---

## 🎉 Summary

**The AI-Powered Backtesting System allows you to:**

✅ Test strategies on historical data  
✅ Simulate AI auto-switching behavior  
✅ See day-by-day performance breakdown  
✅ Control risk with max loss limits  
✅ Export results for detailed analysis  
✅ Make informed decisions before live trading  

**Test smart. Trade smarter.** 🚀

---

*Last Updated: 2026-02-09*
