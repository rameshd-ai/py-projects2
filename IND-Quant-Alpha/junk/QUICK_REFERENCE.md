# 🚀 Dynamic Trade Frequency - Quick Reference

## 📊 Default Frequency Table

| Capital | Trades/Hour (Normal) | Trades/Hour (Reduced @2% loss) | Trades/Hour (Hard @5% loss) |
|---------|---------------------|-------------------------------|----------------------------|
| ₹25,000 | 2 | 1 | 1 |
| ₹75,000 | 3 | 1 | 1 |
| ₹2,50,000 | 4 | 2 | 1 |
| ₹6,00,000 | 5 | 2 | 1 |

---

## 🎯 Quick Access

### Settings
1. Open **Settings** page
2. Click **"Trade Frequency"** tab
3. Edit slabs or drawdown thresholds
4. Click **Save**

### View Frequency (Active Sessions)
Look for in session card:
- **Badge**: NORMAL 🟢 / REDUCED 🟡 / HARD_LIMIT 🔴
- **Counter**: "Trades this hour: 1 / 3"
- **Warning**: If reduced/limited

### Backtest
Check **"Freq Mode"** column in daily breakdown table.

---

## 🧪 Test Command

```bash
cd kite_quant
python test_trade_frequency.py
```

Expected: **6/6 test suites passed** ✅

---

## 🛡️ Key Safeguards

- ✅ **2% loss** → Frequency reduced by 50%
- ✅ **5% loss** → Hard limit (1 trade/hour)
- ✅ **Hourly reset** → Fresh start every hour
- ✅ **Capital-based** → Scales with account size
- ✅ **Min 1 trade** → Never completely locked out

---

## 📝 Code Location

| Component | File | Line(s) |
|-----------|------|---------|
| Core Logic | `engine/trade_frequency.py` | All |
| Session Integration | `app.py` | 3193-3212 |
| Settings API | `app.py` | 3992-4023 |
| Settings UI | `templates/settings.html` | 139-457 |
| Session Display | `templates/dashboard/ai_agent.html` | 458-463 |
| Backtest | `app.py` | _simulate_trading_day |

---

## 🎯 Common Customizations

### More Conservative (Beginners)
```json
{
  "rules": [
    { "min_capital": 0, "max_capital": 100000, "max_trades_per_hour": 1 },
    { "min_capital": 100000, "max_capital": null, "max_trades_per_hour": 2 }
  ],
  "max_hourly_cap": 2,
  "drawdown_trigger_percent": 0.015,  // 1.5%
  "hard_drawdown_trigger_percent": 0.03  // 3%
}
```

### More Aggressive (Day Traders)
```json
{
  "rules": [
    { "min_capital": 0, "max_capital": 50000, "max_trades_per_hour": 3 },
    { "min_capital": 50000, "max_capital": 200000, "max_trades_per_hour": 5 },
    { "min_capital": 200000, "max_capital": null, "max_trades_per_hour": 7 }
  ],
  "max_hourly_cap": 7,
  "drawdown_trigger_percent": 0.03,  // 3%
  "hard_drawdown_trigger_percent": 0.07  // 7%
}
```

---

## ❓ FAQs

**Q: How do I disable this?**  
A: Set all slabs to 10 trades/hour and `max_hourly_cap` to 10. (Not recommended)

**Q: Does it work in backtest?**  
A: Yes! Backtest simulates the same hourly frequency logic.

**Q: What if I lose 10% in a day?**  
A: Daily loss limit (separate feature) will stop the session completely.

**Q: Can I set different limits per stock?**  
A: No, frequency settings are global across all sessions.

**Q: Does this affect position sizing?**  
A: No, risk-per-trade % is unchanged. This only controls trade frequency.

---

## 🚀 Restart Required

After implementation, restart the Flask server:

```bash
python app.py
```

Then test the Settings → Trade Frequency page.

---

**Questions?** Read `TRADE_FREQUENCY_GUIDE.md` for full details.
