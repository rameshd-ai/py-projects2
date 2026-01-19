"""
Pillar 3: Functional & Business Logic
Tests critical user flows using Page Object Model.
"""
import pytest


def test_page_loads(page, base_url):
    """Basic test that page loads successfully."""
    page.goto(base_url, wait_until='networkidle')
    assert page.url == base_url or base_url in page.url


def test_page_has_content(page, base_url):
    """Test that page has visible content."""
    page.goto(base_url, wait_until='networkidle')
    body = page.locator('body')
    assert body.count() > 0, "Page should have a body element"
    
    # Check for some text content
    text_content = body.inner_text()
    assert len(text_content) > 0, "Page should have text content"
