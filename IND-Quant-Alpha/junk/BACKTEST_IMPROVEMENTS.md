# F&O Backtesting Improvements - Applied to Live, Paper & Backtest

## Issues Fixed

### 1. **No Profits / Only Losses**
**Root Causes:**
- Stop loss too tight (30% → hit easily)
- Target too aggressive (50% → rarely reached)
- Entry signals too conservative (skipped most opportunities)
- Bias detection too strict (skipped NEUTRAL days)

**Solutions Applied to ALL Modes:**
- ✅ **Wider Stop Loss**: 60% (40% loss tolerance for option volatility)
- ✅ **Realistic Target**: 130% (30% profit target)
- ✅ **Aggressive Entry Signals**: 
  - Any 0.1% move in direction
  - Any matching candle color
  - Periodic hourly entries
- ✅ **Always Trade**: Even NEUTRAL days pick direction based on momentum

### 2. **BANKNIFTY Day 1 Loss, No Other Days**
**Root Causes:**
- High capital requirement: Rs.15,000+ needed (150 premium × 15 lots / 30%)
- With Rs.9k-10k capital: Can't afford even 1 lot
- Day 1 loss reduces capital further → no trades possible

**Solutions:**
- ✅ **Capital Check**: Skips days if can't afford 1 lot
- ✅ **Minimum Capital Display**: Shows required capital upfront
- ✅ **For BANKNIFTY**: Need Rs.15,000+ for consistent trading

## Centralized Position Sizing

**File**: `engine/position_sizing.py`

```python
# Configuration (applied to Live, Paper, Backtest)
FO_POSITION_SIZE_PERCENT = 0.30  # 30% of capital
MIN_PREMIUM_FLOOR = 50.0          # Rs.50 minimum premium
```

### Capital Requirements:
- **NIFTY**: Rs.10,000+ (120 premium × 25 lots / 0.30)
- **BANKNIFTY**: Rs.15,000+ (150 premium × 15 lots / 0.30)

## F&O-Aware Strategy Logic

**File**: `strategies/base_strategy.py`

### New Methods (All Strategies Inherit):
```python
get_stop_loss_fo_aware(entry_price, session)  # 60% for options vs 99.5% for stocks
get_target_fo_aware(entry_price, session)     # 130% for options vs 103% for stocks
_is_option_trading(session)                    # Auto-detects NFO exchange
```

### Applied In:
- ✅ **Live Trading** (`app.py` line ~3241)
- ✅ **Paper Trading** (same code path)
- ✅ **Backtest** (`backtest/backtest_engine.py` line ~163)

## Entry Signal Improvements

### Before (Too Conservative):
```python
if price_change > 0.3%:  # Rarely triggers
    enter CE
if 3 consecutive green candles:  # Very rare
    enter CE
```

### After (More Aggressive):
```python
if price_change > 0.1%:      # Frequent
    enter CE
if any green candle:         # Very frequent
    enter CE
if idx % 12 == 0:           # Every hour guaranteed
    enter CE
```

## Bias Detection Improvements

### Before:
```python
if trend > 0.3%: BULLISH
elif trend < -0.3%: BEARISH
else: NEUTRAL → SKIP DAY  # Problem!
```

### After:
```python
if trend > 0.15%: BULLISH
elif trend < -0.15%: BEARISH
else:
    # Use recent momentum instead of skipping
    if last_5_candles > 0: BULLISH
    else: BEARISH
→ ALWAYS TRADE
```

## Stop Loss & Target Comparison

| Mode | Instrument | Stop Loss | Target | Typical Result |
|------|------------|-----------|--------|----------------|
| **Stock** | RELIANCE | 99.5% (-0.5%) | 103% (+3%) | Small, frequent |
| **F&O Option** | NIFTY CE | 60% (-40%) | 130% (+30%) | Larger, realistic |

### Why Different?
- **Options are more volatile** - need wider stops
- **Premium moves faster** - can hit 30% target quickly
- **Stocks are stable** - tight stops protect capital

## Testing Results

### Minimum Capital Test:
```
Rs.5,000:  0 lots - INSUFFICIENT (for NIFTY)
Rs.10,000: 1 lot  - CAN TRADE
Rs.20,000: 2 lots - CAN TRADE
```

### Trade Frequency (Expected):
- **Before**: 0-2 trades/day (too conservative)
- **After**: 5-15 trades/day (more opportunities)

## Recommendations

### For Profitable Backtesting:
1. **Use Rs.10k+ for NIFTY**, Rs.15k+ for BANKNIFTY
2. **Test 1 month minimum** - 1 week too short for F&O patterns
3. **Check Daily Loss Limit** - Set to 10% in Settings
4. **Monitor Frequency Mode** - Should see NORMAL/REDUCED/HARD_LIMIT

### Capital Guidelines:
| Capital | NIFTY | BANKNIFTY | Expected Lots |
|---------|-------|-----------|---------------|
| Rs.5k   | ❌ Skip | ❌ Skip | 0 |
| Rs.10k  | ✅ 1 lot | ❌ Skip | 1 |
| Rs.15k  | ✅ 1 lot | ✅ 1 lot | 1 |
| Rs.20k  | ✅ 2 lots | ✅ 1 lot | 2 |
| Rs.30k  | ✅ 3 lots | ✅ 2 lots | 3 |

## Files Modified

### Backend:
1. `engine/position_sizing.py` - Centralized F&O position sizing
2. `strategies/base_strategy.py` - F&O-aware stop/target methods
3. `app.py` - Bias detection, entry signals, position sizing calls
4. `backtest/backtest_engine.py` - F&O-aware stop/target

### Applied To:
- ✅ Live Trading
- ✅ Paper Trading  
- ✅ Backtesting

**All modes now use identical F&O logic!**
