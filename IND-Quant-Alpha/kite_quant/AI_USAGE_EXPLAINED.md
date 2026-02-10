# AI USAGE IN TRADING SYSTEM

## ✅ **YES, AI is Used - But Only for Strategy Switching**

### **What AI Does Currently:**

#### 1. **Strategy Auto-Switching** (Backtest, Live, Paper)
- **Frequency**: Every 5 minutes (configurable via `ai_check_interval_minutes`)
- **Purpose**: GPT analyzes market conditions and recommends which strategy to use
- **Input to GPT**:
  - Current NIFTY price & change %
  - Bank NIFTY price & change %
  - India VIX (volatility index)
  - Recent 10 candles (5-min timeframe)
  - Current time of day
  - Current strategy being used

- **Output from GPT**:
  - Recommended strategy (e.g., "Momentum Breakout", "RSI Reversal Fade")
  - Confidence level (low/medium/high)
  - Reasoning (why this strategy fits current market)
  - Market bias (bullish/bearish/neutral)

- **Code Location**:
  - Live/Paper: `app.py` lines 3109-3208 (inside `_run_session_engine_tick`)
  - Backtest: `app.py` lines 4409-4464 (inside `_simulate_trading_day`)

#### 2. **AI Check Intervals**

**Backtest**:
- Checks every **6 candles** (30 min) when NO position
- Checks every **12 candles** (60 min) when IN position
- More frequent when looking for entry

**Live/Paper**:
- Checks every **5 minutes** by default
- Configurable per session: `ai_check_interval_minutes`

---

### **What AI Does NOT Do:**

#### ❌ **Entry Decisions**
AI does NOT decide when to enter trades. Entry logic uses:
- **Unified entry function**: `engine/unified_entry.py`
- **Simple price action rules**: green/red candles, price moves > 0.1%
- **Strategy-agnostic**: Enters on almost every candle (very aggressive)

**Why?**
- GPT API calls are expensive (costs add up)
- GPT is slow (~2-5 seconds per call)
- Can't check every candle (75+ candles per hour)
- Real trading needs instant decisions

#### ❌ **Exit Decisions**
AI does NOT decide when to exit. Exit logic uses:
- **Stop loss** from strategy (e.g., 1% for Momentum Breakout)
- **Target** from strategy (e.g., 2% for Momentum Breakout)
- **Trailing stop loss** (moves up as price moves in profit)
- **End-of-Day exit** at 3:15 PM

#### ❌ **Position Sizing**
AI does NOT decide how much to trade. Position sizing uses:
- **Fixed risk %** (e.g., 2% of capital per trade)
- **Capital-based F&O lots** (centralized function)

#### ❌ **Trade Frequency**
AI does NOT decide how many trades to take. Frequency uses:
- **Dynamic hourly limits** based on capital (10-100 trades/hour)
- **Drawdown rules** (reduce frequency at -15%, stop at -25%)

---

## 🤔 **Why 0 AI Switches in Your Backtest?**

Possible reasons:

### 1. **AI Was Disabled**
Check if `ai_enabled: false` was sent in backtest request.

**How to verify**:
- Look for `[AI BACKTEST] GPT not available` in logs
- Check backtest request payload in browser DevTools

### 2. **Only 9 Trades = Few Opportunities**
With only 9 trades total:
- AI checks every 6-12 candles (30-60 min)
- Hard limit triggered early, stopped most trading
- Not enough time for AI to switch strategies

### 3. **GPT Kept Same Strategy**
GPT might have analyzed the market and decided:
- "Current strategy is optimal, don't switch"
- This is NORMAL if market conditions are stable

**Example GPT reasoning**:
> "Momentum Breakout is ideal for current bullish trend with moderate volatility. No switch needed."

### 4. **Low Confidence Threshold**
Code uses `min_confidence="medium"` (line 4440):
- Only switches if GPT is "medium" or "high" confidence
- If GPT returns "low" confidence, no switch happens

---

## 💡 **Should We Use AI for Entry/Exit Decisions?**

### **Option 1: Keep Current Approach** (Recommended)
✅ **Pros**:
- Fast execution (no API delays)
- Low cost (fewer GPT calls)
- Predictable behavior (rules-based)
- AI focuses on high-level strategy (what GPT is good at)

