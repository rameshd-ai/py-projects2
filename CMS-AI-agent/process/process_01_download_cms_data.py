"""
Process 01: Download CMS Data for Training

Downloads CMS data (pages, VComponents, etc.) for AI training.
For each site in login_token.json: fetches GetSiteVComponents and saves to output/{site_slug}/.
Also supports full download with site_id (pages, template pages, categories).

Usage:
    # CLI - fetch GetSiteVComponents for all sites from login_token.json
    python -m process.process_01_download_cms_data --all

    # CLI - full download for one site (requires site_id)
    python -m process.process_01_download_cms_data <site_url> <site_id> [profile_alias]

    # Programmatic
    from process.process_01_download_cms_data import fetch_vcomponents_for_all_sites
    results = fetch_vcomponents_for_all_sites()
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from helper_functions.login_token import login_and_get_headers
from helper_functions.vcomponent_page import (
    generate_vcomponent_url,
    fetch_vcomponent_html_and_screenshot,
    fetch_vcomponent_with_page,
)
from apis import (
    get_active_pages_from_api_all,
    GetAllVComponents,
    GetTemplatePageByName,
    GetPageCategoryList,
)

logger = logging.getLogger(__name__)

OUTPUT_FOLDER = os.environ.get("CMS_OUTPUT_FOLDER", "output")
TOKEN_FILENAME = "login_token.json"


def _sanitize_site_slug(site_url: str) -> str:
    """Create a safe filename from site URL."""
    slug = re.sub(r"^https?://", "", site_url)
    slug = re.sub(r"[^\w\-.]", "_", slug)
    return slug.strip("_")[:80] or "cms_data"


def _ensure_output_folder() -> str:
    """Create output folder if it doesn't exist."""
    base = Path(__file__).resolve().parent.parent
    folder = base / OUTPUT_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def _load_login_tokens(output_folder: Optional[str] = None) -> list:
    """Load site entries from login_token.json. If output_folder is set, look there; else output/."""
    base = Path(__file__).resolve().parent.parent
    if output_folder:
        token_path = Path(output_folder) / TOKEN_FILENAME
    else:
        token_path = base / OUTPUT_FOLDER / TOKEN_FILENAME
    if not token_path.exists():
        logger.warning(f"login_token.json not found at {token_path}")
        return []
    try:
        with open(token_path) as f:
            data = json.load(f)
        return data.get("sites", [])
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load login_token.json: {e}")
        return []


def _load_last_sites(output_folder: Optional[str] = None) -> list:
    """Load site URLs from last_sites.json (form selection). If output_folder is set, look there; else output/."""
    base = Path(__file__).resolve().parent.parent
    if output_folder:
        path = Path(output_folder) / "last_sites.json"
    else:
        path = base / OUTPUT_FOLDER / "last_sites.json"
    if not path.exists():
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("sites", [])
    except (json.JSONDecodeError, IOError):
        return []


def fetch_and_save_site_vcomponents(
    site_url: str,
    headers: dict,
    output_base: Optional[Path] = None,
) -> Optional[dict]:
    """
    Fetch GetSiteVComponents for one site and save to output/{site_slug}/GetSiteVComponents.json.
    """
    site_url = site_url.rstrip("/")
    slug = _sanitize_site_slug(site_url)
    base = Path(__file__).resolve().parent.parent
    folder = (output_base or base / OUTPUT_FOLDER) / slug
    folder.mkdir(parents=True, exist_ok=True)
    filepath = folder / "GetSiteVComponents.json"

    logger.info(f"Fetching VComponents for {site_url}...")

    vcomponents = GetAllVComponents(site_url, headers, page_size=1000)

    if isinstance(vcomponents, dict) and "error" in vcomponents:
        logger.error(f"  Failed: {vcomponents.get('error', 'unknown')}")
        return None

    count = len(vcomponents) if isinstance(vcomponents, list) else 0
    response_data = {
        "site_url": site_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "TotalRecords": count,
        "vComponents": vcomponents if isinstance(vcomponents, list) else [],
    }

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(response_data, f, indent=2, default=str)
        logger.info(f"  Saved {count} VComponents to {filepath}")
        return {"filepath": str(filepath), "count": count}
    except (IOError, TypeError) as e:
        logger.error(f"  Failed to save: {e}")
        return None


