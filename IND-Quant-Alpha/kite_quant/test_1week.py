"""
Quick 1-week backtest test
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from engine import config_store
config_store.apply_config_to_env()

from app import _run_ai_backtest
from datetime import date, timedelta
import logging

# Show INFO logs
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Test 1 week
end_date = date.today() - timedelta(days=5)
start_date = end_date - timedelta(days=7)

print(f"\nRunning 1-week backtest: {start_date} to {end_date}")
print("="*80)

result = _run_ai_backtest(
    instrument="NIFTY 50",
    from_date=start_date,
    to_date=end_date,
    timeframe="5m",
    initial_capital=10000,
    risk_percent=2.0,
    ai_enabled=False,  # Disable AI for now due to context error
    ai_check_interval=60
)

print("\n" + "="*80)
print("BACKTEST RESULTS")
print("="*80)

if result.get("success"):
    print(f"Net P&L: Rs.{result.get('net_pnl', 0):,.2f}")
    print(f"Total Trades: {result.get('total_trades', 0)}")
    print(f"Wins: {result.get('wins', 0)} | Losses: {result.get('losses', 0)}")
    print(f"Win Rate: {result.get('win_rate', 0):.1f}%")
    print(f"Best Day: Rs.{result.get('best_day_pnl', 0):,.2f}")
    print(f"Worst Day: Rs.{result.get('worst_day_pnl', 0):,.2f}")
    print(f"AI Switches: {result.get('ai_switches', 0)}")
    
    print("\nDaily Breakdown:")
    print(f"{'Date':<12} {'Trades':<8} {'P&L':<12} {'Cumulative':<12} {'Freq Mode':<12}")
    print("-"*80)
    for day in result.get('daily_breakdown', []):
        print(f"{day['date']:<12} {day['trades']:<8} Rs.{day['pnl']:<9.2f} Rs.{day['cumulative_pnl']:<9.2f} {day.get('frequency_mode', 'N/A'):<12}")
else:
    print(f"ERROR: {result.get('error', 'Unknown error')}")

print("="*80)