❌ **Cons**:
- Entry logic is simple (no deep market analysis)

### **Option 2: Add AI Entry Decisions**
💭 **How it would work**:
```
For each candle:
1. Check hourly frequency limit
2. If passed, call GPT: "Should I enter now? Why?"
3. Wait 2-5 seconds for response
4. If GPT says YES, enter trade
```

✅ **Pros**:
- More intelligent entry timing
- Better context awareness (news, market sentiment)

❌ **Cons**:
- **SLOW**: 2-5 seconds per GPT call × 75 candles/hour = 2.5-6 minutes of delays per hour
- **EXPENSIVE**: 50 trades/day × $0.01 per GPT call = $0.50/day = $10/month for backtest alone
- **Miss opportunities**: Price moves fast, 5-second delay can mean missed entry
- **Rate limits**: OpenAI limits requests (60/min for free tier)

---

## 📊 **Current AI Performance**

Since we can't see AI switches in your backtest, let's analyze what SHOULD happen:

### **Expected AI Behavior (1 Day Trading)**
- Trading hours: 9:15 AM - 3:15 PM = **6 hours = 360 minutes**
- AI checks every 30 min (on average) = **12 AI checks per day**
- Expected switches: **2-5 per day** (GPT doesn't switch unless conditions change)

### **Why Your Backtest Showed 0 Switches**
1. **Hard limit triggered early** → Only 9 trades → Trading stopped
2. **Not enough time** → AI needs at least 2-3 hours to see market changes
3. **Stable market** → GPT saw no reason to switch from Momentum Breakout

---

## 🎯 **Recommendations**

### **Immediate: Test with Higher Capital**
Run backtest with **₹50,000** instead of ₹10,000:
- Higher capital = more buffer before hard limit
- More trades = more AI checks
- Better visibility into AI switching behavior

### **Medium-term: Add AI Entry Signal** (Optional)
Instead of calling GPT on EVERY candle, call it:
- **After AI strategy switch** (get GPT's entry signal for new strategy)
- **Every 15 minutes** (get GPT's market bias: bullish/bearish/neutral)
- Use this as a **filter** on top of technical entry signals

**Example**:
```python
if technical_signal == "enter" and ai_market_bias == "bullish":
    enter_trade()
```

### **Long-term: Hybrid Approach** (Best)
1. **AI for strategy selection** (current - keep this)
2. **Technical indicators for entry timing** (current - keep this)
3. **AI for position sizing** (new - ask GPT: "How confident? 1x or 2x size?")
4. **AI for early exit** (new - ask GPT: "Market changed? Exit before stop loss?")

---

## 📝 **How to Verify AI is Working**

### **Check Terminal Logs**:
```bash
# Search for AI decision logs
Select-String -Path "terminals\*.txt" -Pattern "\[AI BACKTEST\] GPT"
Select-String -Path "terminals\*.txt" -Pattern "GPT switched to"
Select-String -Path "terminals\*.txt" -Pattern "AI STRATEGY EVALUATION"
```

### **Expected Log Output**:
```
[AI BACKTEST] 2026-02-05 10:15: GPT switched to RSI Reversal Fade (confidence: high)
[AI BACKTEST] GPT reasoning: Market showing signs of exhaustion after strong rally, VIX rising...
```

### **If You See**:
- `GPT not available` → OpenAI API key issue
- `GPT strategy check failed` → Network or API error
- Nothing → AI was disabled in request

---

## ⚙️ **Current AI Settings**

**Backtest**:
- `ai_enabled`: `true` (default)
- `ai_check_interval`: Every 6-12 candles (30-60 min)
- `min_confidence`: "medium" (only switches if GPT is confident)

**Live/Paper**:
- `ai_auto_switching_enabled`: Must be enabled per session
- `ai_check_interval_minutes`: 5 minutes (default)

---

**Summary**: AI is used for **strategy switching only**, not entry/exit. This is a good balance of intelligence and speed. Your 0 AI switches were likely due to the backtest hitting hard limit early (only 9 trades) and not giving AI enough time to analyze market changes.

**Next Steps**: 
1. Run a FULL DAY backtest with new settings (should get 50+ trades)
2. Check logs for `[AI BACKTEST] GPT switched to` messages
3. If still 0 switches, check if AI was enabled in request