def fetch_vcomponents_for_all_sites(output_folder: Optional[str] = None) -> list:
    """
    For each site in login_token.json, fetch GetSiteVComponents and save to output/{site_slug}/.
    """
    sites = _load_login_tokens(output_folder)
    if not sites:
        logger.error("No sites found in login_token.json. Generate tokens first.")
        return []

    output_base = Path(output_folder) if output_folder else None
    results = []

    for entry in sites:
        site_url = entry.get("site_url")
        headers = entry.get("headers")
        if not site_url or not headers:
            logger.warning(f"Skipping entry without site_url or headers: {entry.get('site_url', '?')}")
            continue

        result = fetch_and_save_site_vcomponents(site_url, headers, output_base)
        if result:
            results.append({"site_url": site_url, **result})
        else:
            results.append({"site_url": site_url, "error": "Fetch or save failed"})

    return results


def _write_progress(progress_file: Optional[Path], data: dict) -> None:
    """Write progress to JSON file for UI polling. When status is 'done', also write summary."""
    if not progress_file:
        return
    try:
        with open(progress_file, "w") as f:
            json.dump(data, f, indent=0)
        if data.get("status") == "done":
            summary_path = progress_file.parent / "download_summary.json"
            summary = {
                "site_url": data.get("site_url", ""),
                "output_path": data.get("output_path", ""),
                "total": data.get("total", 0),
                "fetched": data.get("fetched", 0),
                "failed": data.get("failed", 0),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2)
    except (IOError, TypeError):
        pass


