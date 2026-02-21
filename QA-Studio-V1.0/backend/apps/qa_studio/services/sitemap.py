"""Fetch and parse sitemap.xml to get all URLs."""
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Set

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
MAX_DEPTH = 5
MAX_URLS = 500
TIMEOUT = 15


def _base_url(url: str) -> str:
    """Get base URL (origin) for sitemap lookup."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return base.rstrip("/")


def _sitemap_url(base: str) -> str:
    """Construct sitemap.xml URL from base URL."""
    return f"{base}/sitemap.xml"


def _fetch_xml(url: str) -> str:
    """Fetch URL and return response body as string."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


def _local_name(tag: str) -> str:
    """Get local name from possibly namespaced tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_sitemap_xml(xml_str: str, base_url: str) -> tuple[List[str], List[str]]:
    """
    Parse sitemap XML. Returns (urls, child_sitemap_urls).
    Handles both regular sitemap (url/loc) and sitemap index (sitemap/loc).
    """
    urls: List[str] = []
    child_sitemaps: List[str] = []
    root = ET.fromstring(xml_str)
    for parent in root.iter():
        pl = _local_name(parent.tag).lower()
        for loc in parent:
            if _local_name(loc.tag) != "loc":
                continue
            t = (loc.text or "").strip()
            if not t or not t.startswith("http"):
                continue
            if pl == "sitemap":
                child_sitemaps.append(t)
            else:
                urls.append(t)
    return (urls, child_sitemaps)


def fetch_sitemap_urls(base_url: str) -> tuple[List[str], str]:
    """
    Fetch sitemap from base_url/sitemap.xml and extract all URLs.
    Handles sitemap index (follows child sitemaps recursively).
    Returns (list of unique URLs, error_message). Error is empty on success.
    """
    base = _base_url(base_url)
    sitemap_url = _sitemap_url(base)
    seen_urls: Set[str] = set()
    seen_sitemaps: Set[str] = set()
    to_fetch: List[tuple[str, int]] = [(sitemap_url, 0)]
    last_error = ""

    while to_fetch and len(seen_urls) < MAX_URLS:
        url, depth = to_fetch.pop(0)
        if depth > MAX_DEPTH:
            continue
        if url in seen_sitemaps:
            continue
        seen_sitemaps.add(url)
        try:
            xml_str = _fetch_xml(url)
        except Exception as e:
            last_error = str(e)
            if depth == 0:
                return ([], f"Could not fetch sitemap: {e}")
            continue
        try:
            page_urls, child_sitemaps = _parse_sitemap_xml(xml_str, base)
        except ET.ParseError as e:
            last_error = str(e)
            if depth == 0:
                return ([], f"Invalid sitemap XML: {e}")
            continue
        for u in page_urls:
            seen_urls.add(u)
        for child in reversed(child_sitemaps):
            if child not in seen_sitemaps and len(seen_urls) + len(to_fetch) < MAX_URLS:
                to_fetch.insert(0, (child, depth + 1))

    if not seen_urls:
        msg = last_error if last_error else "No URLs found in sitemap. Check that sitemap.xml exists and contains valid URLs."
        return ([], msg)

    return (sorted(seen_urls), "")
