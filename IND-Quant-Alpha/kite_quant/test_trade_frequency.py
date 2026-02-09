"""
Test script for Dynamic Trade Frequency Engine
Validates capital-based frequency calculation and drawdown logic
"""
from engine.trade_frequency import (
    calculate_max_trades_per_hour,
    get_trade_frequency_config,
    validate_trade_frequency_config,
    DEFAULT_TRADE_FREQUENCY_CONFIG
)


def test_capital_slabs():
    """Test that different capital levels get correct trade limits"""
    print("\n=== TEST 1: Capital Slab Matching ===")
    
    test_cases = [
        (25000, 0, 2, "NORMAL"),      # Low capital -> 2 trades/hour
        (75000, 0, 3, "NORMAL"),      # Mid capital -> 3 trades/hour
        (250000, 0, 4, "NORMAL"),     # Higher capital -> 4 trades/hour
        (600000, 0, 5, "NORMAL"),     # High capital -> 5 trades/hour
    ]
    
    passed = 0
    for capital, daily_pnl, expected_limit, expected_mode in test_cases:
        limit, mode = calculate_max_trades_per_hour(capital, daily_pnl)
        status = "[PASS]" if limit == expected_limit and mode == expected_mode else "[FAIL]"
        print(f"{status} Capital Rs.{capital:,} -> {limit} trades/hour (Mode: {mode})")
        if limit == expected_limit and mode == expected_mode:
            passed += 1
    
    print(f"\nResult: {passed}/{len(test_cases)} passed\n")
    return passed == len(test_cases)


def test_drawdown_reduction():
    """Test that drawdown triggers frequency reduction"""
    print("\n=== TEST 2: Drawdown-Based Reduction ===")
    
    capital = 100000
    test_cases = [
        (0, "NORMAL", "No loss"),
        (-500, "NORMAL", "Minor loss (0.5%)"),
        (-2100, "REDUCED", "Soft drawdown (2.1%)"),
        (-3000, "REDUCED", "Moderate loss (3%)"),
        (-5500, "HARD_LIMIT", "Hard drawdown (5.5%)"),
    ]
    
    passed = 0
    for daily_pnl, expected_mode, description in test_cases:
        limit, mode = calculate_max_trades_per_hour(capital, daily_pnl)
        status = "[PASS]" if mode == expected_mode else "[FAIL]"
        print(f"{status} {description}: PnL Rs.{daily_pnl:,} -> Mode: {mode}, Limit: {limit}/hour")
        if mode == expected_mode:
            passed += 1
    
    print(f"\nResult: {passed}/{len(test_cases)} passed\n")
    return passed == len(test_cases)


def test_frequency_reduction_math():
    """Test that REDUCED mode cuts frequency by 50%"""
    print("\n=== TEST 3: Frequency Reduction Math ===")
    
    # Capital in 4-trades slab, with 2% drawdown (should reduce to 2 trades)
    capital = 250000
    daily_pnl = -5000  # 2% loss
    
    limit, mode = calculate_max_trades_per_hour(capital, daily_pnl)
    
    expected_mode = "REDUCED"
    expected_limit = 2  # 4 * 0.5 = 2
    
    passed = mode == expected_mode and limit == expected_limit
    status = "[PASS]" if passed else "[FAIL]"
    
    print(f"{status} Capital Rs.{capital:,}, Loss Rs.{daily_pnl:,}")
    print(f"  Expected: {expected_limit} trades/hour ({expected_mode})")
    print(f"  Got: {limit} trades/hour ({mode})")
    print(f"\nResult: {'PASSED' if passed else 'FAILED'}\n")
    
    return passed