def fetch_vcomponent_pages_for_site(
    site_url: str,
    headers: dict,
    output_base: Optional[Path] = None,
    progress_file: Optional[Path] = None,
    retry_failed_only: bool = False,
    site_index: int = 1,
    site_total: int = 1,
) -> dict:
    """
    For each VComponent in GetSiteVComponents.json, fetch HTML and PNG screenshot.
    Saves to output/{site_slug}/vcomponents/{vcomponent_id}/{vcomponent_id}.html and .png

    If retry_failed_only=True, only fetches VComponents missing .html or .png.
    """
    site_url = site_url.rstrip("/")
    slug = _sanitize_site_slug(site_url)
    base = Path(__file__).resolve().parent.parent
    site_folder = (output_base or base / OUTPUT_FOLDER) / slug
    vcomponents_path = site_folder / "GetSiteVComponents.json"

    if not vcomponents_path.exists():
        logger.warning(f"GetSiteVComponents.json not found at {vcomponents_path}. Run --all first.")
        return {"site_url": site_url, "error": "GetSiteVComponents.json not found", "fetched": 0, "failed": 0}

    try:
        with open(vcomponents_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {"site_url": site_url, "error": str(e), "fetched": 0, "failed": 0}

    vcomponents = data.get("vComponents", [])
    vcomp_folder = site_folder / "vcomponents"
    if retry_failed_only:
        failed_only = []
        for vc in vcomponents:
            vcomponent_id = vc.get("vComponentId")
            if not vcomponent_id:
                continue
            vc_dir = vcomp_folder / str(vcomponent_id)
            html_path = vc_dir / f"{vcomponent_id}.html"
            png_path = vc_dir / f"{vcomponent_id}.png"
            if not html_path.exists() or not png_path.exists():
                failed_only.append(vc)
        vcomponents = failed_only
        if not vcomponents:
            logger.info(f"No failed VComponents to retry for {site_url}")
            _write_progress(progress_file, {"status": "done", "site_url": site_url, "site_index": site_index, "site_total": site_total, "current": 0, "total": 0, "fetched": 0, "failed": 0, "retry": "none_failed"})
            return {"site_url": site_url, "fetched": 0, "failed": 0, "total": 0, "retry": "none_failed"}

    vcomp_folder.mkdir(parents=True, exist_ok=True)
    extra_headers = headers if headers else None

    fetched = 0
    failed = 0
    first_error = None
    total = len(vcomponents)
    vcomp_folder = Path(vcomp_folder).resolve()
    vcomp_folder.mkdir(parents=True, exist_ok=True)
    # Write sentinel file so user can verify we're writing to the correct folder
    sentinel = vcomp_folder / "._download_folder.txt"
    sentinel.write_text(f"Download target: {vcomp_folder}\nStarted: {datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")
    logger.info(f"Fetching VComponent pages for {site_url} ({total} components) -> {vcomp_folder}")

    _write_progress(progress_file, {"status": "running", "site_url": site_url, "site_index": site_index, "site_total": site_total, "output_path": str(vcomp_folder), "current": 0, "total": total, "fetched": 0, "failed": 0})

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        return {"site_url": site_url, "error": str(e), "fetched": 0, "failed": total}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context_kwargs = {"viewport": {"width": 1280, "height": 800}, "ignore_https_errors": True}
            if extra_headers:
                context_kwargs["extra_http_headers"] = extra_headers
            context = browser.new_context(**context_kwargs)
            page = context.new_page()

            for i, vc in enumerate(vcomponents):
                vcomponent_id = vc.get("vComponentId")
                if not vcomponent_id:
                    _write_progress(progress_file, {"status": "running", "site_url": site_url, "site_index": site_index, "site_total": site_total, "output_path": str(vcomp_folder), "current": i + 1, "total": total, "fetched": fetched, "failed": failed})
                    continue
                url = generate_vcomponent_url(site_url, vcomponent_id)
                vc_dir = vcomp_folder / str(vcomponent_id)
                try:
                    result = fetch_vcomponent_with_page(page, url, vc_dir, vcomponent_id)
                    if result:
                        fetched += 1
                        vc["_download"] = {
                            "html": str(vc_dir / f"{vcomponent_id}.html"),
                            "png": str(vc_dir / f"{vcomponent_id}.png"),
                            "downloaded_at": datetime.now(timezone.utc).isoformat(),
                        }
                    else:
                        failed += 1
                        vc["_download"] = {"downloaded": False}
                except Exception as e:
                    failed += 1
                    vc["_download"] = {"downloaded": False, "error": str(e)}
                    if first_error is None:
                        first_error = str(e)
                    logger.warning(f"VComponent {vcomponent_id} failed: {e}")
                    _write_progress(progress_file, {"status": "running", "site_url": site_url, "site_index": site_index, "site_total": site_total, "output_path": str(vcomp_folder), "current": i + 1, "total": total, "fetched": fetched, "failed": failed})
                    continue
                _write_progress(progress_file, {"status": "running", "site_url": site_url, "site_index": site_index, "site_total": site_total, "output_path": str(vcomp_folder), "current": i + 1, "total": total, "fetched": fetched, "failed": failed})
                if (i + 1) % 10 == 0:
                    logger.info(f"  Progress: {i + 1}/{len(vcomponents)} ({fetched} ok, {failed} failed)")
        finally:
            context.close()
            browser.close()

    # Update GetSiteVComponents.json with download tracking
    data["download_stats"] = {
        "fetched": fetched,
        "failed": failed,
        "total": total,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(vcomponents_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Updated GetSiteVComponents.json with download tracking")
    except (IOError, TypeError) as e:
        logger.warning(f"Could not update GetSiteVComponents.json: {e}")

    result_dict = {"site_url": site_url, "fetched": fetched, "failed": failed, "total": len(vcomponents)}
    if first_error:
        result_dict["first_error"] = first_error
    _write_progress(progress_file, {"status": "done", "site_url": site_url, "site_index": site_index, "site_total": site_total, "output_path": str(vcomp_folder), "current": total, "total": total, "fetched": fetched, "failed": failed, "first_error": first_error})
    return result_dict


def fetch_vcomponent_pages_for_all_sites(
    output_folder: Optional[str] = None,
    progress_file: Optional[Path] = None,
    retry_failed_only: bool = False,
) -> list:
    """
    For each site in login_token.json, fetch HTML and PNG for each VComponent.
    If retry_failed_only=True, only fetches VComponents missing .html or .png.
    """
    all_tokens = _load_login_tokens(output_folder)
    if not all_tokens:
        logger.error("No sites found in login_token.json. Generate tokens first.")
        return []

    # Use last_sites (form) to filter - only process sites user selected. Fall back to all tokens.
    last_sites = _load_last_sites(output_folder)
    want_urls = {s.get("cms_url", "").rstrip("/") for s in last_sites if s.get("cms_url")}
    if want_urls:
        sites = [t for t in all_tokens if (t.get("site_url") or "").rstrip("/") in want_urls]
    else:
        sites = all_tokens

    # Deduplicate by site_url (same site in list = process once)
    seen = set()
    unique_sites = []
    for entry in sites:
        url = (entry.get("site_url") or "").rstrip("/")
        if url and url not in seen:
            seen.add(url)
            unique_sites.append(entry)

    output_base = Path(output_folder) if output_folder else None
    results = []
    site_total = len(unique_sites)

    for idx, entry in enumerate(unique_sites):
        site_url = entry.get("site_url")
        headers = entry.get("headers")
        if not site_url:
            continue
        result = fetch_vcomponent_pages_for_site(site_url, headers or {}, output_base, progress_file, retry_failed_only, site_index=idx + 1, site_total=site_total)
        results.append(result)

    return results


def download_cms_data_for_training(
    site_url: str,
    site_id: str,
    profile_alias: str = "default",
    output_folder: Optional[str] = None,
    include_page_details: bool = False,
) -> Optional[dict]:
    """
    Download CMS data for training and save to output folder.

    Fetches: active pages, VComponents, template pages, page categories.

    Args:
        site_url: CMS base URL (e.g., https://example.cms.milestoneinternet.info)
        site_id: Site ID for the target site
        profile_alias: Profile alias for token generation (default: "default")
        output_folder: Override output folder
        include_page_details: If True, fetch full page info for each page (slower)

    Returns:
        dict: Result with filepath, stats, etc. Or None if failed.
    """
    site_url = site_url.rstrip("/")
    folder = output_folder or _ensure_output_folder()
    slug = _sanitize_site_slug(site_url)

    logger.info(f"Downloading CMS data for training: {site_url} (site_id: {site_id})")

    # 1. Get auth headers
    headers = login_and_get_headers(site_url, profile_alias)
    if not headers:
        logger.error("[FAIL] Could not obtain auth token.")
        return None

    training_data = {
        "site_url": site_url,
        "site_id": site_id,
        "profile_alias": profile_alias,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "pages": [],
        "vcomponents": [],
        "template_pages": [],
        "page_categories": [],
    }

    # 2. Fetch active pages
    logger.info("Fetching active pages...")
    pages = get_active_pages_from_api_all(site_url, site_id, headers)
    training_data["pages"] = pages
    logger.info(f"  Fetched {len(pages)} active pages")

    # 3. Fetch all VComponents
    logger.info("Fetching VComponents...")
    vcomponents = GetAllVComponents(site_url, headers, page_size=1000)
    if isinstance(vcomponents, dict) and "error" in vcomponents:
        logger.warning(f"  VComponents fetch failed: {vcomponents.get('error', 'unknown')}")
    else:
        training_data["vcomponents"] = vcomponents if isinstance(vcomponents, list) else []
        logger.info(f"  Fetched {len(training_data['vcomponents'])} VComponents")

    # 4. Fetch template pages
    logger.info("Fetching template pages...")
    for search_term in ["Base Layout Page", "Layout", "Base"]:
        template_result = GetTemplatePageByName(site_url, headers, search_term)
        if isinstance(template_result, list) and template_result:
            training_data["template_pages"] = template_result[:50]
            logger.info(f"  Fetched {len(training_data['template_pages'])} template page(s)")
            break
    else:
        logger.info("  Template pages: none found")

    # 5. Fetch page categories
    logger.info("Fetching page categories...")
    categories = GetPageCategoryList(site_url, headers)
    if isinstance(categories, dict) and "error" in categories:
        logger.warning(f"  Page categories fetch failed: {categories.get('error', 'unknown')}")
    else:
        training_data["page_categories"] = categories if isinstance(categories, list) else []
        logger.info(f"  Fetched {len(training_data['page_categories'])} page categories")

    # 6. Optionally fetch page details (can be slow for many pages)
    if include_page_details and pages:
        logger.info("Fetching page details (this may take a while)...")
        from apis import get_page_info

        page_details = []
        for i, page in enumerate(pages[:50]):  # Limit to 50 to avoid timeout
            page_id = page.get("PageId")
            if page_id:
                detail = get_page_info(site_url, str(page_id), headers)
                if detail:
                    page_details.append(detail)
        training_data["page_details"] = page_details
        logger.info(f"  Fetched {len(page_details)} page details")

    # 7. Save to output folder
    filename = f"cms_training_data_{slug}.json"
    filepath = os.path.join(folder, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(training_data, f, indent=2, default=str)
        logger.info(f"[SUCCESS] CMS training data saved to {filepath}")
    except (IOError, TypeError) as e:
        logger.error(f"[FAIL] Could not save training data: {e}")
        return None

    return {
        "filepath": filepath,
        "filename": filename,
        "stats": {
            "pages": len(training_data["pages"]),
            "vcomponents": len(training_data["vcomponents"]),
            "template_pages": len(training_data["template_pages"]),
            "page_categories": len(training_data["page_categories"]),
        },
    }


def main() -> None:
    """CLI entry point. Dispatches to fetch_vcomponents_for_all_sites or download_cms_data_for_training."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if len(sys.argv) >= 2 and sys.argv[1] == "--all":
        # Fetch GetSiteVComponents for all sites from login_token.json
        results = fetch_vcomponents_for_all_sites()
        if not results:
            print("[FAIL] No sites processed. Ensure login_token.json exists with tokens.")
            sys.exit(1)
        success = sum(1 for r in results if "count" in r)
        print(f"\n[OK] Processed {success}/{len(results)} site(s)")
        for r in results:
            if "count" in r:
                print(f"  - {r['site_url']}: {r['count']} VComponents -> {r['filepath']}")
            else:
                print(f"  - {r['site_url']}: FAILED")

        # If --pages, also fetch HTML and PNG for each VComponent
        if len(sys.argv) >= 3 and sys.argv[2] == "--pages":
            print("\nFetching VComponent pages (HTML + screenshot)...")
            page_results = fetch_vcomponent_pages_for_all_sites()
            for r in page_results:
                if "error" in r:
                    print(f"  - {r['site_url']}: {r['error']}")
                else:
                    print(f"  - {r['site_url']}: {r['fetched']}/{r['total']} pages (failed: {r['failed']})")
    elif len(sys.argv) >= 2 and sys.argv[1] == "--pages":
        # Fetch HTML + PNG for each VComponent (requires GetSiteVComponents.json)
        # Optional: --progress-file <path> for UI progress polling
        # Optional: --output-dir <path> for explicit output folder (avoids path resolution issues)
        # Optional: --retry-failed to only fetch VComponents missing .html or .png
        progress_file = None
        if "--progress-file" in sys.argv:
            idx = sys.argv.index("--progress-file")
            if idx + 1 < len(sys.argv):
                progress_file = Path(sys.argv[idx + 1])
        output_folder = None
        if "--output-dir" in sys.argv:
            idx = sys.argv.index("--output-dir")
            if idx + 1 < len(sys.argv):
                output_folder = str(Path(sys.argv[idx + 1]).resolve())
        retry_failed = "--retry-failed" in sys.argv
        msg = "Retrying failed VComponent pages..." if retry_failed else "Fetching VComponent pages (HTML + screenshot)..."
        print(msg)
        page_results = fetch_vcomponent_pages_for_all_sites(output_folder=output_folder, progress_file=progress_file, retry_failed_only=retry_failed)
        if not page_results:
            print("[FAIL] No sites processed. Ensure login_token.json and GetSiteVComponents.json exist.")
            sys.exit(1)
        for r in page_results:
            if "error" in r:
                print(f"  - {r['site_url']}: {r['error']}")
            else:
                print(f"  - {r['site_url']}: {r['fetched']}/{r['total']} pages (failed: {r['failed']})")
    elif len(sys.argv) >= 3:
        # Full download for one site (requires site_id)
        site_url = sys.argv[1]
        site_id = sys.argv[2]
        profile_alias = sys.argv[3] if len(sys.argv) > 3 else "default"

        print(f"Downloading CMS data for training: {site_url} (site_id: {site_id})")
        result = download_cms_data_for_training(
            site_url=site_url,
            site_id=site_id,
            profile_alias=profile_alias,
        )

        if result:
            print(f"[OK] Training data saved to: {result['filepath']}")
            print(f"     Pages: {result['stats']['pages']}, VComponents: {result['stats']['vcomponents']}")
        else:
            print("[FAIL] Download failed.")
            sys.exit(1)
    else:
        print("Usage:")
        print("  python -m process.process_01_download_cms_data --all")
        print("      Fetch GetSiteVComponents for all sites in login_token.json")
        print("  python -m process.process_01_download_cms_data --all --pages")
        print("      Fetch GetSiteVComponents + HTML and PNG for each VComponent")
        print("  python -m process.process_01_download_cms_data --pages [--retry-failed] [--progress-file PATH]")
        print("      Fetch HTML and PNG for each VComponent (--retry-failed = only missing ones)")
        print("  python -m process.process_01_download_cms_data <site_url> <site_id> [profile_alias]")
        print("      Full download (pages, VComponents, templates, categories) for one site")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
