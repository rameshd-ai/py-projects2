# 📈 Kite Quant - AI-Powered Stock Trading Bot

**An intelligent, automated trading system for Indian stock market (NSE) using Zerodha Kite Connect API**

Perfect for beginners! This bot analyzes market data, predicts trends, and can execute trades automatically.

---

## 🎯 What Does This Bot Do?

### For Complete Beginners:

**Think of this bot as your smart trading assistant that:**
1. 📊 **Monitors the market** - Watches stock prices in real-time (every second!)
2. 🤖 **Predicts trends** - Uses AI to forecast if market will go UP ↗ or DOWN ↘
3. 📰 **Reads news** - Analyzes financial news to gauge market sentiment
4. 🌍 **Checks USA market** - Since US affects India, it tracks S&P 500 impact
5. 💼 **Executes trades** - Buys/sells stocks automatically based on signals
6. 🛡️ **Manages risk** - Sets automatic stop-loss and profit targets

### Key Concepts Explained:

#### 🇮🇳 **Nifty 50 Index**
- India's main stock market index (like Dow Jones in USA)
- Tracks top 50 companies on NSE (National Stock Exchange)
- When Nifty goes up ↗ = Indian market is doing well
- When Nifty goes down ↘ = Indian market is struggling

#### 📊 **Trading Terms Made Simple:**

| Term | What It Means |
|------|---------------|
| **P&L** | Profit & Loss - How much money you made/lost |
| **Sentiment** | Market mood based on news (positive = optimistic, negative = pessimistic) |
| **USA Bias** | How yesterday's US market affects today's Indian market |
| **Bullish ↗** | Market expected to go UP (good time to buy) |
| **Bearish ↘** | Market expected to go DOWN (good time to sell) |
| **Stop Loss (SL)** | Auto-sell if price drops too much (limits losses) |
| **Take Profit (TP)** | Auto-sell when target profit reached |
| **Intraday** | Buy and sell on the same day (no overnight positions) |

---

## ⚙️ Quick Setup

