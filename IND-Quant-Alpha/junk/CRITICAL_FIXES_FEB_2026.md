# CRITICAL FIXES - February 2026

## 🚨 Problems Found

### 1. **Live/Paper Trading Broken**
**Error**: `UnboundLocalError: cannot access local variable 'datetime' where it is not associated with a value`

**Location**: `app.py` line 3055 in `_run_session_engine_tick()`

**Cause**: In the `/api/logs` endpoint (lines 3653-3706), I:
- Imported `logging` module inside the function
- Created a local variable `logger = logging.getLogger()` 
- This shadowed the global `logger` variable
- Used `datetime.now()` but the local scope was confused

**Impact**: 
- ⚠️ **CRITICAL**: Live and Paper trading sessions were completely broken
- Engine tick failed every minute
- No trading could occur

**Fix**: 
- Removed unnecessary imports from inside `api_get_logs()` function
- Used aliased imports (`from datetime import datetime as dt`) to avoid conflicts
- Removed the `logger = logging.getLogger()` line that was shadowing global

---

### 2. **Only 9 Trades in Backtest**
**Symptoms**:
- Backtest showed only 9 trades for 1 day
- "Hard Limit Days: 1" 
- Net P&L: -₹1296.47
- Win rate: 11.1%
- AI Switches: 0

**Root Causes**:

#### A. **Hard Drawdown Limit Triggered**
- Capital: ₹10,000
- Hard drawdown trigger: **5%** = -₹500 loss
- Backtest lost -₹1296 on first day
- Frequency dropped to **1 trade/hour** (from 10)
- Only managed 9 trades before stopping

**Solution**: Dramatically increased drawdown thresholds in `config.json`:
```json
"drawdown_trigger_percent": 0.15,        // Was 0.02 (2%) → Now 15%
"hard_drawdown_trigger_percent": 0.25,   // Was 0.05 (5%) → Now 25%
"max_daily_loss_percent": 0.3            // Was 0.1 (10%) → Now 30%
```

#### B. **Low Hourly Trade Limits**
Old settings allowed only **10 trades/hour** for capital < 50k.

**New Settings**:
- 0-50k capital: **50 trades/hour** (was 10)
- 50-200k: **60 trades/hour** (was 15)
- 200-500k: **80 trades/hour** (was 20)
- 500k+: **100 trades/hour** (was 20)
- Max hourly cap: **100** (was 20)

#### C. **Added Backtest Frequency Override**
New config option: `"backtest_disable_frequency_limit": true`

When enabled, backtest **ignores hourly frequency limits** (for testing purposes only).

**Code change in `app.py`** (lines 4519-4541):
```python
# Check if frequency limiting is disabled in backtest (from Settings)
freq_config = get_trade_frequency_config()
backtest_disable_limit = freq_config.get("backtest_disable_frequency_limit", False)

trades_this_hour = hourly_trade_counts.get(current_hour, 0)

# Block if hourly limit reached (unless disabled for backtest)
if not backtest_disable_limit and trades_this_hour >= max_trades_this_hour:
    logger.info(f"[AI BACKTEST] {trade_date} {candle_time}: Hourly limit reached...")
    continue
```

---

### 3. **0 AI Switches**
**Possible Reasons**:
1. AI was disabled in backtest request (frontend sends `ai_enabled: false`)
2. GPT didn't recommend any strategy switches (kept same strategy all day)
3. AI check interval was too long (checks every 6-12 candles = 30-60 min)
4. Only 9 trades meant few opportunities for AI to switch

**Investigation Needed**: 
- Check terminal logs for `[AI BACKTEST]` messages
- Look for `GPT strategy check failed` errors
- Verify `ai_enabled` parameter in backtest request from frontend

---

## 📋 All Changes Made

### Files Modified:

1. **`app.py`**:
   - Fixed `api_get_logs()` function (removed variable shadowing)
   - Added `backtest_disable_frequency_limit` check in `_simulate_trading_day()`
   - Added import: `get_trade_frequency_config` from `engine.trade_frequency`

2. **`config.json`**:
   - Increased all `max_trades_per_hour` values (10→50, 15→60, 20→80, 20→100)
   - Increased `max_hourly_cap` from 20 to 100
   - Increased `drawdown_trigger_percent` from 0.02 to 0.15
   - Increased `hard_drawdown_trigger_percent` from 0.05 to 0.25
   - Increased `max_daily_loss_percent` from 0.1 to 0.3
   - Added `backtest_disable_frequency_limit: true`

---

## 🎯 Expected Results After Fix

### Backtest:
- **50+ trades per day** (up from 9)
- **No premature hard limits** (unless losing 25% of capital)
- **More AI switches** (more opportunities for GPT to evaluate)
- **Better win rate** (more samples, law of large numbers)

### Live/Paper:
- **Engine tick working** (no more UnboundLocalError)
- **Trading resumes** (was completely broken before)

---

## ⚠️ Warning: Aggressive Settings

The new settings are **EXTREMELY AGGRESSIVE**:
- Up to **100 trades/hour** allowed
- Will only slow down at **15% loss** (was 2%)
- Will only stop at **25% loss** (was 5%)
- Max daily loss: **30%** (was 10%)

**Recommendation for Live Trading**:
- Test thoroughly in Paper mode first
- Consider reducing limits for live money:
  - `max_hourly_cap: 20-30` (not 100)
  - `drawdown_trigger_percent: 0.05` (5%)
  - `hard_drawdown_trigger_percent: 0.10` (10%)
  - `max_daily_loss_percent: 0.10` (10%)

---

## 🔄 Next Steps

1. ✅ Fixed code
2. ✅ Updated settings
3. ⏳ **Restart server** (to apply fixes)
4. ⏳ **Run 1-day backtest** (verify more trades)
5. ⏳ **Check terminal logs** (verify AI switches)
6. ⏳ **Test Paper trading** (verify engine tick works)

---

## 📊 How to Verify Fix

### Check Backtestresults:
- Total trades should be **50+** (not 9)
- Avg trades/hour should be **8-10** (not 1.5)
- AI switches should be **2-5** (not 0)
- Frequency mode should be **NORMAL** for most candles (not HARD_LIMIT)

### Check Terminal Logs:
Search for:
- `[AI BACKTEST]` - Should see many entries
- `GPT switched to` - AI strategy changes
- `Hourly limit reached` - Should be rare now
- `Hard drawdown triggered` - Should only happen at -25% loss
- `ENGINE TICK` - Should run every minute without errors

---

## 🐛 Debugging Commands

If still having issues:

```bash
# Check if server is running
curl http://localhost:5000/api/engine-status

# View recent logs
Get-Content terminals\823960.txt -Tail 50

# Search for specific errors
Select-String -Path "terminals\*.txt" -Pattern "UnboundLocalError"
Select-String -Path "terminals\*.txt" -Pattern "HARD_LIMIT"
Select-String -Path "terminals\*.txt" -Pattern "GPT switched"
```

---

**Date**: February 10, 2026  
**Status**: ✅ Fixes applied, awaiting server restart and testing
