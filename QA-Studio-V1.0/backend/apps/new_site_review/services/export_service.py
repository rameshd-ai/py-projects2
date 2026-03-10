"""Export site data to Excel: GSC (clicks, impressions) + GA4 (sessions) + crawl (title, meta, h1, schema, inlinks)."""
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from apps.new_site_review.db.settings_store import get_ga4_settings
from apps.new_site_review.routers.auth import get_credentials

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_EXPORTS_DIR = _DATA_DIR / "exports"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    base = f"{parsed.scheme or 'https'}://{parsed.netloc or parsed.path}"
    return base.rstrip("/")


def _fetch_page_details(full_url: str) -> dict:
    """Fetch URL and return title, meta_description, h1, schema_count. Inlinks = 0 (placeholder)."""
    out = {
        "title": "",
        "title_length": 0,
        "meta_description": "",
        "meta_description_length": 0,
        "h1": "",
        "schema_count": 0,
        "inlinks": 0,
    }
    try:
        r = requests.get(full_url, timeout=15, headers={"User-Agent": _USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title_el = soup.find("title")
        out["title"] = (title_el.get_text(strip=True) if title_el else "")[:500]
        out["title_length"] = len(out["title"])
        meta = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if not meta and soup.find("meta", attrs={"name": "Description"}):
            meta = soup.find("meta", attrs={"name": "Description"})
        if meta and meta.get("content"):
            out["meta_description"] = (meta["content"] or "").strip()[:1000]
        out["meta_description_length"] = len(out["meta_description"])
        h1_el = soup.find("h1")
        out["h1"] = (h1_el.get_text(strip=True) if h1_el else "")[:500]
        out["schema_count"] = len(soup.find_all("script", type=re.compile(r"application/ld\+json", re.I)))
    except Exception:
        pass
    return out


def _gsc_rows(creds, site_url: str, row_limit: int = 1000) -> list[dict]:
    """Query Search Console for clicks, impressions per page. Returns list of { url_path (or page), clicks, impressions }."""
    try:
        service = build("webmasters", "v3", credentials=creds, cache_discovery=False)
        sites = service.sites().list().execute()
        site_entry = None
        for s in sites.get("siteEntry", []):
            if not s.get("siteUrl"):
                continue
            if site_url.rstrip("/") in s["siteUrl"] or s["siteUrl"].rstrip("/") in site_url:
                site_entry = s
                break
        if not site_entry:
            site_entry = sites.get("siteEntry", [{}])[0] if sites.get("siteEntry") else None
        if not site_entry:
            return []
        site_url_gsc = site_entry["siteUrl"]
        body = {
            "startDate": (datetime.utcnow() - timedelta(days=28)).strftime("%Y-%m-%d"),
            "endDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "dimensions": ["page"],
            "rowLimit": row_limit,
        }
        resp = service.searchanalytics().query(siteUrl=site_url_gsc, body=body).execute()
        rows = []
        for r in resp.get("rows", []):
            keys = r.get("keys", [])
            page_url = (keys[0] or "").strip() if keys else ""
            # GSC "page" dimension is full URL; store path for Excel
            parsed = urlparse(page_url)
            url_path = parsed.path or "/"
            rows.append({
                "url_path": url_path,
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
            })
        return rows
    except HttpError as e:
        raise RuntimeError(f"Search Console API error: {e}") from e
    except Exception as e:
        raise RuntimeError(f"GSC fetch failed: {e}") from e


def _ga4_sessions_simple(creds, property_id: str) -> dict[str, int]:
    """Fallback: use run_report via discovery."""
    try:
        service = build("analyticsdata", "v1beta", credentials=creds, cache_discovery=False)
        body = {
            "dimensions": [{"name": "pagePath"}],
            "metrics": [{"name": "sessions"}],
            "dateRanges": [{"startDate": "28daysAgo", "endDate": "today"}],
        }
        resp = service.properties().runReport(property=f"properties/{property_id}", body=body).execute()
        path_to_sessions = {}
        for r in resp.get("rows", []):
            dims = r.get("dimensionValues", [])
            vals = r.get("metricValues", [])
            path = (dims[0].get("value") or "").strip() if dims else ""
            sess = int(vals[0].get("value") or 0) if vals else 0
            path_to_sessions[path] = sess
        return path_to_sessions
    except Exception:
        return {}


def build_export(site_id: str, site_name: str, live_url: str) -> tuple[str, str]:
    """
    Build Excel export for site. Returns (filename, download_path).
    Raises if not logged in or API errors.
    """
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Not logged in. Sign in with Google first.")
    ga4 = get_ga4_settings()
    property_id = (ga4.ga4_property_id or "").strip() if ga4 else ""
    base_url = _normalize_domain(live_url)
    gsc_rows = _gsc_rows(creds, base_url)
    ga4_sessions = {}
    if property_id:
        ga4_sessions = _ga4_sessions_simple(creds, property_id)
    # Build rows: url_path, clicks, impressions, sessions, gks, title_length, meta_description, meta_description_length, h1, schema_count, inlinks
    rows = []
    for i, g in enumerate(gsc_rows):
        url_path = g.get("url_path") or ""
        full_url = urljoin(base_url + "/", url_path.lstrip("/")) if url_path else base_url
        details = _fetch_page_details(full_url)
        sessions = ga4_sessions.get(url_path) or ga4_sessions.get("/" + url_path.lstrip("/")) or 0
        rows.append({
            "url_path": url_path or "/",
            "clicks": g.get("clicks", 0),
            "impressions": g.get("impressions", 0),
            "sessions": sessions,
            "gks": "",  # placeholder
            "title_length": details["title_length"],
            "meta_description": details["meta_description"],
            "meta_description_length": details["meta_description_length"],
            "h1": details["h1"],
            "schema_count": details["schema_count"],
            "inlinks": details["inlinks"],
        })
    # If no GSC data, create one row from homepage
    if not rows:
        details = _fetch_page_details(base_url)
        rows = [{
            "url_path": "/",
            "clicks": 0,
            "impressions": 0,
            "sessions": 0,
            "gks": "",
            "title_length": details["title_length"],
            "meta_description": details["meta_description"],
            "meta_description_length": details["meta_description_length"],
            "h1": details["h1"],
            "schema_count": details["schema_count"],
            "inlinks": details["inlinks"],
        }]
    _EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w\-]", "_", site_name)[:50]
    filename = f"site_{site_id}_{safe_name}_{ts}.xlsx"
    path = _EXPORTS_DIR / filename
    wb = Workbook()
    ws = wb.active
    ws.title = "Site export"
    headers = [
        "url_path", "clicks", "impressions", "sessions", "gks",
        "title_length", "meta_description", "meta_description_length", "h1", "schema_count", "inlinks",
    ]
    ws.append(headers)
    for r in rows:
        ws.append([
            r.get("url_path", ""),
            r.get("clicks", 0),
            r.get("impressions", 0),
            r.get("sessions", 0),
            r.get("gks", ""),
            r.get("title_length", 0),
            r.get("meta_description", ""),
            r.get("meta_description_length", 0),
            r.get("h1", ""),
            r.get("schema_count", 0),
            r.get("inlinks", 0),
        ])
    wb.save(path)
    download_path = f"/new-site-review/downloads/{filename}"
    return filename, download_path
