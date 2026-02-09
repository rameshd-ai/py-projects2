"""
Comprehensive algo testing script - works even when market is closed.
Tests all strategies with mock data to verify they're functioning correctly.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from strategies import data_provider
from strategies.strategy_registry import STRATEGY_MAP
from datetime import datetime, timedelta
import json

# Mock market data
MOCK_CANDLES = [
    {"timestamp": "2024-02-09 09:20:00", "open": 21850, "high": 21880, "low": 21840, "close": 21870, "volume": 150000},
    {"timestamp": "2024-02-09 09:25:00", "open": 21870, "high": 21920, "low": 21865, "close": 21915, "volume": 180000},
    {"timestamp": "2024-02-09 09:30:00", "open": 21915, "high": 21950, "low": 21910, "close": 21945, "volume": 200000},
    {"timestamp": "2024-02-09 09:35:00", "open": 21945, "high": 21980, "low": 21940, "close": 21970, "volume": 220000},
    {"timestamp": "2024-02-09 09:40:00", "open": 21970, "high": 22000, "low": 21960, "close": 21990, "volume": 250000},
    {"timestamp": "2024-02-09 09:45:00", "open": 21990, "high": 22020, "low": 21985, "close": 22010, "volume": 230000},
    {"timestamp": "2024-02-09 09:50:00", "open": 22010, "high": 22035, "low": 22005, "close": 22030, "volume": 240000},
    {"timestamp": "2024-02-09 09:55:00", "open": 22030, "high": 22050, "low": 22025, "close": 22045, "volume": 260000},
    {"timestamp": "2024-02-09 10:00:00", "open": 22045, "high": 22070, "low": 22040, "close": 22065, "volume": 270000},
    {"timestamp": "2024-02-09 10:05:00", "open": 22065, "high": 22080, "low": 22055, "close": 22070, "volume": 240000},
]


class MockDataProvider:
    """Mock data provider for testing strategies"""
    
    def __init__(self, candles=None, ltp=22070):
        self.candles = candles or MOCK_CANDLES
        self.ltp = ltp
    
    def get_recent_candles(self, instrument, interval="5m", count=10, period="1d"):
        """Return mock candles"""
        return self.candles[-count:] if count else self.candles
    
    def get_ltp(self, instrument):
        """Return mock LTP"""
        return self.ltp
    
    def get_quote(self, instrument, exchange="NSE"):
        """Return mock quote"""
        return {
            "last": self.ltp,
            "last_price": self.ltp,
            "open": self.candles[0]["open"] if self.candles else self.ltp,
            "high": max(c["high"] for c in self.candles) if self.candles else self.ltp,
            "low": min(c["low"] for c in self.candles) if self.candles else self.ltp,
            "close": self.candles[-1]["close"] if self.candles else self.ltp,
            "volume": sum(c["volume"] for c in self.candles) if self.candles else 1000000,
        }
    
    def get_rsi(self, instrument, interval="5m", period=14, count=None, data_period="2d"):
        """Return mock RSI"""
        return 65.5  # Neutral RSI
    
    def get_vwap(self, instrument, interval="5m", count=50, period="3d"):
        """Return mock VWAP"""
        if not self.candles:
            return self.ltp
        total_volume = sum(c["volume"] for c in self.candles)
        if total_volume == 0:
            return self.ltp
        vwap = sum(c["close"] * c["volume"] for c in self.candles) / total_volume
        return vwap


def test_strategy(strategy_name, strategy_class, instrument="NIFTY"):
    """Test a single strategy with mock data"""
    print(f"\n{'='*60}")
    print(f"Testing: {strategy_name}")
    print(f"{'='*60}")
    
    try:
        # Create mock data provider
        mock_data = MockDataProvider()
        
        # Instantiate strategy
        strategy = strategy_class(instrument, mock_data)
        
        # Test check_entry
        print("Testing check_entry()...")
        entry_result = strategy.check_entry()
        
        if isinstance(entry_result, dict):
            can_enter = entry_result.get("can_enter", False)
            entry_price = entry_result.get("entry_price")
            reason = entry_result.get("reason", "No reason")
            conditions = entry_result.get("conditions", {})
            
            print(f"  [+] Can Enter: {can_enter}")
            print(f"  [+] Entry Price: {entry_price}")
            print(f"  [+] Reason: {reason}")
            if conditions:
                print(f"  [+] Conditions:")
                for k, v in conditions.items():
                    status = "[OK]" if v else "[NO]"
                    print(f"      {status} {k}: {v}")
        else:
            can_enter, entry_price = entry_result
            print(f"  [+] Can Enter: {can_enter}")
            print(f"  [+] Entry Price: {entry_price}")
        
        # Test get_stop_loss and get_target
        if entry_price:
            print("\nTesting get_stop_loss()...")
            stop_loss = strategy.get_stop_loss(entry_price)
            print(f"  [+] Stop Loss: {stop_loss}")
            
            print("Testing get_target()...")
            target = strategy.get_target(entry_price)
            print(f"  [+] Target: {target}")
        
        # Test check_exit with mock trade
        print("\nTesting check_exit()...")
        mock_trade = {
            "entry_price": entry_price or 22000,
            "stop_loss": stop_loss if entry_price else 21900,
            "target": target if entry_price else 22100,
            "entry_time": datetime.now().isoformat(),
        }
        exit_reason = strategy.check_exit(mock_trade)
        print(f"  [+] Exit Reason: {exit_reason or 'None (hold position)'}")
        
        print(f"\n[PASS] {strategy_name} - ALL TESTS PASSED")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] {strategy_name} - FAILED")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_all_strategies():
    """Test all registered strategies"""
    print("\n" + "="*60)
    print("ALGO TESTING SUITE")
    print("="*60)
    print(f"Testing {len(STRATEGY_MAP)} strategies with mock market data")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {}
    passed = 0
    failed = 0
    
    # Get unique strategies (some have multiple names)
    tested = set()
    for name, strategy_class in STRATEGY_MAP.items():
        if strategy_class in tested:
            continue
        tested.add(strategy_class)
        
        success = test_strategy(name, strategy_class)
        results[name] = success
        
        if success:
            passed += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total Strategies: {len(tested)}")
    print(f"[PASS] Passed: {passed}")
    print(f"[FAIL] Failed: {failed}")
    print(f"Success Rate: {(passed/(passed+failed)*100):.1f}%")
    print("="*60)
    
    # List failed strategies
    if failed > 0:
        print("\n[WARNING] Failed Strategies:")
        for name, success in results.items():
            if not success:
                print(f"  - {name}")
    
    return passed, failed


def test_specific_strategy(strategy_name):
    """Test a specific strategy by name"""
    if strategy_name not in STRATEGY_MAP:
        print(f"[ERROR] Strategy '{strategy_name}' not found")
        print("\nAvailable strategies:")
        for name in sorted(set(STRATEGY_MAP.keys())):
            print(f"  - {name}")
        return False
    
    strategy_class = STRATEGY_MAP[strategy_name]
    return test_strategy(strategy_name, strategy_class)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test trading strategies with mock data")
    parser.add_argument("--strategy", "-s", type=str, help="Test specific strategy")
    parser.add_argument("--list", "-l", action="store_true", help="List all strategies")
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable Strategies:")
        print("="*60)
        tested = set()
        for name, strategy_class in STRATEGY_MAP.items():
            if strategy_class.__name__ not in tested:
                tested.add(strategy_class.__name__)
                print(f"  - {name}")
        print("="*60)
        print(f"\nTotal: {len(tested)} unique strategies")
    
    elif args.strategy:
        test_specific_strategy(args.strategy)
    
    else:
        # Run all tests
        passed, failed = test_all_strategies()
        sys.exit(0 if failed == 0 else 1)
