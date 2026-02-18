# Capital-Based Position Sizing - Implementation Summary

## Problem
Previously, all modes (Live, Paper, Backtest) forced a minimum of 1 lot regardless of capital, making Rs.5,000 and Rs.10,000 produce identical results.

## Solution Applied to All 3 Modes

### 1. F&O Position Sizing (30% of Capital Rule)
```python
# Use up to 30% of capital for F&O positions
max_position_value = capital * 0.30
cost_per_lot = premium * lot_size
affordable_lots = int(max_position_value / cost_per_lot)

# Only trade if can afford at least 1 lot
if affordable_lots < 1:
    return None  # Skip trade
```

### 2. Premium Floor Adjustment
- **Before**: Rs.20 floor (unrealistically cheap)
- **After**: Rs.50 floor (more realistic for ATM options)

### 3. No Forced Minimum
- **Before**: `lots = max(1, calculated_lots)` - Always trades at least 1 lot
- **After**: `lots = calculated_lots` - Only trades if capital is sufficient

## Files Modified

### 1. `app.py` - Recommendation Building (Live/Paper)
- **Line 2664-2682**: `_build_ai_trade_recommendation_index()`
  - Uses 30% of capital for position sizing
  - Returns `None` if insufficient capital (< 1 lot)

### 2. `app.py` - Option Premium Calculation
- **Line 2465-2467**: `get_affordable_index_options()`
  - Increased premium floor from Rs.20 to Rs.50

### 3. `app.py` - Trade Execution (Live/Paper)
- **Line 3268-3272**: `_run_session_engine_tick()`
  - Checks `lots < 1` before executing
  - Removed `max(1, lots * lot_size)` forcing

### 4. `app.py` - Backtesting
- **Line 3962-3997**: Daily F&O recommendation
  - Uses 30% capital rule
  - Skips day if insufficient capital
- **Line 4214-4245**: Entry execution
  - Uses 30% capital for lots calculation
  - Skips entry if can't afford 1 lot

### 5. `risk_manager.py` - Position Sizing Logic
- **Line 29-55**: `calculate_position_size()`
  - F&O (lot_size > 1): 30% of capital
  - Stocks (lot_size = 1): Risk-based with stop loss
- **Line 55-58**: `can_afford_trade()`
  - Checks against 30% of capital (not full capital)

## Results

### Before Fix
```
Rs.5,000:  Same trades as Rs.10,000 (forced 1 lot minimum)
Rs.10,000: Same trades as Rs.5,000 (forced 1 lot minimum)
```

### After Fix
```
Rs.5,000:  0 trades (insufficient for NIFTY F&O @ Rs.3,000/lot)
Rs.10,000: 5 trades with 1 lot each (can afford 1 lot @ Rs.3,000)
Rs.20,000: Would trade 2 lots (can afford 2 lots @ Rs.6,000)
```

## Key Benefits

1. **Realistic Capital Constraints**: Small capital may skip F&O trading entirely
2. **Proper Scaling**: Larger capital → more lots → larger P&L
3. **Consistent Across Modes**: Live, Paper, and Backtest all use same logic
4. **Risk Management**: Only uses 30% of capital per position (keeps 70% in reserve)

## Testing

Run backtests with different capital amounts to verify:
```bash
# Test with 5k (should skip most F&O days)
Capital: 5,000 → Trades: 0-1

# Test with 10k (should trade 1 lot when possible)
Capital: 10,000 → Trades: ~5 per week → 1 lot each

# Test with 20k (should trade 2 lots when possible)
Capital: 20,000 → Trades: ~5 per week → 2 lots each
```

## Notes

- **30% Rule**: Uses max 30% of capital per position (adjustable if needed)
- **NIFTY**: Lot size = 25, typical premium = Rs.120, cost/lot = Rs.3,000
- **BANKNIFTY**: Lot size = 15, typical premium = Rs.150, cost/lot = Rs.2,250
- Minimum capital for NIFTY F&O: ~Rs.10,000 (30% = Rs.3,000 = 1 lot)
- Minimum capital for BANKNIFTY F&O: ~Rs.7,500 (30% = Rs.2,250 = 1 lot)
