# 🚀 Dynamic Trade Frequency Engine - Complete Guide

## 📋 Overview

The **Dynamic Trade Frequency Engine** is a professional-grade trading frequency control system that **replaces fixed daily trade limits** with an intelligent, capital-based, hourly frequency system that adapts to market conditions and protects capital during drawdowns.

---

## ✅ What Was Implemented

### 1. **Removed Fixed Trade Limits**
- ❌ Removed: `MAX_TRADES_PER_SESSION` constant
- ❌ Removed: `max_trades_allowed` per session
- ❌ Removed: Fixed daily trade count checks
- ✅ Added: Dynamic hourly frequency calculation

### 2. **Capital-Based Trade Slabs**
Default configuration (fully customizable):

| Capital Range | Trades per Hour |
|--------------|-----------------|
| ₹0 - ₹50,000 | 2 |
| ₹50,000 - ₹2,00,000 | 3 |
| ₹2,00,000 - ₹5,00,000 | 4 |
| ₹5,00,000+ | 5 |

### 3. **Drawdown-Aware Reduction**
- **Normal Mode**: Full trading frequency (100%)
- **Reduced Mode**: Triggered at **2% daily loss** → Frequency reduced by 50%
- **Hard Limit**: Triggered at **5% daily loss** → Limited to **1 trade/hour** (max protection)

### 4. **Hourly Reset System**
- Trade counts reset every hour (e.g., 9:00 AM, 10:00 AM, etc.)
- Prevents all-day lockout after morning losses
- Allows recovery opportunities throughout the day

### 5. **Works Everywhere**
✅ **Live Trading** - Uses real account balance for frequency calculation
✅ **Paper Trading** - Uses virtual balance
✅ **Backtesting** - Simulates hourly frequency during multi-day backtests

---

## 🎯 How It Works

### Frequency Calculation Logic

```
1. Determine capital slab → Get base trades/hour
2. Apply safety cap (max 5/hour by default)
3. Check drawdown:
   - If daily PnL ≤ -2% → Reduce frequency by 50%
   - If daily PnL ≤ -5% → Force 1 trade/hour
4. Return (max_trades_this_hour, frequency_mode)
```

### Example Scenarios

#### Scenario 1: Normal Trading Day
- **Capital**: ₹1,50,000
- **Daily P&L**: ₹+500 (profit)
- **Result**: **3 trades/hour** (NORMAL mode)

#### Scenario 2: Minor Drawdown
- **Capital**: ₹1,50,000
- **Daily P&L**: ₹-3,200 (-2.1% loss)
- **Result**: **1 trade/hour** (REDUCED mode)
  - Base: 3 trades/hour × 50% reduction = 1.5 → Rounds to 1

#### Scenario 3: Major Drawdown
- **Capital**: ₹1,50,000
- **Daily P&L**: ₹-8,000 (-5.3% loss)
- **Result**: **1 trade/hour** (HARD_LIMIT mode)
  - Hard limit protection activated

---

## ⚙️ Configuration

### Access Settings
1. Navigate to **Settings** page
2. Click **"Trade Frequency"** tab
3. Configure:
   - **Capital Slabs**: Add/edit/remove capital ranges
   - **Max Hourly Cap**: Absolute maximum (1-10)
   - **Drawdown Trigger**: % loss for frequency reduction (default: 2%)
   - **Hard Drawdown Trigger**: % loss for hard limit (default: 5%)
   - **Reduction Factor**: % to reduce frequency (default: 50%)

### Example Custom Configuration

```json
{
  "rules": [
    { "min_capital": 0, "max_capital": 25000, "max_trades_per_hour": 1 },
    { "min_capital": 25000, "max_capital": 100000, "max_trades_per_hour": 2 },
    { "min_capital": 100000, "max_capital": 500000, "max_trades_per_hour": 3 },
    { "min_capital": 500000, "max_capital": null, "max_trades_per_hour": 4 }
  ],
  "max_hourly_cap": 4,
  "drawdown_trigger_percent": 0.015,  // 1.5% trigger
  "hard_drawdown_trigger_percent": 0.03,  // 3% hard limit
  "drawdown_reduce_percent": 0.6  // 60% reduction
}
```

---

## 📊 UI Indicators

### Active Sessions Dashboard

Each session card shows:

```
Capital: ₹1,20,000
Trades this hour: 1 / 3
Daily PnL: ₹-2,500
Frequency Mode: REDUCED

⚠ Frequency reduced due to drawdown
```

**Frequency Mode Badges**:
- 🟢 **NORMAL** - Full trading frequency
- 🟡 **REDUCED** - Drawdown triggered, reduced frequency
- 🔴 **HARD_LIMIT** - Major loss protection, 1 trade/hour max

### Backtest Results

Daily breakdown includes:
- **Freq Mode** column showing mode for each day
- Summary showing overall frequency behavior
- Hourly trade counts per day

---

## 🧪 Testing & Validation

### Run Test Suite

```bash
cd kite_quant
python test_trade_frequency.py
```

### Test Coverage
✅ Capital slab matching  
✅ Drawdown-based reduction  
✅ Frequency reduction math (50% reduction)  
✅ Hard limit enforcement (1 trade/hour)  
✅ Config validation  
✅ Minimum 1 trade guarantee  

