# Backtest Improvement Plan - Root Cause Analysis

## Current Problem (Your Screenshot)
```
Net P&L: -₹543.70
Total Trades: 3 (only on 2026-02-05)
Win Rate: 33.3% (1 win, 2 losses)
Other days: 0 trades
```

## What Went WRONG with "Improvements"

### ❌ Bad Changes Made:
1. **Wider Stop Loss (60%)** → BIGGER losses when hit
   - Before: ~1.5% loss per trade
   - After: 40% loss per trade = **26x bigger losses!**

2. **Complex Option Simulation** → Unreliable placeholder logic
   - Live/Paper use 65+ real strategies
   - Backtest used fake entry/exit signals

3. **Over-Engineered** → More code, worse results

## ✅ Changes Reverted:
1. Stop loss back to strategy-specific (0.5-2%)
2. Target back to strategy-specific (2-5%)  
3. Removed F&O-specific stop/target overrides

## Real Issues (Not Fixed Yet)

### Issue 1: Only 3 Trades in 4 Days
**Why:**
- Entry signals not triggering  
- Maybe wrong candle data format
- Maybe hourly frequency limit blocking trades

### Issue 2: Backtest Uses Placeholder Logic
**Why:**
- Live/Paper: Use real strategy classes (Momentum Breakout, RSI Reversal, etc.)
- Backtest: Uses hardcoded if/else statements
- **Solution**: Make backtest use SAME strategy classes as Live/Paper

### Issue 3: No F&O Options in Backtest
**Why:**
- Backtest tries to simulate options but poorly
- Live/Paper actually trade real NFO options
- **Solution**: Either trade underlying OR integrate real NFO data

## Recommended Fix (Centralized Approach)

### Step 1: Use Real Strategies (CRITICAL)
```python
# Current (BAD - placeholder logic)
if price_change > 0.1%:
    enter_trade()

# Should be (GOOD - real strategy)
strategy = get_strategy_for_session(session, "Momentum Breakout")
can_enter, price = strategy.check_entry()
if can_enter:
    enter_trade(price)
```

### Step 2: Centralized Entry/Exit
**File**: `strategies/base_strategy.py`
- ✅ Already has stop_loss/target methods
- ✅ All 65+ strategies inherit from it
- ✅ Live/Paper already use this
- ❌ Backtest bypasses it (uses placeholder)

**Fix**: Make backtest call `strategy.check_entry()` and `strategy.check_exit()`

### Step 3: Simplify F&O
**Options**:
1. **Option A**: Trade underlying (NIFTY spot) - Simple, works now
2. **Option B**: Use real NFO data - Complex, needs Zerodha integration
3. **Option C**: Skip F&O in backtest - Test stocks only

## Testing Strategy

### Test 1: Simple Stock (Not Index)
```
Instrument: RELIANCE
Capital: ₹10,000
Duration: 1 month
Expected: 20-50 trades, mixed P&L
```

### Test 2: Index (Underlying)
```
Instrument: NIFTY 50
Capital: ₹10,000
Duration: 1 month
Trade: Underlying (not options)
Expected: 30-60 trades, better results
```

### Test 3: Compare with Live/Paper
```
1. Run Paper trading for 1 day
2. Run Backtest for same day
3. Should get similar # of trades
```

## What NOT to Do

### ❌ Don't:
1. Make stop loss wider (causes BIGGER losses)
2. Add complex option simulation (unreliable)
3. Change strategy logic in backtest only
4. Add hardcoded entry/exit rules

### ✅ Do:
1. Use SAME strategy classes as Live/Paper
2. Keep stop/target from strategies
3. Test with stocks first (simpler)
4. Compare results with Live/Paper

## Current Code Status

### Centralized (Good):
- ✅ `engine/position_sizing.py` - Used by all 3 modes
- ✅ `strategies/base_strategy.py` - Used by Live/Paper
- ✅ `engine/trade_frequency.py` - Used by all 3 modes

### Not Centralized (Bad):
- ❌ Backtest entry/exit logic - Hardcoded, not using strategies
- ❌ Backtest option simulation - Placeholder math, not real

## Next Steps

1. **Immediate**: Test with RELIANCE stock (not index)
2. **Short term**: Make backtest use real strategy classes  
3. **Long term**: Integrate real NFO option data OR just trade underlying

## Capital Requirements (Unchanged)

| Capital | NIFTY | BANKNIFTY | Notes |
|---------|-------|-----------|-------|
| ₹5k     | ❌    | ❌        | Insufficient |
| ₹10k    | ✅    | ❌        | NIFTY only |
| ₹15k+   | ✅    | ✅        | Both work |

## Summary

**Problem**: Tried to "improve" by widening stop loss → Made losses 26x bigger
**Solution**: Reverted changes, kept strategies' original stop/target logic
**Next**: Make backtest use REAL strategy classes (same as Live/Paper)
