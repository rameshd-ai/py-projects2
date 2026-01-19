"""
Pillar 4: Console & Technical Checks
Tests for JavaScript errors and network failures.
"""
import pytest


def test_no_console_errors(page, base_url):
    """Test that page has no console errors."""
    console_errors = []
    
    def handle_console(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)
    
    page.on('console', handle_console)
    page.goto(base_url, wait_until='networkidle')
    
    if console_errors:
        pytest.fail(f"Console errors found: {console_errors}")


def test_no_failed_requests(page, base_url):
    """Test that no network requests failed."""
    failed_requests = []
    
    def handle_request_failed(request):
        failed_requests.append({
            'url': request.url,
            'failure': request.failure
        })
    
    page.on('requestfailed', handle_request_failed)
    page.goto(base_url, wait_until='networkidle')
    
    if failed_requests:
        # Filter out expected failures (e.g., favicon.ico)
        critical_failures = [
            f for f in failed_requests 
            if not any(ignore in f['url'].lower() for ignore in ['favicon', 'analytics', 'tracking'])
        ]
        if critical_failures:
            pytest.fail(f"Failed requests: {critical_failures}")