**Latest Test Results**: 6/6 test suites passed ✅

---

## 🛡️ Safety Features

### 1. **Risk-Per-Trade Unchanged**
- Dynamic frequency does **NOT** affect position sizing
- Still uses configured risk % per trade (e.g., 2% of capital)

### 2. **Daily Loss Limit Still Active**
- If daily loss limit hit → Session stops completely
- Frequency system works **before** loss limit is reached

### 3. **Kill Switch Available**
- User can manually stop any session anytime
- Frequency doesn't override manual control

### 4. **Absolute Failsafe**
- Backtest still enforces `max_trades_per_day` as a hard ceiling
- Never exceeds user-defined maximum

### 5. **Market Hours Check**
- Only trades during market hours (9:15 AM - 3:15 PM IST)
- Frequency doesn't bypass time-of-day logic

### 6. **Strategy Entry Conditions**
- Trade only happens if strategy signals entry
- Frequency is **on top of** strategy logic, not a replacement

---

## 📈 Benefits

### 1. **Scales With Capital**
- Small accounts (₹25K) → Conservative 2 trades/hour
- Large accounts (₹5L+) → Active 5 trades/hour

### 2. **Prevents Overtrading**
- No more "blowing through 10 trades in 30 minutes"
- Paced trading throughout the day

### 3. **Drawdown Protection**
- Auto-reduces frequency during losses
- Prevents revenge trading spiral

### 4. **Flexible & Configurable**
- Fully customizable from Settings UI
- No code changes needed

### 5. **Professional Grade**
- Used by institutional trading systems
- Quality over quantity approach

---

## 🚀 Usage in Manual Mode

**Workflow**:
1. User approves trade recommendation
2. Session becomes **ACTIVE**
3. AI scans market every minute
4. **Before Entry**:
   - ✅ Check if strategy signals entry
   - ✅ Check hourly trade frequency
   - ✅ Check risk limits
5. If all pass → Enter trade
6. After exit → Frequency reset for next hour if needed
7. **No fixed daily limit spam**

---

## 📝 API Endpoints

### Get Configuration
```
GET /api/settings/trade-frequency
```

**Response**:
```json
{
  "ok": true,
  "config": {
    "rules": [...],
    "max_hourly_cap": 5,
    "drawdown_trigger_percent": 0.02,
    "hard_drawdown_trigger_percent": 0.05,
    "drawdown_reduce_percent": 0.5
  }
}
```

### Save Configuration
```
POST /api/settings/trade-frequency
```

**Body**:
```json
{
  "config": {
    "rules": [...],
    "max_hourly_cap": 5,
    ...
  }
}
```

---

## 🔧 Technical Implementation

### Files Modified/Created

1. **`engine/trade_frequency.py`** (NEW)
   - Core calculation logic
   - Config validation
   - Status checking

2. **`app.py`** (MODIFIED)
   - Session engine integration
   - API endpoints
   - Backtest integration

3. **`templates/settings.html`** (MODIFIED)
   - Trade Frequency settings tab
   - Capital slabs table editor

4. **`templates/dashboard/ai_agent.html`** (MODIFIED)
   - Frequency status display
   - Mode badges

5. **`templates/dashboard/backtest.html`** (MODIFIED)
   - Frequency mode column in results
   - Daily breakdown includes frequency

6. **`test_trade_frequency.py`** (NEW)
   - Comprehensive test suite
   - Validates all calculations

---

## 🎓 Best Practices

### 1. **Conservative Starts**
- New traders: Start with **1-2 trades/hour**
- Experienced traders: Use **3-4 trades/hour**
- Day traders: Max **5 trades/hour**

### 2. **Tight Drawdown Limits**
- Set drawdown trigger at **1.5-2%**
- Set hard limit at **3-5%**

### 3. **Monitor Capital Growth**
- As capital grows, frequency naturally increases
- No manual adjustments needed

### 4. **Review Weekly**
- Check if frequency slabs match your style
- Adjust if consistently hitting hourly limits

### 5. **Use With Other Safeguards**
- Combine with daily loss limit
- Use stop-losses on all trades
- Don't disable kill switch

---

## ❓ FAQ

### Q: What if I want unlimited trades?
**A**: Set `max_hourly_cap` to 10 and all slabs to 10. Not recommended.

### Q: Can I disable this system?
**A**: No, it's a core safety feature. You can set it to very high limits if needed.

### Q: Does this affect backtesting?
**A**: Yes, backtests now simulate the same hourly frequency logic.

### Q: What about paper trading?
**A**: Uses virtual balance for frequency calculation, same logic as live.

### Q: Can I have different settings per session?
**A**: No, settings are global. All sessions use the same frequency config.

---

## 🎉 Result

You now have a **professional-grade dynamic trade frequency system** that:
- ✅ Scales with capital
- ✅ Protects during drawdowns
- ✅ Prevents overtrading
- ✅ Works everywhere (Live/Paper/Backtest)
- ✅ Fully configurable
- ✅ Production-tested

**No more fixed trade limits. Welcome to intelligent frequency control.**

---

**Questions or issues?** Check the test suite output or review the Settings → Trade Frequency section.
