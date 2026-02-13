"""
Playwright test for paper trading interface
Tests the UI workflow from button click to trade execution
"""
import asyncio
import sys
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, expect
import json

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:5000"
TARGET_URL = f"{BASE_URL}/dashboard/paper-trade"

def print_header(text):
    print("\n" + "="*80)
    print(f" {text}")
    print("="*80)

def print_step(step_num, text):
    print(f"\n[STEP {step_num}] {text}")
    print("-" * 80)

def get_timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

class PlaywrightPaperTradeTest:
    def __init__(self):
        self.browser: Browser = None
        self.page: Page = None
        self.screenshots = []
        self.console_logs = []
        self.console_errors = []
        
    async def setup(self, headless=False):
        """Setup browser and page"""
        print_step(0, "Setting up browser")
        self.playwright = await async_playwright().start()
        
        print(f"  Launching browser (headless={headless})...")
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=['--start-maximized']
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        
        self.page = await self.context.new_page()
        
        # Capture console logs
        self.page.on("console", lambda msg: self.console_logs.append({
            'time': get_timestamp(),
            'type': msg.type,
            'text': msg.text
        }))
        
        # Capture console errors
        self.page.on("pageerror", lambda err: self.console_errors.append({
            'time': get_timestamp(),
            'error': str(err)
        }))
        
        print(f"  ✓ [{get_timestamp()}] Browser launched successfully")
        
    async def teardown(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def take_screenshot(self, name: str):
        """Take and save screenshot"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"screenshot_{timestamp}_{name}.png"
        path = f"d:/GItHIbProjects/py-projects2/IND-Quant-Alpha/kite_quant/{filename}"
        
        await self.page.screenshot(path=path, full_page=True)
        self.screenshots.append({'name': name, 'path': path, 'time': get_timestamp()})
        print(f"  📸 Screenshot saved: {filename}")
        return path
        
    async def wait_and_log(self, seconds: int, message: str):
        """Wait with countdown logging"""
        print(f"  ⏳ {message}")
        for i in range(seconds, 0, -1):
            print(f"     {i}s...", end='\r')
            await asyncio.sleep(1)
        print(f"     Done!   ")
        
    async def navigate_to_page(self):
        """Step 1: Navigate to paper trade page"""
        print_step(1, f"Navigating to {TARGET_URL}")
        
        try:
            await self.page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            print(f"  ✓ [{get_timestamp()}] Page loaded successfully")
            
            # Wait for key elements
            await self.page.wait_for_selector("#investment-amount", timeout=5000)
            await self.page.wait_for_selector("#paper-trade-btn", timeout=5000)
            
            print(f"  ✓ [{get_timestamp()}] Key elements found")
            
            await self.take_screenshot("01_page_loaded")
            return True
            
        except Exception as e:
            print(f"  ✗ [{get_timestamp()}] Failed to load page: {e}")
            await self.take_screenshot("01_page_load_error")
            return False
            
    async def check_investment_amount(self):
        """Step 2: Check investment amount"""
        print_step(2, "Checking investment amount")
        
        try:
            # Get the investment amount input value
            investment_input = await self.page.locator("#investment-amount")
            current_value = await investment_input.input_value()
            
            print(f"  Current investment amount: ₹{current_value}")
            
            # Set to 10000 if not already
            if current_value != "10000":
                print(f"  Setting investment amount to ₹10000...")
                await investment_input.fill("10000")
                await asyncio.sleep(0.5)
                
                # Verify the change
                new_value = await investment_input.input_value()
                print(f"  ✓ [{get_timestamp()}] Investment amount set to: ₹{new_value}")
            else:
                print(f"  ✓ [{get_timestamp()}] Investment amount already set to ₹10000")
                
            await self.take_screenshot("02_investment_amount_checked")
            return True
            
        except Exception as e:
            print(f"  ✗ [{get_timestamp()}] Failed to check investment amount: {e}")
            return False
            
    async def click_trade_button(self):
        """Step 3: Click the TRADE button"""
        print_step(3, "Clicking TRADE button")
        
        try:
            trade_button = self.page.locator("#paper-trade-btn")
            
            # Check if button is visible and enabled
            is_visible = await trade_button.is_visible()
            is_enabled = await trade_button.is_enabled()
            
            print(f"  Trade button visible: {is_visible}")
            print(f"  Trade button enabled: {is_enabled}")
            
            if not is_visible or not is_enabled:
                print(f"  ✗ [{get_timestamp()}] Trade button not ready")
                await self.take_screenshot("03_button_not_ready")
                return False
                
            # Click the button
            print(f"  Clicking TRADE button...")
            await trade_button.click()
            print(f"  ✓ [{get_timestamp()}] Trade button clicked")
            
            # Wait a bit for the API call to complete
            await asyncio.sleep(2)
            
            # Check status message
            status_el = self.page.locator("#paper-trade-status")
            status_text = await status_el.inner_text()
            print(f"  Status after click: {status_text}")
            
            await self.take_screenshot("03_after_trade_click")
            return True
            
        except Exception as e:
            print(f"  ✗ [{get_timestamp()}] Failed to click trade button: {e}")
            await self.take_screenshot("03_click_error")
            return False
            
    async def monitor_waiting_to_enter(self, timeout_seconds=60):
        """Step 4: Monitor for 'Waiting to enter' row"""
        print_step(4, f"Monitoring for 'Waiting to enter' row (timeout: {timeout_seconds}s)")
        
        start_time = asyncio.get_event_loop().time()
        waiting_detected = False
        
        try:
            while asyncio.get_event_loop().time() - start_time < timeout_seconds:
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                
                # Check the paper trades table
                tbody = self.page.locator("#paper-executions-tbody")
                rows = await tbody.locator("tr").count()
                
                if rows > 0:
                    # Check for "Waiting to enter" badge
                    waiting_badges = await tbody.locator(".badge.bg-info:has-text('Waiting to enter')").count()
                    
                    if waiting_badges > 0 and not waiting_detected:
                        print(f"  ✓ [{get_timestamp()}] 'Waiting to enter' row detected! (elapsed: {elapsed}s)")
                        waiting_detected = True
                        await self.take_screenshot("04_waiting_to_enter_detected")
                        
                        # Get row details
                        first_row = tbody.locator("tr").first
                        row_html = await first_row.inner_html()
                        print(f"  Row details:")
                        
                        # Extract cells
                        cells = await first_row.locator("td").all_inner_texts()
                        if len(cells) >= 5:
                            print(f"    - Option Type: {cells[1]}")
                            print(f"    - Strike: {cells[2]}")
                            print(f"    - Strategy: {cells[3]}")
                            print(f"    - Entry Price: {cells[6]}")
                        
                        return True
                    
                    if waiting_detected:
                        print(f"  [{get_timestamp()}] Still showing 'Waiting to enter' (elapsed: {elapsed}s)")
                
                # Wait before next check
                await asyncio.sleep(2)
                
            if not waiting_detected:
                print(f"  ✗ [{get_timestamp()}] 'Waiting to enter' row did not appear within {timeout_seconds}s")
                await self.take_screenshot("04_waiting_timeout")
                return False
                
        except Exception as e:
            print(f"  ✗ [{get_timestamp()}] Error monitoring for 'Waiting to enter': {e}")
            await self.take_screenshot("04_monitoring_error")
            return False
            
    async def monitor_trade_open(self, timeout_seconds=180):
        """Step 5: Monitor for trade to become OPEN"""
        print_step(5, f"Monitoring for trade to become OPEN (timeout: {timeout_seconds}s)")
        
        start_time = asyncio.get_event_loop().time()
        open_detected = False
        
        try:
            while asyncio.get_event_loop().time() - start_time < timeout_seconds:
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                
                tbody = self.page.locator("#paper-executions-tbody")
                
                # Check for OPEN badge
                open_badges = await tbody.locator(".badge.bg-warning:has-text('OPEN')").count()
                
                if open_badges > 0 and not open_detected:
                    print(f"  ✓ [{get_timestamp()}] Trade OPEN detected! (elapsed: {elapsed}s)")
                    open_detected = True
                    await self.take_screenshot("05_trade_open_detected")
                    
                    # Get trade details
                    first_row = tbody.locator("tr").first
                    cells = await first_row.locator("td").all_inner_texts()
                    
                    if len(cells) >= 17:
                        print(f"  Trade details:")
                        print(f"    - Option Type: {cells[1]}")
                        print(f"    - Strike: {cells[2]}")
                        print(f"    - Strategy: {cells[3]}")
                        print(f"    - Entry Time: {cells[4]}")
                        print(f"    - Entry Price: {cells[6]}")
                        print(f"    - Current Price: {cells[8]}")
                        print(f"    - Quantity: {cells[9]}")
                        print(f"    - Capital Used: {cells[11]}")
                        print(f"    - Gross P&L: {cells[13]}")
                        print(f"    - Net P&L: {cells[15]}")
                        print(f"    - Status: {cells[16]}")
                    
                    return True
                
                if not open_detected and elapsed % 10 == 0:
                    print(f"  [{get_timestamp()}] Still waiting for trade to open... (elapsed: {elapsed}s)")
                
                await asyncio.sleep(2)
                
            if not open_detected:
                print(f"  ✗ [{get_timestamp()}] Trade did not become OPEN within {timeout_seconds}s")
                await self.take_screenshot("05_open_timeout")
                return False
                
        except Exception as e:
            print(f"  ✗ [{get_timestamp()}] Error monitoring for OPEN status: {e}")
            await self.take_screenshot("05_monitoring_error")
            return False
            
    async def monitor_price_updates(self, duration_seconds=180):
        """Step 6: Monitor real-time price and P&L updates"""
        print_step(6, f"Monitoring real-time price updates for {duration_seconds}s")
        
        start_time = asyncio.get_event_loop().time()
        price_updates = []
        row_stable = True
        
        try:
            while asyncio.get_event_loop().time() - start_time < duration_seconds:
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                
                tbody = self.page.locator("#paper-executions-tbody")
                rows = await tbody.locator("tr").count()
                
                if rows == 0:
                    print(f"  ⚠ [{get_timestamp()}] Row disappeared! (elapsed: {elapsed}s)")
                    row_stable = False
                    await self.take_screenshot(f"06_row_disappeared_{elapsed}s")
                    break
                
                # Get current price and P&L
                first_row = tbody.locator("tr").first
                cells = await first_row.locator("td").all_inner_texts()
                
                if len(cells) >= 16:
                    current_price = cells[8]  # Current price column
                    gross_pnl = cells[13]     # Gross P&L column
                    net_pnl = cells[15]       # Net P&L column
                    
                    price_updates.append({
                        'time': get_timestamp(),
                        'elapsed': elapsed,
                        'current_price': current_price,
                        'gross_pnl': gross_pnl,
                        'net_pnl': net_pnl
                    })
                    
                    # Log every 30 seconds
                    if elapsed % 30 == 0 or elapsed == 0:
                        print(f"  [{get_timestamp()}] Update at {elapsed}s:")
                        print(f"    - Current Price: {current_price}")
                        print(f"    - Gross P&L: {gross_pnl}")
                        print(f"    - Net P&L: {net_pnl}")
                        
                        await self.take_screenshot(f"06_price_update_{elapsed}s")
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            # Analyze price updates
            print(f"\n  Analysis of {len(price_updates)} price updates:")
            
            if len(price_updates) >= 2:
                # Check if prices changed
                first_price = price_updates[0]['current_price']
                last_price = price_updates[-1]['current_price']
                
                unique_prices = len(set([u['current_price'] for u in price_updates]))
                unique_pnls = len(set([u['net_pnl'] for u in price_updates]))
                
                print(f"    - First price: {first_price}")
                print(f"    - Last price: {last_price}")
                print(f"    - Unique prices: {unique_prices}")
                print(f"    - Unique P&Ls: {unique_pnls}")
                
                prices_updated = unique_prices > 1
                pnl_updated = unique_pnls > 1
                
                print(f"    - Price updated: {'✓ Yes' if prices_updated else '✗ No (static)'}")
                print(f"    - P&L updated: {'✓ Yes' if pnl_updated else '✗ No (static)'}")
                
                return {
                    'row_stable': row_stable,
                    'prices_updated': prices_updated,
                    'pnl_updated': pnl_updated,
                    'update_count': len(price_updates)
                }
            else:
                print(f"    ⚠ Not enough updates captured")
                return {
                    'row_stable': row_stable,
                    'prices_updated': False,
                    'pnl_updated': False,
                    'update_count': len(price_updates)
                }
                
        except Exception as e:
            print(f"  ✗ [{get_timestamp()}] Error monitoring price updates: {e}")
            await self.take_screenshot("06_monitoring_error")
            return {
                'row_stable': False,
                'prices_updated': False,
                'pnl_updated': False,
                'update_count': 0,
                'error': str(e)
            }
            
    async def get_console_errors(self):
        """Get any console errors"""
        print_step(7, "Checking for console errors")
        
        if self.console_errors:
            print(f"  ✗ Found {len(self.console_errors)} console errors:")
            for i, err in enumerate(self.console_errors, 1):
                print(f"    {i}. [{err['time']}] {err['error']}")
            return self.console_errors
        else:
            print(f"  ✓ [{get_timestamp()}] No console errors detected")
            return []
            
    async def run_test(self):
        """Run the complete test workflow"""
        print_header("PLAYWRIGHT PAPER TRADING TEST")
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Target URL: {TARGET_URL}")
        
        results = {
            'page_loaded': False,
            'investment_amount_correct': False,
            'trade_button_clicked': False,
            'waiting_to_enter_appeared': False,
            'trade_became_open': False,
            'price_monitoring': {},
            'console_errors': [],
            'screenshots': []
        }
        
        try:
            # Setup browser
            await self.setup(headless=False)
            
            # Step 1: Navigate
            results['page_loaded'] = await self.navigate_to_page()
            if not results['page_loaded']:
                return results
                
            # Step 2: Check investment amount
            results['investment_amount_correct'] = await self.check_investment_amount()
            
            # Step 3: Click trade button
            results['trade_button_clicked'] = await self.click_trade_button()
            if not results['trade_button_clicked']:
                return results
                
            # Step 4: Monitor for "Waiting to enter"
            results['waiting_to_enter_appeared'] = await self.monitor_waiting_to_enter(timeout_seconds=60)
            
            # Step 5: Monitor for "OPEN" status
            results['trade_became_open'] = await self.monitor_trade_open(timeout_seconds=180)
            
            if results['trade_became_open']:
                # Step 6: Monitor price updates
                results['price_monitoring'] = await self.monitor_price_updates(duration_seconds=180)
            
            # Step 7: Check console errors
            results['console_errors'] = await self.get_console_errors()
            
            # Take final screenshot
            await self.take_screenshot("99_final_state")
            
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            results['screenshots'] = self.screenshots
            
        return results


async def main():
    test = PlaywrightPaperTradeTest()
    
    try:
        results = await test.run_test()
        
        # Print final report
        print_header("TEST RESULTS SUMMARY")
        print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("\n📊 Test Results:")
        print(f"  {'✓' if results['page_loaded'] else '✗'} Page loaded: {results['page_loaded']}")
        print(f"  {'✓' if results['investment_amount_correct'] else '✗'} Investment amount checked: {results['investment_amount_correct']}")
        print(f"  {'✓' if results['trade_button_clicked'] else '✗'} TRADE button clicked: {results['trade_button_clicked']}")
        print(f"  {'✓' if results['waiting_to_enter_appeared'] else '✗'} 'Waiting to enter' appeared: {results['waiting_to_enter_appeared']}")
        print(f"  {'✓' if results['trade_became_open'] else '✗'} Trade became OPEN: {results['trade_became_open']}")
        
        if results['price_monitoring']:
            pm = results['price_monitoring']
            print(f"\n📈 Price Monitoring:")
            print(f"  {'✓' if pm.get('row_stable', False) else '✗'} Row remained stable: {pm.get('row_stable', False)}")
            print(f"  {'✓' if pm.get('prices_updated', False) else '✗'} Real-time price updates: {pm.get('prices_updated', False)}")
            print(f"  {'✓' if pm.get('pnl_updated', False) else '✗'} Real-time P&L updates: {pm.get('pnl_updated', False)}")
            print(f"  Total updates captured: {pm.get('update_count', 0)}")
            
        if results['console_errors']:
            print(f"\n⚠ Console Errors: {len(results['console_errors'])} errors detected")
        else:
            print(f"\n✓ Console Errors: None")
            
        if results['screenshots']:
            print(f"\n📸 Screenshots captured: {len(results['screenshots'])}")
            for sc in results['screenshots']:
                print(f"  - {sc['name']} @ {sc['time']}")
                
        print("\n" + "="*80)
        
        # Keep browser open for user to inspect
        print("\n⏸ Browser will remain open for inspection.")
        print("Press Ctrl+C to close and exit...")
        
        try:
            # Keep the script running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\nClosing browser...")
            
    finally:
        await test.teardown()
        print("✓ Test cleanup complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
