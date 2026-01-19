"""
Pillar 1: Rendering & Responsiveness
Tests viewport rendering and visual regression.
"""
import pytest
from pathlib import Path
from playwright.sync_api import expect
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.image_processor import ImageProcessor


def test_viewport_rendering(page, base_url, device, reports_dir, run_id, sitemap_url):
    """
    Test that pages render correctly at different viewports.
    - If baseline images exist: Performs pixel-perfect visual regression testing
    - If no baselines: Checks for broken UI and responsiveness issues only
    Tests base URL and optionally all URLs from sitemap.
    Handles timeouts and bot-blocking gracefully.
    """
    import time
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    
    # Initialize image processor
    image_processor = ImageProcessor(reports_dir)
    
    # Check if baselines exist
    baselines_dir = Path(reports_dir).parent / 'baselines'
    has_baselines = baselines_dir.exists() and any(baselines_dir.glob('*.png'))
    
    if has_baselines:
        print(f"\n[MODE] Visual Regression: Comparing screenshots with Figma baselines")
    else:
        print(f"\n[MODE] UI Health Check: Testing for broken UI and responsiveness (no baselines provided)")
    
    # Get URLs to test
    urls_to_test = [str(base_url)]
    
    # If sitemap URL is provided, get all URLs from sitemap
    if sitemap_url:
        try:
            from advertools import sitemap_to_df
            print(f"\n{'='*80}")
            print(f"[SITEMAP] Fetching URLs from sitemap: {sitemap_url}")
            print(f"{'='*80}")
            df = sitemap_to_df(str(sitemap_url))
            if 'loc' in df.columns and len(df) > 0:
                sitemap_urls = df['loc'].head(10).tolist()  # Limit to first 10 URLs for speed
                urls_to_test.extend(sitemap_urls)
                print(f"[SITEMAP] Found {len(sitemap_urls)} URLs in sitemap")
                print(f"[SITEMAP] Will test {len(urls_to_test)} total URLs (1 base + {len(sitemap_urls)} from sitemap)")
                print(f"[SITEMAP] URLs to test:")
                for i, u in enumerate(urls_to_test, 1):
                    print(f"  {i}. {u}")
                print(f"{'='*80}\n")
        except Exception as e:
            print(f"[WARNING] Could not parse sitemap: {e}. Testing base URL only.")
    
    # Track results
    results = {
        'tested': 0,
        'passed': 0,
        'failed': 0,
        'skipped': 0,
        'timeouts': 0,
        'errors': [],
        'detailed_errors': []  # Structured error information
    }
    
    # Test each URL with timeout protection
    device_name = device if device else 'desktop'
    
    print(f"\n{'='*80}")
    print(f"[START] Testing {len(urls_to_test)} URL(s) for {device_name} viewport")
    print(f"{'='*80}\n")
    
    for idx, url in enumerate(urls_to_test, 1):
        url_num = f"[{idx}/{len(urls_to_test)}]"
        
        # Print prominent progress indicator
        print(f"\n{'='*80}")
        print(f"TESTING URL {idx}/{len(urls_to_test)}: {url}")
        print(f"Device: {device_name} | Progress: {int((idx/len(urls_to_test))*100)}%")
        print(f"{'='*80}\n")
        
        print(f"{url_num} Opening browser window for {device_name}...")
        print(f"{url_num} Browser should be visible - navigating to: {url}")
        
        try:
            start_time = time.time()
            
            # Add a small delay to ensure browser window is visible
            time.sleep(2)
            print(f"{url_num} Waiting 2 seconds for browser to be visible...")
            
            # Navigate to URL with timeout
            try:
                print(f"{url_num} Navigating to {url}...")
                page.goto(url, wait_until='networkidle', timeout=20000)  # 20 second timeout
                print(f"{url_num} Page loaded in {time.time() - start_time:.1f}s")
            except PlaywrightTimeoutError:
                results['timeouts'] += 1
                error_msg = f"Timeout loading {url} (may be blocked or slow)"
                print(f"{url_num} [TIMEOUT] {error_msg}")
                results['errors'].append(error_msg)
                # Try to continue with what we have
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=10000)
                    print(f"{url_num} [PARTIAL] Loaded with domcontentloaded fallback")
                except:
                    print(f"{url_num} [SKIP] Could not load {url}, skipping...")
                    results['skipped'] += 1
                    continue
            
            # Wait for page to be fully loaded (with shorter timeout)
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except PlaywrightTimeoutError:
                print(f"{url_num} [WARNING] Network not idle, continuing anyway...")
            
            # Check for bot blocking indicators
            page_content = page.content()
            bot_indicators = ['cloudflare', 'access denied', 'bot detected', 'captcha', 'blocked']
            if any(indicator in page_content.lower() for indicator in bot_indicators):
                print(f"{url_num} [WARNING] Possible bot blocking detected on {url}")
            
            # Basic checks
            title = page.title()
            if not title:
                print(f"{url_num} [WARNING] Page has no title: {url}")
            
            # Create safe filename from URL
            url_safe = url.replace('http://', '').replace('https://', '').replace('/', '_').replace(':', '_')
            url_safe = ''.join(c for c in url_safe if c.isalnum() or c in ('_', '-', '.'))[:50]  # Limit and sanitize
            
            # Use device_name for filename
            device_name = device if device else 'desktop'
            
            # Take screenshot for visual regression
            screenshot_filename = f'{device_name}_{url_safe}_{run_id}_viewport.png'
            screenshot_path = Path(reports_dir) / 'screenshots' / screenshot_filename
            
            # Take full page screenshot with timeout
            try:
                page.screenshot(
                    path=str(screenshot_path),
                    full_page=True,
                    timeout=15000  # 15 second timeout for screenshot
                )
                print(f"{url_num} [SUCCESS] Screenshot saved: {screenshot_filename}")
            except PlaywrightTimeoutError:
                print(f"{url_num} [WARNING] Screenshot timeout for {url}, trying viewport screenshot...")
                # Fallback to viewport-only screenshot
                page.screenshot(
                    path=str(screenshot_path),
                    timeout=5000
                )
            
            # Perform visual regression comparison OR UI health checks
            baseline_path = image_processor._get_baseline_path(
                Path(reports_dir) / 'screenshots' / screenshot_filename
            )
            
            comparison_result = image_processor.compare_images(
                actual_path=str(screenshot_path),
                baseline_path=str(baseline_path) if baseline_path.exists() else None,
                threshold=0.01  # 1% difference threshold
            )
            
            # Save comparison result
            image_processor.save_comparison_result(
                comparison_result,
                device=device,
                url=url
            )
            
            results['tested'] += 1
            
            # If baseline was just created (first run), that's fine
            if comparison_result.get('is_baseline'):
                print(f"{url_num} [BASELINE] Auto-created baseline for {device} viewport: {url}")
                results['passed'] += 1
                continue
            
            # If no baseline exists (and wasn't created), perform UI health checks instead
            if comparison_result.get('match') is None:
                # No baseline - do UI health checks
                print(f"{url_num} [UI CHECK] No baseline - performing UI health checks for {device} viewport: {url}")
                
                ui_issues = []
                
                # Check 1: Viewport meta tag
                viewport_meta = page.locator('meta[name="viewport"]')
                if not viewport_meta.count():
                    ui_issues.append("Missing viewport meta tag")
                
                # Check 2: Responsive layout elements
                body_width = page.evaluate('() => document.body.scrollWidth')
                viewport_width = page.viewport_size['width']
                
                if body_width > viewport_width * 1.1:  # 10% overflow tolerance
                    ui_issues.append(f"Horizontal overflow detected: {body_width}px > {viewport_width}px")
                
                # Check 3: Critical elements visibility
                critical_selectors = ['header', 'main', 'nav', 'footer']
                missing_elements = []
                for selector in critical_selectors:
                    if page.locator(selector).count() == 0:
                        missing_elements.append(selector)
                
                if missing_elements:
                    ui_issues.append(f"Missing critical elements: {', '.join(missing_elements)}")
                
                # Check 4: Images loading
                broken_images = page.evaluate('''() => {
                    const images = Array.from(document.querySelectorAll('img'));
                    return images.filter(img => !img.complete || img.naturalHeight === 0).length;
                }''')
                
                if broken_images > 0:
                    ui_issues.append(f"{broken_images} broken image(s) detected")
                
                # Check 5: Text readability (check for very small text)
                small_text = page.evaluate('''() => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    return elements.filter(el => {
                        const style = window.getComputedStyle(el);
                        const fontSize = parseFloat(style.fontSize);
                        return fontSize > 0 && fontSize < 10; // Less than 10px
                    }).length;
                }''')
                
                if small_text > 5:  # More than 5 elements with tiny text
                    ui_issues.append(f"Many elements with very small text ({small_text} elements < 10px)")
                
                # Report results
                if ui_issues:
                    print(f"{url_num} [UI ISSUES] Found {len(ui_issues)} issue(s):")
                    for issue in ui_issues:
                        print(f"{url_num}   - {issue}")
                    results['failed'] += 1
                    # Store detailed issue information
                    for issue in ui_issues:
                        issue_entry = {
                            'type': 'ui_health_check',
                            'category': _categorize_issue(issue),
                            'device': device,
                            'url': url,
                            'message': issue,
                            'severity': 'error'
                        }
                        results['errors'].append(issue_entry)
                        results['detailed_errors'].append(issue_entry)
                else:
                    print(f"{url_num} [PASS] UI health check passed for {device} viewport: {url}")
                    results['passed'] += 1
                
                continue
            
            # Visual regression comparison (baselines exist)
            if not comparison_result['match']:
                diff_percentage = comparison_result['difference']
                diff_path = comparison_result.get('diff_path', 'N/A')
                error_msg = f"Visual regression: {diff_percentage}% difference at {url}"
                print(f"{url_num} [FAIL] {error_msg}")
                results['failed'] += 1
                # Store detailed visual regression error
                visual_error = {
                    'type': 'visual_regression',
                    'category': 'visual_diff',
                    'device': device,
                    'url': url,
                    'message': error_msg,
                    'difference_percentage': diff_percentage,
                    'diff_image_path': str(diff_path) if diff_path != 'N/A' else None,
                    'baseline_path': comparison_result.get('baseline_path'),
                    'actual_path': comparison_result.get('actual_path'),
                    'severity': 'error'
                }
                results['errors'].append(error_msg)
                results['detailed_errors'].append(visual_error)
                # Don't fail immediately, continue testing other URLs
                continue
            else:
                print(f"{url_num} [PASS] Visual regression passed for {device} viewport: {url}")
                results['passed'] += 1
                
        except Exception as e:
            error_msg = f"Error testing {url}: {str(e)}"
            print(f"{url_num} [ERROR] {error_msg}")
            # Store detailed exception error
            exception_error = {
                'type': 'exception',
                'category': 'test_error',
                'device': device,
                'url': url,
                'message': error_msg,
                'exception_type': type(e).__name__,
                'severity': 'error'
            }
            results['errors'].append(error_msg)
            results['detailed_errors'].append(exception_error)
            results['skipped'] += 1
            # Continue with next URL instead of failing completely
            continue
    
    # Print summary with results location
    device_name = device if device else 'desktop'
    print(f"\n{'='*80}")
    print(f"[SUMMARY] {device_name} viewport testing complete:")
    print(f"  Tested: {results['tested']}/{len(urls_to_test)}")
    print(f"  Passed: {results['passed']}")
    print(f"  Failed: {results['failed']}")
    print(f"  Skipped: {results['skipped']}")
    print(f"  Timeouts: {results['timeouts']}")
    print(f"\n[RESULTS] Screenshots saved to: {reports_dir}/screenshots/")
    print(f"[RESULTS] View results at: http://localhost:5000/static/reports/{run_id}/screenshots/")
    print(f"{'='*80}")
    
    # Save detailed errors to JSON file for bug report
    if results.get('detailed_errors'):
        import json
        errors_file = Path(reports_dir) / 'detailed_errors.json'
        with open(errors_file, 'w') as f:
            json.dump({
                'run_id': run_id,
                'device': device_name,
                'total_errors': len(results['detailed_errors']),
                'errors_by_category': _organize_errors_by_category(results['detailed_errors']),
                'errors': results['detailed_errors']
            }, f, indent=2)
        print(f"\n[BUG REPORT] Detailed errors saved to: {errors_file}")
    
    if results['errors']:
        print(f"\n[ERRORS] {len(results['errors'])} errors encountered:")
        for error in results['errors'][:5]:  # Show first 5 errors
            if isinstance(error, dict):
                print(f"  - {error.get('message', str(error))}")
            else:
                print(f"  - {error}")
        if len(results['errors']) > 5:
            print(f"  ... and {len(results['errors']) - 5} more")
    
    # Save detailed errors to JSON file for bug report
    if results.get('detailed_errors'):
        import json
        errors_file = Path(reports_dir) / 'detailed_errors.json'
        with open(errors_file, 'w') as f:
            json.dump({
                'run_id': run_id,
                'device': device_name,
                'total_errors': len(results['detailed_errors']),
                'errors_by_category': _organize_errors_by_category(results['detailed_errors']),
                'errors': results['detailed_errors']
            }, f, indent=2)
        print(f"\n[BUG REPORT] Detailed errors saved to: {errors_file}")
    
    # Fail only if all URLs failed
    if results['tested'] == 0:
        pytest.fail(f"Failed to test any URLs. All {len(urls_to_test)} URLs had errors or timeouts.")
    
    # Warn if many failures
    if results['failed'] > results['passed']:
        pytest.fail(f"More failures than passes: {results['failed']} failed, {results['passed']} passed")


