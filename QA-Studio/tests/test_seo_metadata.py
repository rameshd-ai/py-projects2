"""
Pillar 6: Content, SEO & Schema Validation
Tests SEO elements and Schema.org JSON-LD.
"""
import pytest
from bs4 import BeautifulSoup
import json


def test_seo_meta_tags(page, base_url):
    """Test that page has essential SEO meta tags."""
    page.goto(base_url, wait_until='networkidle')
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    
    # Check for title
    title = soup.find('title')
    assert title and title.text, "Page should have a title tag"
    
    # Check for meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        desc_content = meta_desc.get('content', '')
        assert len(desc_content) >= 120, "Meta description should be at least 120 characters"
        assert len(desc_content) <= 160, "Meta description should be at most 160 characters"


def test_h1_count(page, base_url):
    """Test that page has appropriate H1 count (should be 1)."""
    page.goto(base_url, wait_until='networkidle')
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    
    h1_tags = soup.find_all('h1')
    assert len(h1_tags) == 1, f"Page should have exactly 1 H1 tag, found {len(h1_tags)}"


def test_schema_org_jsonld(page, base_url):
    """Test that page has valid Schema.org JSON-LD if present."""
    page.goto(base_url, wait_until='networkidle')
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find all JSON-LD scripts
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)
            # Basic validation - should be a dict or list
            assert isinstance(data, (dict, list)), "JSON-LD should be valid JSON"
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON-LD found: {script.string}")
