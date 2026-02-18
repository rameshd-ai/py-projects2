# 🤖 AI Auto-Switching Guide

> **✨ NEW: AI Auto-Switching is ENABLED BY DEFAULT!**  
> When you create a new trading session, AI will automatically analyze market conditions every 5 minutes and switch to the optimal strategy. No setup required!

## Overview

The AI Trading Agent now features **intelligent automatic strategy switching** powered by GPT-4o-mini. The AI continuously analyzes real-time market conditions and automatically switches to the optimal trading strategy.

## Features

### 1. **Smart Strategy Selection**
- GPT analyzes NIFTY 50, BANK NIFTY, India VIX, and recent price action
- Considers time of day, volatility, trend strength, and volume patterns
- Recommends the best strategy from 12+ available algorithms

### 2. **Automatic Strategy Switching**
- AI checks market conditions every 5 minutes (configurable)
- Only switches when confidence is "medium" or "high"
- Prevents unnecessary switches (stays if current strategy is still optimal)
- Tracks number of switches per session

### 3. **Full Transparency**
- Shows AI recommendation with confidence level
- Displays reasoning for each recommendation
- Shows market assessment summary
- Logs all switches with timestamps

## How to Use

### Step 1: Create a Trading Session
1. Go to **AI Trading Agent** page
2. Select your instrument (e.g., BANKNIFTY, NIFTY)
3. Choose execution mode (PAPER or LIVE)
4. Approve and run the trade
5. **AI Auto-Switching is NOW ENABLED BY DEFAULT!** 🎉

### Step 2: Monitor AI Recommendations (Automatic)
- The session card will show a blue 🤖 AI Auto-Switch badge
- AI recommendations appear in a blue info box showing:
  - Recommended strategy
  - Confidence level (low/medium/high)
  - Reasoning (2-3 sentences)
  - Market assessment
- Number of AI switches is shown as a badge (e.g., ↻ 3)

## AI Decision Process

The AI evaluates:

### Market Context
- **NIFTY 50**: Current price and % change
- **BANK NIFTY**: Current price and % change  
- **India VIX**: Volatility level
- **Time of Day**: Market open (9:15-9:45), mid-day, closing (14:30-15:15)
- **Recent Price Action**: Last 5 candles - trend, volume, range

### Strategy Profiles

#### Trending Markets
- **Momentum Breakout**: Strong breakouts with high volume
- **EMA Ribbon Trend**: Multiple EMAs aligned
- **Pullback Continuation**: Healthy pullbacks in trends
- **VWAP Trend Ride**: Price respecting VWAP levels

#### Ranging Markets
- **Bollinger Mean Reversion**: Low volatility, Bollinger extremes
- **RSI Reversal**: RSI overbought/oversold reversals
- **VWAP Reclaim**: Trend reversal on VWAP reclaim

#### High Volatility
- **News Volatility Burst**: VIX spike, sudden moves
- **Volume Climax Reversal**: Exhaustion after climax volume
- **Time-Based Volatility**: Market open/close periods

#### Consolidation/Breakout
- **Range Compression Breakout**: Tight consolidation before expansion
- **Liquidity Sweep Reversal**: False breakouts and reversals

## Configuration

### Check Interval
- **Default**: 5 minutes ⚡ (NEW: automatically set)
- **Recommended**: 5-10 minutes
- **Aggressive**: 3 minutes (more switches)
- **Conservative**: 10-15 minutes (fewer switches)
- **Can be changed**: Click "Enable AI" again to adjust interval

### Confidence Threshold
- Currently set to "medium" (hardcoded)
- "Low" confidence recommendations are ignored
- Only "medium" and "high" confidence triggers switches

## API Endpoints

### Enable/Disable AI Switching
```
POST /api/trade-sessions/<session_id>/ai-mode
Body: {
  "enabled": true,
  "interval_minutes": 5
}
```

