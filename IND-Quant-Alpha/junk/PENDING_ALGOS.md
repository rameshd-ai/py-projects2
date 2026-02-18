# Pending Algos to Be Developed

**35 algos** (40 total − 5 implemented) have no executable strategy logic yet (they fall back to Momentum Breakout). Use this list with GPT: ask for **best way to implement** and **Python code** for `check_entry`, `check_exit`, `get_stop_loss`, `get_target` in the same style as existing strategies in `kite_quant/strategies/` (e.g. `momentum_breakout.py`, `rsi_reversal.py`).

**Reference:** Each strategy must inherit `BaseStrategy`, take `(instrument, data_provider)`, and use `self.data.get_recent_candles()`, `self.data.get_ltp()`, `self.data.get_vwap()`, `self.data.get_rsi()`, and for exit LTP use `self._get_exit_ltp(trade)` so NFO options work.

---

## 1. pullback_continuation
**Name:** Pullback Continuation  
**Entry:** Strong trend intact; wait for pullback to VWAP/EMA. Enter on rejection candle (bullish/bearish) + volume return in direction of original trend.  
**Description:** In a strong trend, wait for pullback to VWAP/EMA. Enter when price shows rejection (bullish/bearish candle + volume return) in direction of original trend.

---

## 2. bollinger_mean_reversion
**Name:** Bollinger Band Mean Reversion  
**Entry:** Price closes outside Bollinger Band with rejection wick; enter toward middle band. Exit near VWAP or mid-band.  
**Description:** When price closes outside Bollinger Band and shows rejection wick, enter trade toward middle band. Exit near VWAP or mid-band.

---

## 3. vwap_mean_reversion
**Name:** VWAP Mean Reversion  
**Entry:** Price overextended from VWAP; volume declining on extension; enter snapback toward VWAP.  
**Description:** When price deviates far from VWAP (overextended move) and volume declines, expect snapback toward VWAP.

---

## 4. liquidity_sweep_reversal
**Name:** Liquidity Sweep Reversal  
**Entry:** Price takes out previous high/low (sweep); quick reversal with strong opposite candle + volume spike; enter reversal targeting prior range.  
**Description:** If price takes out previous high/low and quickly reverses with strong opposite candle and volume spike, enter reversal trade targeting prior range.

---

## 5. inside_bar_breakout
**Name:** Inside Bar Breakout  
**Entry:** Tight consolidation (inside previous candle range); enter on breakout of range with volume expansion.  
**Description:** Detect tight consolidation candle (inside previous candle range). Enter on breakout of that range with volume expansion.

---

## 6. news_volatility_burst
**Name:** News Volatility Burst  
**Entry:** Major news catalyst; volume surge; enter in direction of first strong impulse; tight trailing stop.  
**Description:** When major news hits and volume surges, enter in direction of first strong impulse move. Use tight trailing stop.

---

## 7. time_based_volatility_play
**Name:** Time-Based Volatility Play  
**Entry:** Trade during volatility windows: open, post-lunch, closing hour; combine with breakout or momentum setup.  
**Description:** Increase probability weight during known volatility windows (market open, post-lunch, closing hour). Combine with breakout or momentum setup.

---

## 8. iv_expansion_play
**Name:** IV Expansion Play  
**Entry:** IV below recent average; catalyst expected within holding period; long options for IV expansion.  
**Description:** When IV is low but expected move or event is near, buy options expecting IV expansion and price move.

---

## 9. gamma_scalping_lite
**Name:** Gamma Scalping Lite  
**Entry:** Quick momentum move in high volatility; tight stop; small target; exit quickly.  
**Description:** In high volatility environment, scalp quick option price swings using fast momentum bursts. Exit quickly.

---

## 10. straddle_breakout
**Name:** Straddle Breakout  
**Entry:** Event or big move expected; direction unclear; ATM straddle; exit losing leg when direction confirms.  
**Description:** When expecting big move but direction unclear, take ATM straddle. Exit losing leg early when direction confirms.

---