### Prerequisites:
- Python 3.10+ installed
- Poetry (Python package manager)
- Zerodha trading account (for live trading)
- News API key (free at https://newsapi.org)

### Installation:

1. **Install Dependencies**
   ```bash
   cd kite_quant
   poetry install
   ```

2. **Run the Application**
   ```bash
   poetry run python app.py
   ```

3. **Access Dashboard**
   - Open browser: http://localhost:5000
   - Login: `admin` / `admin`
   - Go to **Settings** → Enter your API keys

---

## 🔑 Getting API Keys

### 1. Zerodha Kite Connect (For Live Trading)
1. Go to https://kite.trade/
2. Sign up/Login to your Zerodha account
3. Create a new app at https://kite.trade/apps/
4. Copy: **API Key**, **API Secret**, **Access Token**
5. Paste in Dashboard → Settings

### 2. News API (For Sentiment Analysis)
1. Go to https://newsapi.org
2. Sign up for free account
3. Copy your **API Key**
4. Paste in Dashboard → Settings

---

## 🎮 How to Use

### Dashboard Overview:

#### **1. Overview Section**
- **Status**: Shows if bot is running/stopped
- **Nifty 50 Index**: Live Indian market performance (updates every 1 second!)
- **USA Bias**: How US market affects India today
- **USA Live Futures**: Real-time US market sentiment
- **Today's Prediction**: AI forecast (Bullish ↗ / Bearish ↘)
- **Prediction Accuracy**: How accurate past predictions were

#### **2. Testing & Backtest**
- Test your strategy with historical data
- No real money involved
- See how it would've performed in the past

#### **3. Live Trading**
- Real trading with actual money
- Automatic buy/sell execution
- Real-time profit/loss tracking

---

## 🛡️ Safety Features

### Risk Management (Built-in):
- ✅ **Max 3 trades per day** - Prevents overtrading
- ✅ **1.5% Stop Loss** - Limits losses on each trade
- ✅ **3% Take Profit** - Locks in profits automatically
- ✅ **Auto-close at 2:30 PM IST** - Exits all positions before market close
- ✅ **Kill Switch** - Emergency button to close all trades instantly

### Beginner Tips:
- 🟢 **Start with Backtest mode** - Test without real money first
- 🟢 **Use small amounts** - Start with ₹5,000-10,000 initially
- 🟢 **Monitor daily** - Check results and adjust strategy
- 🟢 **Set realistic expectations** - Not every prediction will be correct
- 🔴 **Never invest more than you can afford to lose**

---

## 📊 Understanding the Prediction System

### How the Bot Predicts Market Direction:

1. **USA Market Analysis (40% weight)**
   - If S&P 500 went up yesterday → Bullish signal for India
   - If S&P 500 went down → Bearish signal for India

2. **News Sentiment (30% weight)**
   - AI reads latest financial news
   - Positive news → Bullish signal
   - Negative news → Bearish signal

3. **Technical Indicators (30% weight)**
   - **RSI** (Relative Strength Index): Checks if stock is overbought/oversold
   - **EMA** (Exponential Moving Average): Trend direction
   - **VWAP** (Volume Weighted Average Price): Fair value check

### Prediction Timing:
- ⏰ **Generated**: After US market closes (around 2:00 AM IST)
- ⏰ **Freezes**: Before Indian market opens (9:15 AM IST)
- ⏰ **Verified**: After Indian market closes (3:30 PM IST)

---

## 📱 Live Data Updates

### Real-time Updates (Every 1 Second):
- 🕐 Current time with seconds
- 📊 Nifty 50 Index price and % change
- 💰 Stock prices
- 💵 Profit/Loss

### What the Live Indicators Mean:

| Indicator | Meaning |
|-----------|---------|
| 🟢 Green dot pulsing | Data is updating live |
| ↗ Up arrow | Price/index going UP |
| ↘ Down arrow | Price/index going DOWN |
| → Neutral arrow | No significant movement |
| "Market Closed" | Trading hours ended |

---

## 🕐 Market Timings

### Indian Market (NSE):
- **Open**: 9:15 AM IST
- **Close**: 3:30 PM IST
- **Trading Days**: Monday - Friday

### US Market (S&P 500):
- **Open**: 9:30 AM ET (7:00 PM IST)
- **Close**: 4:00 PM ET (1:30 AM IST next day)

### Bot Behavior:
- **Before 9:15 AM IST**: Shows prediction, no trading
- **9:15 AM - 2:30 PM IST**: Active trading window
- **After 2:30 PM IST**: Auto-closes all positions (safety)
- **After 3:30 PM IST**: Market closed, updates prediction accuracy

---

## 📈 Viewing Historical Performance

### Prediction History Table:
- Shows all past predictions with actual results
- **Green** = Correct prediction ✅
- **Red** = Incorrect prediction ❌
- **Analysis** column explains why prediction succeeded/failed

### Download Data:
- Click "Download Excel" button to export full history
- Analyze your bot's performance over time

---

## ⚠️ Important Disclaimers

1. **Not Financial Advice**: This is an educational/automation tool
2. **Risk Warning**: Stock trading involves risk of loss
3. **No Guarantees**: Past performance doesn't guarantee future results
4. **Test First**: Always backtest before live trading
5. **Your Responsibility**: You are responsible for all trades executed

---

## 🔧 Configuration

### Editable Settings (via Dashboard):
- **Auto-close Time**: When to exit all positions (default: 2:30 PM IST)
- **Max Trades per Day**: Risk control (default: 3)
- **Symbol**: Which stock to trade (default: RELIANCE)
- **API Keys**: Zerodha and News API credentials

---

## 📞 Support & Learning Resources

### Learn More About:
- **NSE**: https://www.nseindia.com
- **Zerodha**: https://zerodha.com
- **Kite Connect API**: https://kite.trade/docs/connect/v3/
- **Technical Indicators**: https://www.investopedia.com

### Common Issues:
1. **"Market Closed" showing**: Normal outside 9:15 AM - 3:30 PM IST
2. **"Waiting for US market to close"**: Prediction generated after 2:00 AM IST
3. **Data not updating**: Check internet connection, refresh browser
4. **API errors**: Verify API keys in Settings

---

## 🚀 Next Steps for Beginners

1. ✅ **Setup the bot** (follow installation above)
2. ✅ **Explore Dashboard** (click all info icons to learn)
3. ✅ **Run Backtest** (test with historical data)
4. ✅ **Watch Live mode** (observe without trading)
5. ✅ **Start small** (trade with small capital first)
6. ✅ **Learn continuously** (read logs, analyze results)

---

## 📄 License & Credits

- Built with Python, Flask, yfinance, and Zerodha Kite Connect
- Uses Material Design for beautiful UI
- Sentiment analysis powered by FinBERT/VADER
- Market data from NSE and Yahoo Finance

---

**Happy Trading! 🎉📈**

*Remember: The best trader is an informed trader. Take time to understand before you invest.*