def test_hard_limit_enforcement():
    """Test that hard drawdown limits to 1 trade/hour"""
    print("\n=== TEST 4: Hard Limit Enforcement ===")
    
    # Test across different capital levels - all should limit to 1 trade
    test_cases = [
        (50000, -2600),    # 5.2% loss on low capital
        (200000, -10500),  # 5.25% loss on mid capital
        (700000, -36000),  # 5.14% loss on high capital
    ]
    
    passed = 0
    for capital, daily_pnl in test_cases:
        limit, mode = calculate_max_trades_per_hour(capital, daily_pnl)
        
        expected_mode = "HARD_LIMIT"
        expected_limit = 1
        
        test_passed = mode == expected_mode and limit == expected_limit
        status = "[PASS]" if test_passed else "[FAIL]"
        
        loss_pct = abs(daily_pnl / capital * 100)
        print(f"{status} Capital Rs.{capital:,}, Loss {loss_pct:.1f}% -> {limit} trade/hour ({mode})")
        
        if test_passed:
            passed += 1
    
    print(f"\nResult: {passed}/{len(test_cases)} passed\n")
    return passed == len(test_cases)


def test_config_validation():
    """Test configuration validation"""
    print("\n=== TEST 5: Config Validation ===")
    
    # Valid config
    valid_config = DEFAULT_TRADE_FREQUENCY_CONFIG.copy()
    test1 = validate_trade_frequency_config(valid_config)
    print(f"[{'PASS' if test1 else 'FAIL'}] Default config is valid")
    
    # Invalid: max_hourly_cap too high
    invalid_config_1 = valid_config.copy()
    invalid_config_1["max_hourly_cap"] = 15
    test2 = not validate_trade_frequency_config(invalid_config_1)
    print(f"[{'PASS' if test2 else 'FAIL'}] Rejects max_hourly_cap > 10")
    
    # Invalid: drawdown percent out of range
    invalid_config_2 = valid_config.copy()
    invalid_config_2["drawdown_trigger_percent"] = 1.5  # > 1
    test3 = not validate_trade_frequency_config(invalid_config_2)
    print(f"[{'PASS' if test3 else 'FAIL'}] Rejects drawdown_trigger_percent > 1")
    
    # Invalid: trades per hour too high
    invalid_config_3 = valid_config.copy()
    invalid_config_3["rules"][0]["max_trades_per_hour"] = 15
    test4 = not validate_trade_frequency_config(invalid_config_3)
    print(f"[{'PASS' if test4 else 'FAIL'}] Rejects max_trades_per_hour > 10")
    
    passed = sum([test1, test2, test3, test4])
    print(f"\nResult: {passed}/4 passed\n")
    
    return passed == 4


def test_minimum_one_trade():
    """Test that frequency never goes below 1 trade/hour"""
    print("\n=== TEST 6: Minimum 1 Trade Guarantee ===")
    
    # Even with massive loss and low capital, should still allow 1 trade
    capital = 10000
    daily_pnl = -3000  # 30% loss (!!)
    
    limit, mode = calculate_max_trades_per_hour(capital, daily_pnl)
    
    passed = limit >= 1
    status = "[PASS]" if passed else "[FAIL]"
    
    print(f"{status} Extreme loss (30%) -> Still allows {limit} trade/hour")
    print(f"\nResult: {'PASSED' if passed else 'FAILED'}\n")
    
    return passed


def run_all_tests():
    """Run complete test suite"""
    print("\n" + "="*60)
    print("  DYNAMIC TRADE FREQUENCY ENGINE - TEST SUITE")
    print("="*60)
    
    tests = [
        ("Capital Slab Matching", test_capital_slabs),
        ("Drawdown Reduction", test_drawdown_reduction),
        ("Frequency Reduction Math", test_frequency_reduction_math),
        ("Hard Limit Enforcement", test_hard_limit_enforcement),
        ("Config Validation", test_config_validation),
        ("Minimum 1 Trade Guarantee", test_minimum_one_trade),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n[ERROR] {name} failed with exception: {e}\n")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")
    
    print(f"\n{'='*60}")
    print(f"  OVERALL: {total_passed}/{total_tests} test suites passed")
    print(f"{'='*60}\n")
    
    if total_passed == total_tests:
        print("[SUCCESS] All tests passed! Dynamic frequency system is working correctly.\n")
        return True
    else:
        print("[WARNING] Some tests failed. Review the output above.\n")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