## 11. sector_rotation_momentum
**Name:** Sector Rotation Momentum  
**Entry:** Identify strongest performing sector; select top relative strength stock in that sector; enter momentum trade.  
**Description:** Detect strongest performing sector. Select top relative strength stock from that sector for momentum trade.

---

## 12. relative_strength_breakout
**Name:** Relative Strength Breakout  
**Entry:** Stock outperforming index intraday; enter on breakout of consolidation.  
**Description:** Choose stocks outperforming index on intraday strength. Enter on breakout of consolidation.

---

## 13. volume_climax_reversal
**Name:** Volume Climax Reversal  
**Entry:** Extreme volume spike + large candle; wait for exhaustion and reversal signal; enter in reversal direction.  
**Description:** After extreme volume spike and large candle, wait for exhaustion and reversal signal.

---

## 14. trend_day_vwap_hold
**Name:** Trend Day VWAP Hold  
**Entry:** Price above VWAP for extended time; buy shallow pullbacks; exit only on VWAP breakdown.  
**Description:** If price stays above VWAP for extended time with shallow pullbacks, keep buying dips. Exit only on VWAP breakdown.

---

## 15. ema_ribbon_trend_alignment
**Name:** EMA Ribbon Trend Alignment  
**Entry:** All EMAs stacked in one direction (9 above 20 above 50); enter on pullback to short (9) EMA.  
**Description:** Use 9/20/50 EMA alignment. Enter when all EMAs stacked in one direction and price pulls back to short EMA.

---

## 16. range_compression_breakout
**Name:** Range Compression Breakout  
**Entry:** Decreasing ATR and tight candles; enter on expansion with volume spike.  
**Description:** Detect decreasing ATR + tight candles. Enter on expansion with volume spike.

---

## 17. failed_breakdown_trap
**Name:** Failed Breakdown / Breakdown Trap  
**Entry:** Price breaks support; quick reclaim with strong bullish candle; enter long (trap reversal).  
**Description:** Price breaks support, quickly reclaims level with strong bullish candle → long trade (trap reversal).

---

## 18. vwap_reclaim
**Name:** VWAP Reclaim  
**Entry:** Price below VWAP in morning; reclaims and holds above VWAP; enter bullish shift.  
**Description:** If price below VWAP early, then reclaims and holds above → bullish shift trade.

---

## 19. volume_dry_up_breakout
**Name:** Volume Dry-Up Breakout  
**Entry:** Volume contracts heavily in consolidation; enter on sudden volume expansion candle.  
**Description:** Volume contracts heavily, then sudden expansion candle → breakout trade.

---

## 20. daily_breakout_continuation
**Name:** Daily Breakout Continuation  
**Entry:** Break multi-day resistance with strong volume; hold for follow-through days.  
**Description:** Stock breaks multi-day resistance with strong volume → hold for follow-through days.

---

## 21. pullback_20_50_dma
**Name:** Pullback to 20/50 DMA  
**Entry:** Strong uptrend intact; buy pullback to 20 or 50 DMA.  
**Description:** In strong uptrend, buy pullbacks to 20 or 50 day moving average.

---

## 22. weekly_range_breakout
**Name:** Weekly Range Breakout  
**Entry:** Break weekly high or low; volume expansion; hold for multi-day momentum.  
**Description:** Break of weekly high/low with volume expansion → multi-day momentum.

---

## 23. gap_and_go_swing
**Name:** Gap & Go (Swing Version)  
**Entry:** Strong gap on earnings/news; high volume; buy first consolidation.  
**Description:** Strong earnings/news gap with high volume → buy first consolidation.

---

## 24. stage2_trend_breakout
**Name:** Stage 2 Trend Breakout (Stan Weinstein)  
**Entry:** Long base complete; breakout with rising volume; start of trend phase.  
**Description:** Stock exits long base with rising volume → start of big trend phase.

---

## 25. swing_rsi_compression_breakout
**Name:** Swing RSI Compression Breakout  
**Entry:** RSI compressed 40-60 for days; enter on RSI expansion; momentum swing.  
**Description:** RSI stays compressed 40–60 for days then expands → start of momentum swing.

