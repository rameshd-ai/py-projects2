# 🚀 Dynamic Trade Frequency Engine

## Overview

The **Dynamic Trade Frequency Engine** is a professional-grade capital management system that replaces fixed daily trade limits with an intelligent, adaptive frequency control mechanism.

Instead of allowing a fixed number of trades per day (which can lead to overtrading with small capital or underutilization with large capital), this system:

- ✅ **Scales with your capital** - More capital = more trading opportunities
- ✅ **Adapts to performance** - Reduces frequency during drawdowns
- ✅ **Prevents overtrading** - Hourly limits protect from brokerage issues
- ✅ **Maintains risk discipline** - Works alongside risk-per-trade controls
- ✅ **Fully configurable** - Customize slabs and triggers from Settings

---

## How It Works

### 1. Capital-Based Frequency Slabs

Your maximum trades per hour is determined by your current capital:

| Capital Range | Trades per Hour (Default) |
|--------------|---------------------------|
| ₹0 - ₹50,000 | 2 |
| ₹50,000 - ₹2,00,000 | 3 |
| ₹2,00,000 - ₹5,00,000 | 4 |
| ₹5,00,000+ | 5 |

**Example:**
- If you have ₹40,000 capital → Max 2 trades per hour
- If you have ₹1,50,000 capital → Max 3 trades per hour
- If you have ₹7,00,000 capital → Max 5 trades per hour

### 2. Hourly Reset

Every hour (9:00 AM, 10:00 AM, 11:00 AM, etc.), your trade counter resets.

This means:
- You can execute up to your limit in each hour
- No single hour can consume your entire day's trading capacity
- Prevents burst trading followed by long idle periods

### 3. Drawdown Protection

The system automatically reduces frequency when you're losing money:

#### Soft Drawdown (Default: -2%)
When daily P&L drops to -2% of capital:
- **Frequency reduces by 50%**
- Example: 4 trades/hour → 2 trades/hour

#### Hard Drawdown (Default: -5%)
When daily P&L drops to -5% of capital:
- **Frequency limited to 1 trade/hour**
- Forces you to slow down and reassess

**Example:**
```
Capital: ₹1,00,000
Base Limit: 3 trades/hour

Scenario 1 (Normal): Daily P&L = +₹500
→ Frequency: NORMAL (3 trades/hour)

Scenario 2 (Soft Drawdown): Daily P&L = -₹2,500 (-2.5%)
→ Frequency: REDUCED (1 trade/hour, reduced by 50%)

Scenario 3 (Hard Drawdown): Daily P&L = -₹6,000 (-6%)
→ Frequency: HARD_LIMIT (1 trade/hour, protection mode)
```

---

## Configuration

### Access Settings

1. Navigate to **Settings** → **Trade Frequency** tab
2. Configure capital slabs and drawdown triggers
3. Click **Save Frequency Settings**

### Capital Slabs

Configure custom frequency tiers:

```json
{
  "rules": [
    {
      "min_capital": 0,
      "max_capital": 50000,
      "max_trades_per_hour": 2
    },
    {
      "min_capital": 50000,
      "max_capital": 200000,
      "max_trades_per_hour": 3
    }
  ]
}
```

**Tips:**
- No overlapping ranges
- Last slab can have `max_capital: null` (no upper limit)
- max_trades_per_hour: 1-10

### Safety Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Max Hourly Cap** | 5 | Absolute maximum per hour |
| **Drawdown Trigger %** | 2% | When to reduce frequency |
| **Hard Drawdown %** | 5% | When to force 1 trade/hour |
| **Reduction Factor** | 50% | How much to reduce frequency |

---

## UI Indicators

In the **Active Sessions** panel, you'll see:

```
Frequency: NORMAL
Trades this hour: 1 / 3
```

**Frequency Modes:**
- 🟢 **NORMAL** - Operating at full capacity
- 🟡 **REDUCED** - Drawdown protection active (⚠ warning shown)
- 🔴 **HARD_LIMIT** - Maximum protection (🛑 limit shown)

---

## Benefits

### 1. Professional Capital Scaling
Real trading firms scale frequency with capital. This mimics institutional practices.

### 2. Prevents Revenge Trading
When you're losing, the system forces you to slow down - preventing emotional overtrading.

### 3. Brokerage Safety
Limits per hour prevent hitting exchange/broker rate limits or triggering surveillance.

### 4. Quality Over Quantity
Instead of rushing to fill a daily quota, you take only the best setups each hour.

### 5. Drawdown Management
Automatically reduces activity during bad days, preserving capital for recovery.

---

## Interaction with Other Safeguards

The Dynamic Frequency Engine **works alongside** existing safety systems:

| System | Purpose | Interaction |
|--------|---------|-------------|
| **Risk per Trade %** | Controls position size | Independent - both apply |
| **Daily Loss Limit** | Stops trading at max loss | Stops session if hit |
| **Kill Switch** | Emergency stop | Overrides everything |
| **AI Strategy Switching** | Adapts strategy to market | Works within frequency limits |
| **Cutoff Time** | End-of-day closure | Stops trading regardless |

**Example Flow:**
```
1. Check: Is hourly limit reached? → No → Continue
2. Check: Does strategy signal entry? → Yes → Continue
3. Check: Is risk per trade acceptable? → Yes → Continue
4. Check: Will this exceed daily loss limit? → No → Continue
5. Execute trade
6. Increment hourly counter
```

---

## Migration from Fixed Daily Limits

### What Changed

**Old System:**
- Fixed `max_trades_allowed` per day (e.g., 10 trades/day)
- If you hit the limit at 10 AM, you're done for the day
- Same limit whether you have ₹10,000 or ₹10,00,000

