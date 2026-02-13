"""
Test script for paper trading workflow
Simulates the browser actions and monitors the trade lifecycle
"""
import requests
import time
import json
import sys
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:5000"
INVESTMENT_AMOUNT = 10000
INSTRUMENT = "NIFTY"

def print_header(text):
    print("\n" + "="*80)
    print(f" {text}")
    print("="*80)

def print_step(step_num, text):
    print(f"\n[STEP {step_num}] {text}")
    print("-" * 80)

def get_timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def test_page_load():
    """Test that the page loads successfully"""
    print_step(1, "Testing page load")
    try:
        response = requests.get(f"{BASE_URL}/dashboard/paper-trade", timeout=10)
        if response.status_code == 200:
            print(f"✓ [{get_timestamp()}] Page loaded successfully (status: {response.status_code})")
            print(f"  Content length: {len(response.text)} bytes")
            return True
        else:
            print(f"✗ [{get_timestamp()}] Page load failed (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"✗ [{get_timestamp()}] Error loading page: {e}")
        return False

def get_risk_config():
    """Get risk configuration"""
    print_step(2, f"Getting risk configuration for investment amount: ₹{INVESTMENT_AMOUNT}")
    try:
        response = requests.get(
            f"{BASE_URL}/api/paper-trade/risk-config",
            params={
                "investment_amount": INVESTMENT_AMOUNT,
                "risk_percent": 2
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ [{get_timestamp()}] Risk config retrieved:")
            print(f"  Max risk per trade: ₹{data.get('max_risk_per_trade', 'N/A')}")
            print(f"  Daily loss limit: ₹{data.get('daily_loss_limit', 'N/A')}")
            return True
        else:
            print(f"✗ [{get_timestamp()}] Failed to get risk config (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"✗ [{get_timestamp()}] Error getting risk config: {e}")
        return False

def start_paper_trade():
    """Start a paper trading session"""
    print_step(3, f"Starting paper trade (Instrument: {INSTRUMENT}, Amount: ₹{INVESTMENT_AMOUNT})")
    try:
        payload = {
            "instrument": INSTRUMENT,
            "investment_amount": INVESTMENT_AMOUNT,
            "ai_auto_switching_enabled": True
        }
        print(f"  Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            f"{BASE_URL}/api/paper-trade/execute",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"  Response status: {response.status_code}")
        print(f"  Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ [{get_timestamp()}] Trade button clicked - Response:")
            print(f"  {json.dumps(data, indent=2)}")
            
            if data.get('ok'):
                print(f"\n  ✓ Session started successfully!")
                print(f"  Message: {data.get('message', 'N/A')}")
                if 'recommendation' in data:
                    rec = data['recommendation']
                    print(f"  Recommendation:")
                    print(f"    - Option Type: {rec.get('optionType', 'N/A')}")
                    print(f"    - Strike: {rec.get('strike', 'N/A')}")
                    print(f"    - Strategy: {rec.get('strategyName', 'N/A')}")
                    print(f"    - Premium: ₹{rec.get('premium', 'N/A')}")
                if 'virtual_balance' in data:
                    print(f"  Virtual Balance: ₹{data['virtual_balance']}")
                return True, data
            else:
                print(f"✗ Trade failed: {data.get('error', 'Unknown error')}")
                return False, data
        else:
            print(f"✗ [{get_timestamp()}] Failed to start trade (status: {response.status_code})")
            print(f"  Response: {response.text[:500]}")
            return False, None
    except Exception as e:
        print(f"✗ [{get_timestamp()}] Error starting trade: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def get_trade_sessions():
    """Get current trade sessions"""
    try:
        response = requests.get(f"{BASE_URL}/api/trade-sessions", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"  Warning: Failed to get sessions (status: {response.status_code})")
            return None
    except Exception as e:
        print(f"  Warning: Error getting sessions: {e}")
        return None

def get_trade_history(mode="PAPER", today=True):
    """Get trade history"""
    try:
        params = {"mode": mode}
        if today:
            params["today"] = "1"
        response = requests.get(f"{BASE_URL}/api/trade-history", params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"  Warning: Failed to get history (status: {response.status_code})")
            return None
    except Exception as e:
        print(f"  Warning: Error getting history: {e}")
        return None

def monitor_trade_lifecycle(max_wait_minutes=8):
    """Monitor the trade lifecycle from 'Waiting to enter' to 'OPEN' to 'CLOSED'"""
    print_step(4, f"Monitoring trade lifecycle (max wait: {max_wait_minutes} minutes)")
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    check_interval = 5  # Check every 5 seconds
    
    waiting_detected = False
    open_detected = False
    open_detection_time = None
    
    check_count = 0
    
    while time.time() - start_time < max_wait_seconds:
        check_count += 1
        elapsed = int(time.time() - start_time)
        
        print(f"\n[CHECK #{check_count}] [{get_timestamp()}] Elapsed: {elapsed}s / {max_wait_seconds}s")
        
        # Get sessions
        sessions_data = get_trade_sessions()
        history_data = get_trade_history()
        
        if sessions_data:
            sessions = sessions_data.get('sessions', [])
            engine_running = sessions_data.get('engine_running')
            next_scan = sessions_data.get('next_scan')
            last_tick = sessions_data.get('last_tick')
            
            print(f"  Engine running: {engine_running}")
            print(f"  Next scan: {next_scan}s")
            print(f"  Last tick: {last_tick}")
            print(f"  Total sessions: {len(sessions)}")
            
            # Filter PAPER mode sessions
            paper_sessions = [s for s in sessions if (s.get('execution_mode') or s.get('mode', '')).upper() == 'PAPER']
            active_paper_sessions = [s for s in paper_sessions if s.get('status') == 'ACTIVE']
            
            print(f"  Active PAPER sessions: {len(active_paper_sessions)}")
            
            if active_paper_sessions:
                for idx, session in enumerate(active_paper_sessions):
                    session_id = session.get('sessionId') or session.get('session_id')
                    has_trade = session.get('current_trade') is not None
                    virtual_balance = session.get('virtual_balance')
                    
                    print(f"\n  Session #{idx+1}: {session_id}")
                    print(f"    - Has current_trade: {has_trade}")
                    print(f"    - Virtual balance: ₹{virtual_balance}")
                    
                    if not has_trade and not waiting_detected:
                        # Waiting to enter
                        print(f"    ✓ STATUS: 'Waiting to enter' detected!")
                        waiting_detected = True
                        rec = session.get('recommendation', {})
                        print(f"    - Recommendation:")
                        print(f"      * Option Type: {rec.get('optionType', 'N/A')}")
                        print(f"      * Strike: {rec.get('strike', 'N/A')}")
                        print(f"      * Strategy: {rec.get('strategyName', 'N/A')}")
                        print(f"      * Premium: ₹{rec.get('premium', 'N/A')}")
                    
                    if has_trade and not open_detected:
                        # Trade OPEN
                        print(f"    ✓ STATUS: 'OPEN' detected! Trade entered.")
                        open_detected = True
                        open_detection_time = time.time()
                        
                        trade = session['current_trade']
                        print(f"    - Trade details:")
                        print(f"      * Entry time: {trade.get('entry_time')}")
                        print(f"      * Entry price: ₹{trade.get('entry_price')}")
                        print(f"      * Quantity: {trade.get('qty')}")
                        print(f"      * Side: {trade.get('side')}")
                        print(f"      * Strategy: {trade.get('strategy_name')}")
                        
                        current_ltp = session.get('current_ltp')
                        if current_ltp:
                            print(f"      * Current LTP: ₹{current_ltp}")
        
        # Check trade history for closed trades
        if history_data:
            trades = history_data.get('trades', [])
            print(f"\n  Closed trades today: {len(trades)}")
            
            if trades:
                for idx, trade in enumerate(trades):
                    print(f"\n  ✓ CLOSED Trade #{idx+1}:")
                    print(f"    - Option Type: {trade.get('option_type')}")
                    print(f"    - Strike: {trade.get('strike')}")
                    print(f"    - Strategy: {trade.get('strategy')}")
                    print(f"    - Entry: {trade.get('entry_time')} @ ₹{trade.get('entry_price')}")
                    print(f"    - Exit: {trade.get('exit_time')} @ ₹{trade.get('exit_price')}")
                    print(f"    - Quantity: {trade.get('qty')}")
                    print(f"    - P&L: ₹{trade.get('pnl')}")
                    print(f"    - Exit Reason: {trade.get('exit_reason')}")
                
                # If we have closed trades, we're done
                print(f"\n✓ Trade lifecycle complete! Trade closed.")
                return True, {
                    'waiting_detected': waiting_detected,
                    'open_detected': open_detected,
                    'closed_detected': True,
                    'closed_trades': len(trades)
                }
        
        # Check if we should continue waiting
        if open_detected and open_detection_time:
            time_since_open = time.time() - open_detection_time
            if time_since_open > 300:  # 5 minutes after opening
                print(f"\n  Trade has been OPEN for {int(time_since_open)}s but hasn't closed yet.")
                print(f"  Continuing to monitor...")
        
        # Wait before next check
        print(f"\n  Waiting {check_interval}s before next check...")
        time.sleep(check_interval)
    
    # Timeout reached
    print(f"\n⚠ Monitoring timeout reached ({max_wait_minutes} minutes)")
    return False, {
        'waiting_detected': waiting_detected,
        'open_detected': open_detected,
        'closed_detected': False,
        'timeout': True
    }

def main():
    print_header("PAPER TRADING WORKFLOW TEST")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {BASE_URL}/dashboard/paper-trade")
    print(f"Investment Amount: ₹{INVESTMENT_AMOUNT}")
    print(f"Instrument: {INSTRUMENT}")
    
    # Test 1: Page load
    if not test_page_load():
        print("\n✗ Test failed: Could not load page")
        return
    
    # Test 2: Risk config
    if not get_risk_config():
        print("\n⚠ Warning: Could not get risk config, but continuing...")
    
    # Test 3: Start trade
    success, trade_data = start_paper_trade()
    if not success:
        print("\n✗ Test failed: Could not start paper trade")
        return
    
    # Test 4: Monitor lifecycle
    success, lifecycle_data = monitor_trade_lifecycle(max_wait_minutes=8)
    
    # Final report
    print_header("TEST SUMMARY")
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nResults:")
    print(f"  ✓ Page loaded: Yes")
    print(f"  ✓ TRADE button worked: Yes")
    print(f"  {'✓' if lifecycle_data.get('waiting_detected') else '✗'} 'Waiting to enter' appeared: {lifecycle_data.get('waiting_detected', False)}")
    print(f"  {'✓' if lifecycle_data.get('open_detected') else '✗'} Trade entered (OPEN status): {lifecycle_data.get('open_detected', False)}")
    print(f"  {'✓' if lifecycle_data.get('closed_detected') else '✗'} Trade closed: {lifecycle_data.get('closed_detected', False)}")
    
    if lifecycle_data.get('closed_trades'):
        print(f"  Total closed trades: {lifecycle_data['closed_trades']}")
    
    if lifecycle_data.get('timeout'):
        print(f"\n⚠ Note: Monitoring timed out. Trade may still be active.")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