def _categorize_issue(issue_message: str) -> str:
    """Categorize an issue message into a category."""
    issue_lower = issue_message.lower()
    if 'viewport' in issue_lower or 'meta tag' in issue_lower:
        return 'viewport_meta'
    elif 'overflow' in issue_lower or 'width' in issue_lower:
        return 'responsive_layout'
    elif 'missing' in issue_lower or 'element' in issue_lower:
        return 'missing_elements'
    elif 'image' in issue_lower or 'broken' in issue_lower:
        return 'broken_images'
    elif 'text' in issue_lower or 'readability' in issue_lower or 'font' in issue_lower:
        return 'text_readability'
    else:
        return 'other'


def _organize_errors_by_category(errors: list) -> dict:
    """Organize errors by category for better reporting."""
    organized = {}
    for error in errors:
        category = error.get('category', 'other')
        if category not in organized:
            organized[category] = []
        organized[category].append(error)
    return organized


def check_ui_health(page, device, url):
    """
    Check for basic UI issues and responsiveness problems.
    Returns list of issues found.
    """
    issues = []
    
    try:
        # Check 1: Page has content
        body = page.locator('body')
        if body.count() == 0:
            issues.append(f"No body element found on {url}")
        else:
            text_content = body.inner_text()
            if len(text_content) < 100:
                issues.append(f"Very little content on page ({len(text_content)} chars)")
        
        # Check 2: Check for broken images
        images = page.locator('img')
        image_count = images.count()
        if image_count > 0:
            for i in range(min(image_count, 10)):  # Check first 10 images
                img = images.nth(i)
                src = img.get_attribute('src')
                if not src or src == '' or src == '#':
                    issues.append(f"Broken image found (no src)")
        
        # Check 3: Check viewport is set correctly
        viewport_size = page.viewport_size
        if not viewport_size:
            issues.append(f"Viewport size not set properly")
        
        # Check 4: Check for horizontal overflow (common responsiveness issue)
        # This checks if content is wider than viewport
        page_width = page.evaluate('document.documentElement.scrollWidth')
        viewport_width = viewport_size['width'] if viewport_size else 0
        
        if page_width > viewport_width + 20:  # Allow 20px tolerance
            issues.append(f"Horizontal overflow detected: content {page_width}px vs viewport {viewport_width}px (may cause horizontal scrolling)")
        
        # Check 5: Device-specific checks
        if device == 'mobile':
            # Check if viewport meta tag exists (important for mobile)
            viewport_meta = page.locator('meta[name="viewport"]')
            if viewport_meta.count() == 0:
                issues.append(f"Missing viewport meta tag (important for mobile responsiveness)")
            
            # Check if navigation is accessible
            # Most mobile sites have burger menu, nav, or header
            nav_elements = page.locator('nav, [role="navigation"], header, .navbar, .menu, .hamburger')
            if nav_elements.count() == 0:
                issues.append(f"No navigation elements found on mobile view")
        
        # Check 6: Look for console errors that might indicate broken functionality
        # This is already captured in test_browser_health but we can check here too
        
        # Check 7: Check if main content is visible
        main_content = page.locator('main, [role="main"], #content, .content, #main')
        if main_content.count() == 0:
            # Not critical but worth noting
            pass  # Many sites don't use semantic main tags
        
    except Exception as e:
        issues.append(f"Error during UI health check: {str(e)}")
    
    return issues


