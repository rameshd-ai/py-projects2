# Backtesting Frequency Update

## Problem
Backtesting page had a confusing "Max Trades/Day (Failsafe)" input field that made it seem like backtest used different logic than Paper/Live trading.

## Solution
**Removed the manual "Max Trades/Day" input** and updated UI to clearly show that backtesting uses the **exact same Trade Frequency settings** as Paper and Live trading.

---

## Changes Made

### 1. **Removed "Max Trades/Day" Input Field**
- The confusing input that allowed manually setting a daily trade limit is now gone
- Backend still has a high failsafe (50 trades/day) but it's not user-configurable

### 2. **Added Clear Info Box**
```
Dynamic Trade Frequency: Backtest uses the same frequency settings from 
Settings → Trade Frequency. Trades per hour adjust based on capital and 
drawdown during simulation.
```

### 3. **Live Frequency Estimation**
- When you change the "Investment Amount", the UI now shows:
  - ₹10,000 → 2 trades/hour
  - ₹50,000 → 3 trades/hour
  - ₹2,00,000 → 4 trades/hour
  - ₹5,00,000+ → 5 trades/hour

### 4. **Clear Explanation**
Added bullet points explaining:
- Uses dynamic hourly frequency from Trade Frequency settings
- Shows estimated trades/hour based on capital
- Explains drawdown logic (2% → REDUCED, 5% → HARD_LIMIT)
- Hourly counter resets behavior
- **Same logic as Paper/Live trading**

---

## How Backtest Works Now

1. **Capital-Based Frequency**: Investment amount determines base trades/hour (same as Settings)
2. **Drawdown Protection**: If daily P&L drops 2% → REDUCED, 5% → HARD_LIMIT (1/hour max)
3. **Hourly Reset**: Counter resets every hour (10am, 11am, 12pm, etc.)
4. **Consistent Logic**: Identical to Paper and Live trading modes

---

## User Benefits

✅ **No Confusion**: One place to configure frequency (Settings → Trade Frequency)  
✅ **Consistency**: Backtest behaves exactly like Paper/Live trading  
✅ **Real-World Testing**: Test with the same frequency rules you'll use live  
✅ **Clear UI**: Shows estimated frequency right on the backtest page  
✅ **Smart Defaults**: High failsafe in backend, but real control is dynamic  

---

## Configuration Location

All frequency rules are configured in:
```
Settings → Trade Frequency Tab
```

Configure:
- Capital slabs (min/max capital → trades/hour)
- Max hourly cap (default: 5)
- Drawdown trigger % (default: 2%)
- Hard drawdown trigger % (default: 5%)
- Drawdown reduction % (default: 50%)

These settings apply to **ALL modes**: Paper, Live, and Backtest.

---

## Technical Note

The backend `_simulate_trading_day()` function already used dynamic frequency logic. 
This update only removed the confusing UI input and added clear documentation about how it works.

**File Changed**: `kite_quant/templates/dashboard/backtest.html`