---

## 26. darvas_box_breakout
**Name:** Darvas Box Breakout  
**Entry:** Identify multi-week box; enter on breakout of box; trend continuation.  
**Description:** Price breaks out of multi-week box range → trend continuation.

---

## 27. relative_strength_swing_leader
**Name:** Relative Strength Swing Leader  
**Entry:** Stock outperforming index for several days; buy on pullbacks.  
**Description:** Stock outperforming index for several days → buy on pullbacks.

---

## 28. trendline_break_retest
**Name:** Trendline Break + Retest  
**Entry:** Break descending trendline; retest holds; enter bullish swing.  
**Description:** Break of descending trendline + successful retest → bullish swing.

---

## 29. swing_volume_accumulation
**Name:** Swing Volume Accumulation  
**Entry:** Price flat, volume rising over days; anticipate breakout; enter on break.  
**Description:** Price flat but volume rising over days → accumulation → breakout soon.

---

## 30. market_regime_detection
**Name:** Market Regime Detection  
**Entry:** Detect regime: Trend / Range / Volatile / Expiry; activate only matching algos.  
**Description:** AI first decides: Trend Day, Range Day, Volatile News Day, or Expiry/Low Liquidity Day. Then only activates matching algos.

---

## 31. multi_timeframe_alignment
**Name:** Multi-Timeframe Alignment  
**Entry:** 5m trend aligns with 15m and 1h; trade in aligned direction.  
**Description:** Trade only when 5m trend = 15m trend = 1h bias.

---

## 32. liquidity_zone_reaction
**Name:** Liquidity Zone Reaction  
**Entry:** Mark PDC high/low, VWAP bands, OI levels; trade reactions from zones.  
**Description:** AI marks previous day high/low, VWAP bands, option OI levels. Trades reactions from these zones.

---

## 33. order_flow_imbalance_proxy
**Name:** Order Flow Imbalance Proxy  
**Entry:** Volume spike + large candle body; use as institutional proxy; trade in direction.  
**Description:** Use volume spikes + large candle bodies as proxy for institutional activity.

---

## 34. volatility_contraction_expansion
**Name:** Volatility Contraction → Expansion Model  
**Entry:** Detect ATR contraction; prepare for expansion; enter on breakout.  
**Description:** Detect shrinking ATR → prepare breakout mode.

---

## 35. time_of_day_behavior
**Name:** Time-of-Day Behavior Model  
**Entry:** Morning: breakout bias; Midday: mean reversion; Power hour: momentum and closing.  
**Description:** Morning = breakout bias; Midday = mean reversion; Power hour = momentum + closing moves.

---

## 36. smart_money_trap_detection
**Name:** Smart Money Trap Detection  
**Entry:** Detect low-volume breakout; detect long wick fakeouts; mark trap probability.  
**Description:** Detect breakout without volume, long wick fakeouts. AI marks trap probability.

---

## 37. options_flow_bias
**Name:** Options Flow Bias (Advanced)  
**Entry:** Call OI unwinding can imply bullish; Put OI unwinding can imply bearish; use as bias.  
**Description:** If available: High Call OI unwinding → bullish; High Put OI unwinding → bearish.

---

## 38. volatility_regime_switch
**Name:** Volatility Regime Switch  
**Entry:** Low IV: option buying; High IV: option selling/credit spreads; switch by regime.  
**Description:** AI shifts between option buying strategies (low IV) and option selling/credit spreads (high IV).

---

## 39. risk_adaptive_position_sizing
**Name:** Risk-Adaptive Position Sizing  
**Entry:** Reduce size in high volatility; reduce on news days; reduce in late session.  
**Description:** AI reduces lot size in high volatility, news days, and late session.

---

**Already implemented (5):** momentum_breakout, vwap_trend_ride, rsi_reversal_fade, orb_opening_range_breakout, index_lead_stock_lag.

After implementing an algo, add its class to `kite_quant/strategies/strategy_registry.py` in `STRATEGY_MAP` (by id and name) and create `kite_quant/strategies/<module>.py` following existing patterns.