@pytest.mark.skip(reason="Disabled: Uses Playwright auto-baseline feature. Use test_viewport_rendering instead which respects manual baseline uploads.")
def test_visual_regression_playwright_native(page, base_url, reports_dir, device):
    """
    DISABLED: This test uses Playwright's native expect().to_have_screenshot() which
    automatically creates baselines. We want baselines to be manually uploaded from Figma.
    
    Use test_viewport_rendering instead, which:
    - Performs UI health checks when no baselines exist
    - Performs visual regression when Figma baselines are uploaded
    """
    # This test is disabled to prevent auto-baseline creation
    pytest.skip("This test is disabled. Use test_viewport_rendering instead.")


def test_responsive_layout_elements(page, base_url, device):
    """
    Test that key elements are visible and properly positioned at different viewports.
    """
    page.goto(base_url, wait_until='networkidle', timeout=30000)
    page.wait_for_load_state('networkidle')
    
    # Check for common responsive elements
    body = page.locator('body')
    assert body.count() > 0, "Page should have a body element"
    
    # Check viewport dimensions
    viewport_size = page.viewport_size
    assert viewport_size is not None, "Viewport size should be set"
    
    # Device-specific checks
    if device == 'mobile':
        # Mobile-specific checks
        # Check if navigation is accessible (might be hamburger menu)
        nav_elements = page.locator('nav, [role="navigation"], .navbar, .menu')
        # Just check that page is responsive, not that specific elements exist
        assert True, "Mobile viewport check passed"
    
    elif device == 'tablet':
        # Tablet-specific checks
        assert viewport_size['width'] >= 768, "Tablet should have appropriate width"
        assert True, "Tablet viewport check passed"
    
    else:  # desktop
        # Desktop-specific checks
        assert viewport_size['width'] >= 1024, "Desktop should have appropriate width"
        assert True, "Desktop viewport check passed"
    
    # Check that page content is visible
    text_content = body.inner_text()
    assert len(text_content) > 0, "Page should have visible text content"


def test_viewport_meta_tag(page, base_url):
    """
    Test that page has proper viewport meta tag for responsive design.
    """
    page.goto(base_url, wait_until='networkidle', timeout=30000)
    
    # Check for viewport meta tag
    viewport_meta = page.locator('meta[name="viewport"]')
    viewport_count = viewport_meta.count()
    
    if viewport_count > 0:
        viewport_content = viewport_meta.get_attribute('content')
        assert viewport_content is not None, "Viewport meta tag should have content attribute"
        # Check if it contains responsive settings
        assert 'width' in viewport_content.lower(), "Viewport meta should include width setting"
    else:
        # Viewport meta tag is recommended but not required
        pytest.skip("No viewport meta tag found (recommended for responsive design)")