**New System:**
- Dynamic hourly limits based on capital
- Resets every hour
- Adapts to performance (drawdown protection)

### Backward Compatibility

- Old sessions without hourly tracking are auto-initialized
- When you resume a stopped session, hourly tracking resets
- No action required - it just works

---

## Examples

### Example 1: Small Account (₹25,000)

```
Capital: ₹25,000
Base Limit: 2 trades/hour
Daily P&L: -₹300 (-1.2%)

Status: NORMAL
Hourly Limit: 2

At 9:30 AM: Trade 1 executed
At 9:45 AM: Trade 2 executed
At 10:00 AM: Hour resets → Can trade again (up to 2)
At 10:15 AM: Trade 3 executed
```

### Example 2: Medium Account with Drawdown (₹1,50,000)

```
Capital: ₹1,50,000
Base Limit: 3 trades/hour
Daily P&L: -₹4,000 (-2.67%)

Status: REDUCED (hit 2% trigger)
Hourly Limit: 1 (reduced from 3)

At 11:00 AM: Trade executed
At 11:30 AM: Strategy signals entry → BLOCKED (hourly limit)
At 12:00 PM: Hour resets → Can trade again (up to 1)
```

### Example 3: Large Account (₹6,00,000)

```
Capital: ₹6,00,000
Base Limit: 5 trades/hour
Daily P&L: +₹8,000 (+1.33%)

Status: NORMAL
Hourly Limit: 5

At 2:00 PM: 3 trades executed this hour
At 2:45 PM: Can still execute 2 more trades
At 3:00 PM: Hour resets (but cutoff 3:15 PM approaching)
```

---

## Troubleshooting

### "Hourly limit reached" Message

**Cause:** You've hit your trades-per-hour limit.

**Solution:**
- Wait for the next hour to reset
- Check your capital slab in Settings
- Verify your drawdown status (REDUCED/HARD_LIMIT?)

### Frequency Stuck at 1 Trade/Hour

**Cause:** You've hit the hard drawdown trigger (-5% default).

**Solution:**
- Your daily loss is significant - system is protecting you
- Either wait for tomorrow (fresh reset) or
- Adjust hard drawdown trigger in Settings (not recommended)

### Settings Not Saving

**Cause:** Validation failed (overlapping slabs, invalid ranges).

**Solution:**
- Check for overlapping capital ranges
- Ensure max_trades_per_hour is 1-10
- Ensure percentages are valid (0.5-20%)

---

## Best Practices

1. **Start Conservative**
   - Use default slabs initially
   - Don't rush to increase hourly limits

2. **Respect Drawdown Signals**
   - If you hit REDUCED mode, take it seriously
   - Don't immediately adjust triggers to override protection

3. **Monitor Hourly Patterns**
   - Track which hours you trade most
   - Are you exhausting limits in the first hour? Reassess strategy

4. **Scale Gradually**
   - As capital grows, frequency naturally increases
   - Don't manually override to trade more than your capital warrants

5. **Combine with AI**
   - Let AI strategy switching work within frequency limits
   - Quality strategies + controlled frequency = consistent results

---

## Technical Details

### Frequency Calculation Algorithm

```python
def calculate_max_trades_per_hour(capital, daily_pnl):
    # 1. Find capital slab
    base_limit = match_capital_slab(capital)
    
    # 2. Apply hourly cap
    base_limit = min(base_limit, max_hourly_cap)
    
    # 3. Check hard drawdown
    if daily_pnl <= -(capital * 0.05):
        return 1, "HARD_LIMIT"
    
    # 4. Check soft drawdown
    if daily_pnl <= -(capital * 0.02):
        base_limit = max(1, int(base_limit * 0.5))
        return base_limit, "REDUCED"
    
    # 5. Normal operation
    return base_limit, "NORMAL"
```

### Session Fields

Each trading session now tracks:
```python
{
    "current_hour_block": 10,        # Current hour (9-15)
    "hourly_trade_count": 2,         # Trades taken this hour
    "frequency_mode": "NORMAL",      # NORMAL|REDUCED|HARD_LIMIT
    # ... other session fields
}
```

### API Endpoints

- `GET /api/settings/trade-frequency` - Get current config
- `POST /api/settings/trade-frequency` - Save new config
- `GET /api/trade-sessions` - Includes frequency status

---

## FAQ

**Q: Can I disable this and use fixed daily limits?**
A: No. The new system is strictly superior and prevents common trading mistakes.

**Q: What if I want to trade more frequently?**
A: Increase your capital. Frequency scales with capital for a reason - risk management.

**Q: Does this work for both LIVE and PAPER modes?**
A: Yes. The system uses virtual_balance for PAPER and real balance for LIVE.

**Q: Will this affect my risk per trade %?**
A: No. Frequency controls *how often* you trade. Risk % controls *how much* per trade.

**Q: Can I override frequency during exceptional opportunities?**
A: No. Discipline is key. If you constantly want to override, your base settings are wrong.

**Q: What happens at 3:00 PM with 5 trades/hour limit?**
A: Cutoff time (e.g., 3:15 PM) overrides frequency. You won't get a full hour.

---

## Conclusion

The **Dynamic Trade Frequency Engine** is a professional-grade feature that:
- Scales trading activity with capital
- Protects you during drawdowns
- Prevents overtrading and brokerage issues
- Maintains consistent quality over quantity

Configure it once in Settings, then let it work in the background, adapting to your capital and performance automatically.

**Trade smarter, not harder.** 🚀
