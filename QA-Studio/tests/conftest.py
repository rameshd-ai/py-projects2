"""
Pytest configuration and fixtures for QA Studio tests.
"""
import pytest
import os
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


def pytest_generate_tests(metafunc):
    """Dynamically parametrize tests based on command-line options."""
    if 'device' in metafunc.fixturenames:
        devices_str = metafunc.config.getoption('--devices')
        devices_list = [d.strip() for d in devices_str.split(',')]
        metafunc.parametrize('device', devices_list, indirect=True)


def pytest_addoption(parser):
    """Add custom pytest command-line options."""
    # Use try-except to handle cases where options might already be registered
    # This can happen if conftest is loaded multiple times
    def safe_addoption(*args, **kwargs):
        try:
            parser.addoption(*args, **kwargs)
        except ValueError as e:
            # Option already exists, ignore
            if 'already added' not in str(e):
                raise
    
    safe_addoption(
        '--run-id',
        action='store',
        default=None,
        help='Test run ID for this execution'
    )
    safe_addoption(
        '--base-url',
        action='store',
        default='https://example.com',
        help='Base URL to test'
    )
    safe_addoption(
        '--sitemap-url',
        action='store',
        default=None,
        help='Sitemap URL'
    )
    safe_addoption(
        '--browsers',
        action='store',
        default='chromium',
        help='Comma-separated list of browsers (chromium, firefox, webkit)'
    )
    safe_addoption(
        '--devices',
        action='store',
        default='desktop',
        help='Comma-separated list of devices (desktop, tablet, mobile)'
    )
    safe_addoption(
        '--pillars',
        action='store',
        default='1,2,3,4,5,6',
        help='Comma-separated list of pillar numbers to test'
    )


@pytest.fixture(scope='session')
def run_id(request):
    """Get the test run ID from command line."""
    return request.config.getoption('--run-id') or 'test_run'


@pytest.fixture(scope='session')
def base_url(request):
    """Get the base URL from command line."""
    return request.config.getoption('--base-url')


@pytest.fixture(scope='session')
def sitemap_url(request, base_url):
    """Get the sitemap URL from command line or default."""
    url = request.config.getoption('--sitemap-url')
    if url:
        return url
    return f"{base_url.rstrip('/')}/sitemap.xml"


@pytest.fixture(scope='session')
def browsers(request):
    """Get list of browsers from command line."""
    browsers_str = request.config.getoption('--browsers')
    return [b.strip() for b in browsers_str.split(',')]


@pytest.fixture(scope='session')
def devices(request):
    """Get list of devices from command line."""
    devices_str = request.config.getoption('--devices')
    return [d.strip() for d in devices_str.split(',')]


@pytest.fixture(scope='function', params=None)
def device(request, devices):
    """Get device name from command line devices list."""
    # Get all devices from command line
    # Pytest will automatically parametrize this fixture based on the devices list
    if hasattr(request, 'param') and request.param:
        return request.param
    
    # If not parametrized, return the first device
    return devices[0] if devices else 'desktop'


@pytest.fixture(scope='session')
def pillars(request):
    """Get list of pillars from command line."""
    pillars_str = request.config.getoption('--pillars')
    return [int(p.strip()) for p in pillars_str.split(',')]


@pytest.fixture(scope='session')
def playwright():
    """Playwright instance for the test session."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope='function')
def browser(playwright, browsers, request):
    """Create a browser instance based on the browser parameter."""
    # Use the first browser from command line (or param if provided)
    if hasattr(request, 'param') and request.param:
        browser_name = request.param
    else:
        # Get from command line --browsers option
        browser_name = browsers[0] if browsers else 'chromium'
    
    print(f"[BROWSER] Using browser: {browser_name}")
    
    # Launch browser with visible window and slow motion for debugging
    launch_options = {
        'headless': False,
        'slow_mo': 500,  # 500ms delay between actions to make it more visible
        'channel': None  # Use default channel
    }
    
    if browser_name == 'chromium':
        browser = playwright.chromium.launch(**launch_options)
    elif browser_name == 'firefox':
        browser = playwright.firefox.launch(**launch_options)
    elif browser_name == 'webkit':
        browser = playwright.webkit.launch(**launch_options)
    else:
        raise ValueError(f"Unknown browser: {browser_name}")
    
    print(f"[BROWSER] Launched {browser_name} browser (visible window should open)")
    
    yield browser
    browser.close()
    print(f"[BROWSER] Closed {browser_name} browser")


@pytest.fixture(scope='function')
def page(browser, device, request):
    """Create a page with device emulation."""
    # Get device name from device fixture (which handles parametrization)
    device_name = device if device else 'desktop'
    
    print(f"[PAGE] Creating page with device: {device_name}")
    
    # Device viewport configurations
    device_configs = {
        'desktop': {'width': 1920, 'height': 1080},
        'tablet': {'width': 768, 'height': 1024},
        'mobile': {'width': 375, 'height': 667}
    }
    
    config = device_configs.get(device_name, device_configs['desktop'])
    print(f"[PAGE] Setting viewport: {config['width']}x{config['height']}")
    print(f"[PAGE] Setting viewport: {config['width']}x{config['height']}")
    
    # Create context with user agent to avoid bot blocking
    context = browser.new_context(
        viewport=config,
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    page = context.new_page()
    
    # Set extra HTTP headers to appear more like a real browser
    page.set_extra_http_headers({
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    })
    
    yield page
    
    context.close()


@pytest.fixture(scope='session')
def reports_dir(run_id):
    """Get the reports directory for this run."""
    reports_path = os.path.join('static', 'reports', run_id)
    os.makedirs(reports_path, exist_ok=True)
    os.makedirs(os.path.join(reports_path, 'screenshots'), exist_ok=True)
    os.makedirs(os.path.join(reports_path, 'logs'), exist_ok=True)
    return reports_path
