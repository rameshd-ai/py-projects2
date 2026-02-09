# Algo status — active only

Swing and inactive algos have been **removed** from `config/algos.json`. Only intraday-executable algos remain.

---

## Active (32)

| # | ID | Name |
|---|----|------|
| 1 | momentum_breakout | Momentum Breakout |
| 2 | vwap_trend_ride | VWAP Trend Ride |
| 3 | pullback_continuation | Pullback Continuation |
| 4 | orb_opening_range_breakout | Opening Range Breakout (ORB) |
| 5 | rsi_reversal_fade | RSI Reversal Fade |
| 6 | bollinger_mean_reversion | Bollinger Band Mean Reversion |
| 7 | vwap_mean_reversion | VWAP Mean Reversion |
| 8 | liquidity_sweep_reversal | Liquidity Sweep Reversal |
| 9 | inside_bar_breakout | Inside Bar Breakout |
| 10 | news_volatility_burst | News Volatility Burst |
| 11 | time_based_volatility_play | Time-Based Volatility Play |
| 12 | gamma_scalping_lite | Gamma Scalping Lite |
| 13 | sector_rotation_momentum | Sector Rotation Momentum |
| 14 | index_lead_stock_lag | Index Lead – Stock Lag |
| 15 | relative_strength_breakout | Relative Strength Breakout |
| 16 | volume_climax_reversal | Volume Climax Reversal |
| 17 | trend_day_vwap_hold | Trend Day VWAP Hold |
| 18 | ema_ribbon_trend_alignment | EMA Ribbon Trend Alignment |
| 19 | range_compression_breakout | Range Compression Breakout |
| 20 | failed_breakdown_trap | Failed Breakdown / Breakdown Trap |
| 21 | vwap_reclaim | VWAP Reclaim |
| 22 | volume_dry_up_breakout | Volume Dry-Up Breakout |
| 23 | daily_breakout_continuation | Daily Breakout Continuation |
| 24 | pullback_20_50_dma | Pullback to 20/50 DMA |
| 25 | swing_rsi_compression_breakout | Swing RSI Compression Breakout |
| 26 | swing_volume_accumulation | Swing Volume Accumulation |
| 27 | multi_timeframe_alignment | Multi-Timeframe Alignment |
| 28 | liquidity_zone_reaction | Liquidity Zone Reaction |
| 29 | order_flow_imbalance_proxy | Order Flow Imbalance Proxy |
| 30 | volatility_contraction_expansion | Volatility Contraction → Expansion Model |
| 31 | time_of_day_behavior | Time-of-Day Behavior Model |
| 32 | smart_money_trap_detection | Smart Money Trap Detection |

---

## Removed (no longer in library)

These were removed from `config/algos.json` (swing / inactive / engine-level):

- iv_expansion_play, straddle_breakout, weekly_range_breakout, gap_and_go_swing, stage2_trend_breakout, darvas_box_breakout, relative_strength_swing_leader, trendline_break_retest, market_regime_detection, options_flow_bias, volatility_regime_switch, risk_adaptive_position_sizing

IV Expansion was also removed from the strategy registry. The file `strategies/iv_expansion_play.py` remains in the repo if you want to re-add the algo later.
