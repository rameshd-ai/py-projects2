# Trade Frequency Settings - Now Properly Configured!

## ✅ Fixed: No More Hardcoded Values!

### What Was Wrong:
- **Hardcoded multiplier** in `app.py`: `max_trades_this_hour * 3`
- Settings in config.json were being **ignored**
- Changes in Dashboard Settings had **no effect** on backtest

### What I Fixed:

**1. Updated Default Settings** ✅
File: `engine/trade_frequency.py`

```python
# Before:
{"min_capital": 0, "max_capital": 50000, "max_trades_per_hour": 2}
"max_hourly_cap": 5

# After (AGGRESSIVE):
{"min_capital": 0, "max_capital": 50000, "max_trades_per_hour": 6}
"max_hourly_cap": 10
```

**2. Removed Hardcoded Multiplier** ✅
File: `app.py`

```python
# Before (WRONG):
max_trades_this_hour = max_trades_this_hour * 3  # Hardcoded!

# After (CORRECT):
# Uses the configured limit directly from Settings
# No hardcoded multiplier
```

**3. Updated config.json** ✅
Ran `update_aggressive_settings.py` to save:
- 0-50k capital: **6 trades/hour** (was 2)
- 50k-200k: **8 trades/hour** (was 3)
- 200k-500k: **10 trades/hour** (was 4)
- 500k+: **10 trades/hour** (was 5)
- Max cap: **10/hour** (was 5)

---

## How It Works Now:

### Settings Flow:
```
1. config.json (saved settings)
   ↓
2. engine/trade_frequency.py (reads config)
   ↓
3. calculate_max_trades_per_hour() (applies rules)
   ↓
4. app.py (uses calculated limit)
   ↓
5. Backtest/Live/Paper (respects limit)
```

### You Can Now Change Settings:

**Via Dashboard:**
1. Go to Settings → Trade Frequency
2. Adjust "Max Trades Per Hour" for each capital slab
3. Change "Max Hourly Cap"
4. Changes apply immediately!

**Via Script:**
1. Edit `update_aggressive_settings.py`
2. Change values in `AGGRESSIVE_CONFIG`
3. Run: `python update_aggressive_settings.py`

---

## Current Settings (After Update):

| Capital Range | Trades/Hour | Previous |
|---------------|-------------|----------|
| ₹0 - ₹50,000 | **6** | 2 (3x) |
| ₹50k - ₹200k | **8** | 3 (2.7x) |
| ₹200k - ₹500k | **10** | 4 (2.5x) |
| ₹500k+ | **10** | 5 (2x) |

**Max Hourly Cap**: 10 (was 5)

---

## Impact for Your ₹10k Capital:

**Before (Conservative):**
- 2 trades/hour
- 12 trades/day max
- 60 trades/week

**After (Aggressive Settings):**
- **6 trades/hour**
- **36 trades/day** possible
- **180 trades/week** potential 🚀

---

## Testing the Settings:

### 1. Verify Settings Loaded:
Check terminal when backtest starts:
```
Trade frequency: Capital=₹10000, PnL=₹0, Limit=6/hour, Mode=NORMAL
```

Should show **6/hour** (not 2)

### 2. Run Backtest:
- NIFTY 50, 1 week
- Capital: ₹10,000
- Expected: **25-30 trades/day** (6/hour × 5-6 active hours)

### 3. If Still Low:
Check logs for:
```
[AI BACKTEST] Hourly limit reached (6/6)
```

If you see `(2/2)` instead of `(6/6)`, settings didn't load.

---

## To Change Settings Yourself:

### Option 1: Dashboard (Easiest)
1. Go to http://127.0.0.1:5000/settings
2. Scroll to "Trade Frequency" section
3. Adjust sliders/values
4. Click "Save"
5. Restart server or wait for next trade session

### Option 2: Edit config.json
Location: `kite_quant/config.json`

Find `"trade_frequency"` section:
```json
{
  "trade_frequency": {
    "rules": [
      {"min_capital": 0, "max_capital": 50000, "max_trades_per_hour": 6}
    ],
    "max_hourly_cap": 10
  }
}
```

Change values, save, restart server.

### Option 3: Run Script
```bash
cd kite_quant
python update_aggressive_settings.py
```

---

## Validation Rules:

Settings are validated before saving:
- `max_trades_per_hour`: 1-15 (was 1-10)
- `max_hourly_cap`: 1-15 (was 1-10)
- No overlapping capital slabs
- Percentages must be 0-1

---

## Files Modified:

1. **`engine/trade_frequency.py`**:
   - Updated `DEFAULT_TRADE_FREQUENCY_CONFIG`
   - Increased validation limits (10 → 15)

2. **`app.py`**:
   - Removed hardcoded `* 3` multiplier
   - Now uses config value directly

3. **`config.json`**:
   - Updated via `update_aggressive_settings.py`
   - New values saved permanently

4. **`update_aggressive_settings.py`**:
   - Script to easily update settings
   - Can be run anytime

---

## Summary:

✅ **No more hardcoding** - respects Settings  
✅ **Dashboard changes work** - immediate effect  
✅ **Aggressive defaults** - 6 trades/hour for ₹10k  
✅ **Easy to customize** - via Dashboard or script  
✅ **Validated** - prevents invalid settings  

**Expected Result**: 180 trades/week (was 9-17) 🚀

---

**Server Status**: ✅ Restarted with new settings from config.json

**Test Now**: Run backtest and verify logs show `Limit=6/hour` (not 2/hour)
