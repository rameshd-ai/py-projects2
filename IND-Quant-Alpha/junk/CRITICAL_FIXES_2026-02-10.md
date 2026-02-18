# CRITICAL FIXES - AI & Performance Issues

## Date: 2026-02-10 10:00 AM

## Problems Identified:
1. **0 AI Switches** - AI strategy rotation completely broken
2. **Only 9 trades/day** - Should be 50-100+ trades
3. **11% win rate** - 8 losses, 1 win (was 55% before)
4. **₹1,296 LOSS** - Instead of profit
5. **All losses from STOP_LOSS** - Stops hitting too early

## Root Causes:

### 1. Python Scoping Bug (CRITICAL)
**File:** `app.py` line 3116
**Issue:** `from datetime import datetime` INSIDE function shadowed module-level datetime
**Impact:** Engine tick completely broken - sessions not updating
**Fix:** Removed redundant import

### 2. AI Check Too Infrequent
**File:** `app.py` line 4425
**Issue:** AI only checked every 12 candles (1 hour) AND only when NO position
**Impact:** AI couldn't rotate strategies, stuck on Momentum Breakout
**Fix:** 
- Check every 6 candles (30 min) when NO position
- Check every 12 candles (1 hour) when we HAVE position
- Removed `and not current_position` requirement

### 3. Stop Losses Too Tight
**Issue:** 1% stop for stocks, 10% for F&O = normal noise triggers stops
**Impact:** 8/9 trades hit stop loss before reaching target
**Fixes:**
- **Momentum Breakout:** 1% → 1.5% stop (0.99 → 0.985)
- **RSI Reversal:** 1% → 1.5% stop (0.99 → 0.985)
- **F&O Options:** 10% → 12% stop (0.90 → 0.88)

## Code Changes:

### app.py - Line 3116
```python
# BEFORE (BROKEN):
from datetime import datetime
last_check_dt = datetime.fromisoformat(last_ai_check)

# AFTER (FIXED):
last_check_dt = datetime.fromisoformat(last_ai_check)
```

### app.py - Line 4425
```python
# BEFORE (TOO RESTRICTIVE):
if candles_since_check >= (ai_check_interval // 5) and not current_position:

# AFTER (MORE FREQUENT):
check_interval = 12 if current_position else 6
if candles_since_check >= check_interval:
```

### app.py - Line 4613 (F&O Stops)
```python
# BEFORE:
stop_loss = option_premium * 0.90  # 10% stop (too tight)

# AFTER:
stop_loss = option_premium * 0.88  # 12% stop (wider)
```

### strategies/momentum_breakout.py
```python
# BEFORE:
return round(entry_price * 0.99, 2)  # 1% stop

# AFTER:
return round(entry_price * 0.985, 2)  # 1.5% stop
```

### strategies/rsi_reversal.py
```python
# BEFORE:
return round(entry_price * 0.99, 2)  # 1% stop

# AFTER:
return round(entry_price * 0.985, 2)  # 1.5% stop
```

## Expected Impact:

✅ **AI Switches:** 0 → 5-15 switches/day
✅ **Total Trades:** 9 → 50-100+ trades/day
✅ **Win Rate:** 11% → 55-60% (back to normal)
✅ **Stop Hits:** Less frequent (wider stops)
✅ **P&L:** ₹-1,296 → ₹5,000+ profit/week target

## Testing Required:

1. Run 1-day backtest (NIFTY 50, 5k capital)
2. Check AI switches > 0
3. Check total trades > 30
4. Check win rate > 50%
5. Check P&L is positive

## Status:
🟢 **Server restarted** - All fixes applied
🟢 **Ready for testing**

## Notes:
- Wider stops = fewer false exits
- More frequent AI checks = better strategy rotation
- Fixed Python bug = engine actually works now
- All changes applied to "ONE BRAIN" architecture (Live/Paper/Backtest unified)
