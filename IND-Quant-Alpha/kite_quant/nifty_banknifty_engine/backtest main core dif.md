You’re right to want backtest to simulate live/paper. Right now it doesn’t do that fully, so the gap is real.
Why it’s “not good” right now
Backtest: Decides at every 5m bar using candle close (and possibly a different entry path than the engine).
Live/Paper: Decides every 60 seconds using live LTP and the session engine logic.
So they don’t use the same clock (5m bars vs 60s ticks) or the same price (bar close vs LTP). That’s why backtest P&L can differ a lot from live/paper — it’s not a faithful simulation of the engine.
What would make it “good” (backtest ≈ live/paper)
Backtest would need to replay the day like the engine:
Same timing: Step through the day in 60-second steps (or at least at the same decision times the engine would use), not “one decision per 5m bar”.
Same logic: At each step run the same entry/exit code as the session engine (e.g. _check_entry_real / should_enter_trade with the same rules and AI).
Same price source: At each step use the same price the engine would see — e.g. “last closed 5m candle’s close” or, if you had it, actual LTP at that time. Not a different bar or different OHLC.
Then:
Backtest on today’s data = “If the engine had run today with this data, what would it have done?”
That would be much closer to what you’d get in paper/live on the same day (still not identical because of real LTP vs replayed price, but far more comparable).
So: yes, today it’s not good for your goal; to make backtest a proper simulator of live/paper, it needs to be changed to replay the session engine (same 60s tick, same logic, same price source) instead of the current “one decision per 5m bar” loop. I can outline concrete code changes for that in your repo if you want to implement it.