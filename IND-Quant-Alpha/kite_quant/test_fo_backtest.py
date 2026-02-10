"""
Test F&O backtesting to verify options trading is enabled
"""
import sys
sys.path.insert(0, 'd:/GItHIbProjects/py-projects2/IND-Quant-Alpha/kite_quant')
from datetime import datetime
from app import _run_ai_backtest

# Run 1-day backtest for NIFTY 50 with F&O
from_date = datetime(2026, 2, 5)
to_date = datetime(2026, 2, 5)

print('=' * 70)
print('=== Running 1-Day NIFTY 50 Backtest (F&O Options) ===')
print('=' * 70)
print(f'Date: {from_date.date()}')
print(f'Initial Capital: Rs.10,000')
print(f'Risk Per Trade: 2%')
print('-' * 70)

result = _run_ai_backtest(
    instrument='NIFTY 50',
    from_date=from_date,
    to_date=to_date,
    initial_capital=10000,
    timeframe='5minute',
    risk_percent=2.0,
    ai_check_interval=30
)

if result.get('success'):
    summary = result['summary']
    print()
    print('=' * 70)
    print('=== BACKTEST RESULTS ===')
    print('=' * 70)
    print(f'Net P&L: Rs.{summary["net_pnl"]:.2f}')
    print(f'Total Trades: {summary["total_trades"]}')
    print(f'Winning Trades: {summary["winning_trades"]}')
    print(f'Losing Trades: {summary["losing_trades"]}')
    print(f'Final Capital: Rs.{summary["ending_capital"]:.2f}')
    print(f'AI Strategy Switches: {summary["ai_switches"]}')
    print(f'Return: {summary["return_pct"]:.2f}%')
    print('-' * 70)
    
    if result['trades']:
        print()
        print('=== TRADE DETAILS ===')
        for i, trade in enumerate(result['trades'], 1):
            pnl_sign = '+' if trade['pnl'] >= 0 else ''
            print(f'{i}. {trade["entry_time"]} -> {trade["exit_time"]}')
            print(f'   Strategy: {trade["strategy"]}')
            print(f'   Entry: Rs.{trade["entry_price"]:.2f} | Exit: Rs.{trade["exit_price"]:.2f}')
            print(f'   Qty: {trade["qty"]} | P&L: {pnl_sign}Rs.{trade["pnl"]:.2f} [{trade["exit_reason"]}]')
            print()
    else:
        print('No trades executed.')
else:
    print('=' * 70)
    print(f'ERROR: {result.get("error", "Unknown error")}')
    print('=' * 70)