### Get Sessions with AI Status
```
GET /api/trade-sessions
Response includes:
- ai_auto_switching_enabled: true/false
- ai_check_interval_minutes: 5
- last_ai_strategy_check: "2026-02-09T10:00:00"
- last_ai_recommendation: {...}
- ai_strategy_switches: 3
```

## Cost Optimization

### OpenAI API Usage
- Uses **GPT-4o-mini** (extremely cost-effective)
- ~$0.15 per million input tokens
- ~$0.60 per million output tokens
- Typical cost: **<$0.01 per day** per active session

### Prompt Size
- Each recommendation: ~500 input tokens + ~150 output tokens
- 5-minute interval = ~12 requests/hour = ~$0.001/hour per session

## Best Practices

### 1. **Start with Paper Trading**
- Test AI switching with PAPER mode first
- Observe AI recommendations and switches
- Verify strategy changes make sense

### 2. **Monitor AI Reasoning**
- Read the AI's market assessment
- Check if reasoning aligns with your view
- Disable if AI recommendations seem off

### 3. **Adjust Check Interval**
- Start with 5 minutes
- Increase to 10-15 min if too many switches
- Decrease to 3 min for highly volatile periods

### 4. **Review Switch History**
- Check the "↻ N" badge to see number of switches
- Too many switches? Increase interval
- Too few switches? Decrease interval or check reasoning

## Troubleshooting

### AI Button Not Appearing
- Ensure session is ACTIVE (not STOPPED)
- Refresh the Active Sessions panel

### No AI Recommendations
- Check OPENAI_API_KEY is configured in Settings
- Verify API key is valid (Settings > OpenAI API Key)
- Check browser console and server logs for errors

### AI Not Switching
- Verify AI Auto-Switching is enabled (🤖 AI Auto-Switch badge visible)
- Check last AI check time
- AI may recommend staying with current strategy (no switch needed)
- Increase to "low" confidence threshold (requires code change)

### Unexpected Switches
- AI is reacting to rapid market changes
- Increase check interval to reduce sensitivity
- Review AI reasoning to understand logic

## Technical Details

### AI Strategy Advisor Module
**File**: `kite_quant/engine/ai_strategy_advisor.py`

**Functions**:
- `get_market_context()`: Gathers market data
- `get_ai_strategy_recommendation()`: Calls OpenAI GPT API
- `should_switch_strategy()`: Determines if switch is needed

### Engine Integration
**File**: `kite_quant/app.py`

**Flow**:
1. Session engine tick (every 30 seconds)
2. For each ACTIVE session with AI enabled:
   - Check if AI interval elapsed
   - Gather market context
   - Call AI advisor
   - If switch recommended, update session strategy
   - Save session state

### Session State
```json
{
  "ai_auto_switching_enabled": true,
  "ai_check_interval_minutes": 5,
  "last_ai_strategy_check": "2026-02-09T10:05:00",
  "last_ai_recommendation": {
    "recommended_strategy": "Momentum Breakout",
    "confidence": "high",
    "reasoning": "Strong bullish breakout with high volume...",
    "switch_from_current": true,
    "market_assessment": "Trending market, VIX low"
  },
  "ai_strategy_switches": 3
}
```

## Future Enhancements

- [ ] Configurable confidence threshold in UI
- [ ] AI recommendation history log
- [ ] Performance tracking per AI switch
- [ ] Backtesting AI switching logic
- [ ] Custom strategy whitelist/blacklist
- [ ] AI explanation on why NOT to switch
- [ ] Switch cooldown period (min time between switches)
- [ ] Multi-model support (Claude, Gemini)

## Support

For issues or questions:
1. Check server logs for `[AI ADVISOR]` entries
2. Verify OpenAI API key in config.json
3. Test with a simple PAPER session first
4. Review AI recommendation reasoning carefully

---

**Status**: ✅ Fully Integrated and Working
**Last Updated**: 2026-02-09
