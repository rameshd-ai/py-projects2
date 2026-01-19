"""
Pillar 5: Cross-Browser & Device Testing
Tests compatibility across different browsers.
"""
import pytest


@pytest.mark.parametrize('browser', ['chromium', 'firefox', 'webkit'], indirect=True)
def test_cross_browser_compatibility(browser, base_url):
    """Test that page works across different browsers."""
    page = browser.new_page()
    try:
        page.goto(base_url, wait_until='networkidle')
        assert page.title(), "Page should have a title in all browsers"
    finally:
        page.close()
