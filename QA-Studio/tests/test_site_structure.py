"""
Pillar 2: Site Architecture & Navigation
Tests sitemap validation and link integrity.
"""
import pytest
import requests
from advertools import sitemap_to_df


def test_sitemap_exists(sitemap_url):
    """Test that sitemap is accessible."""
    response = requests.get(sitemap_url, timeout=10)
    assert response.status_code == 200, f"Sitemap should be accessible at {sitemap_url}"


def test_sitemap_parsing(sitemap_url):
    """Test that sitemap can be parsed."""
    try:
        df = sitemap_to_df(sitemap_url)
        assert len(df) > 0, "Sitemap should contain at least one URL"
    except Exception as e:
        pytest.fail(f"Failed to parse sitemap: {e}")


def test_sitemap_urls_accessible(sitemap_url, base_url):
    """Test that URLs in sitemap return 200 status."""
    try:
        df = sitemap_to_df(sitemap_url)
        # Limit to first 10 URLs for speed
        test_urls = df['loc'].head(10).tolist()
        
        failed_urls = []
        for url in test_urls:
            try:
                response = requests.get(url, timeout=5, allow_redirects=True)
                if response.status_code != 200:
                    failed_urls.append(f"{url} returned {response.status_code}")
            except Exception as e:
                failed_urls.append(f"{url} failed: {e}")
        
        if failed_urls:
            pytest.fail(f"Some URLs failed:\n" + "\n".join(failed_urls))
    except Exception as e:
        pytest.skip(f"Sitemap test skipped: {e}")
