# F&O Options Backtesting Implementation

## Overview
The backtesting system now trades **Futures & Options (F&O)** for indices (NIFTY, BANKNIFTY) instead of the underlying index, matching the live/paper trading behavior.

## How It Works

### 1. Daily Market Bias Detection
- Analyzes first 15 candles of the day
- Calculates price trend and volatility
- Determines bias: **BULLISH** or **BEARISH**

### 2. F&O Option Selection
- **BULLISH bias** → Select **CE (Call Option)**
- **BEARISH bias** → Select **PE (Put Option)**
- Calculates ATM (At-The-Money) strike
- Selects **1 strike OTM** for better Risk/Reward

### 3. Premium Calculation
**Base Premium (Daily):**
- NIFTY: Rs.120
- BANKNIFTY: Rs.150

**Dynamic Premium (Intraday):**
```python
underlying_move = current_ltp - spot_price_at_start
delta = 0.5  # Approximate delta for OTM options
premium_change = underlying_move * delta
current_premium = base_premium + premium_change
```

### 4. Position Sizing
- Uses centralized `calculate_fo_position_size()`
- Calculates max lots based on capital (30% allocation)
- Accounts for lot size:
  - NIFTY: 25 lots
  - BANKNIFTY: 15 lots

### 5. Entry/Exit Logic
**Entry:**
- Triggers based on strategy (Momentum Breakout, RSI Reversal, etc.)
- Enters at current option premium
- Sets option-specific SL/Target:
  - Stop Loss: 15% below entry (0.85x)
  - Target: 30% above entry (1.30x)
  - Risk/Reward: 1:2

**Exit:**
- **Intraday**: Recalculates premium using Delta before SL/Target check
- **EOD**: Calculates final premium and closes position
- **Stop Loss/Target**: Based on option premium, not underlying

## Example Test Result

**Date**: 2025-12-23 (1 day)  
**Capital**: Rs.10,000  
**Instrument**: NIFTY 50

### Trade 1 - WIN
- **Bias**: BEARISH
- **Selected**: NIFTY 26150 PE
- **Entry**: Rs.79.55 (09:40 AM)
- **Exit**: Rs.103.42 (09:55 AM, TARGET)
- **P&L**: +Rs.596.63
- **Lots**: 1 (25 qty)

### Trade 2 - LOSS
- **Selected**: NIFTY 26150 PE
- **Entry**: Rs.107.88 (10:00 AM)
- **Exit**: Rs.99.68 (EOD)
- **P&L**: -Rs.204.98
- **Lots**: 1 (25 qty)

### Results
- **Net P&L**: Rs.391.65
- **Return**: 3.92%
- **Win Rate**: 50% (1W, 1L)

## Code Locations

### Backtesting
- **Function**: `_simulate_trading_day()` in `app.py` (lines 4126-4664)
- **F&O Selection**: Lines 4150-4259
- **Premium Calculation**: Lines 4542-4546 (entry), 4404-4414 (exit check), 4619-4630 (EOD)
- **Position Sizing**: Lines 4549-4554

### Position Sizing
- **Module**: `engine/position_sizing.py`
- **Function**: `calculate_fo_position_size(capital, premium, lot_size)`

## Consistency Across Modes
All three modes (Live, Paper, Backtest) now use:
1. ✅ Real strategy classes (`strategies/`)
2. ✅ F&O options for indices
3. ✅ Centralized position sizing
4. ✅ GPT-based strategy recommendations (when AI enabled)
5. ✅ Dynamic trade frequency from Settings

## Testing
To test F&O backtest:
```python
from app import _run_ai_backtest
from datetime import date

result = _run_ai_backtest(
    instrument="NIFTY 50",
    from_date=date(2025, 12, 23),
    to_date=date(2025, 12, 27),  # 1 week
    timeframe="5m",
    initial_capital=10000,
    risk_percent=2.0,
    ai_enabled=True,
    ai_check_interval=60,
)
```

**Note**: Use dates within last 60 days for 5-minute data (yfinance limitation).

## Verification Logs
The system logs F&O trades clearly:
```
[AI BACKTEST F&O] 2025-12-23: Market bias = BEARISH (trend: -0.13%, vol: 0.33%)
[AI BACKTEST F&O] 2025-12-23: Trading NIFTY 26150 PE
[AI BACKTEST F&O] NIFTY 26150 PE: Premium=79.55, Lots=1, Qty=25
[AI BACKTEST] 2025-12-23 09:40:00: ENTRY Momentum Breakout @Rs.79.55 SL:Rs.67.62 Target:Rs.103.42
[AI BACKTEST] 2025-12-23 09:55:00: EXIT TARGET @ Rs.103.42 | P&L: Rs.596.63
```

## Advantages of F&O Options
1. **Higher Leverage**: Control larger position with lower capital
2. **Limited Risk**: Maximum loss = premium paid
3. **Better Returns**: Options can give 20-50% returns vs 2-3% in cash
4. **Direction-Based**: Can profit from BULLISH (CE) or BEARISH (PE) moves
5. **Realistic**: Matches actual F&O trading behavior

---
**Last Updated**: 2026-02-10  
**Status**: ✅ Fully Implemented and Tested
