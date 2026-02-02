"""
VComponent page helper - URL generation, HTML fetch, and screenshot.

For each VComponent, generates the preview URL, fetches the rendered HTML,
and saves a PNG screenshot using Playwright.

Usage:
    from helper_functions.vcomponent_page import (
        generate_vcomponent_url,
        fetch_vcomponent_html_and_screenshot,
    )

    url = generate_vcomponent_url("https://example.cms.com", vcomponent_id=21016536)
    html_path, png_path = fetch_vcomponent_html_and_screenshot(url, output_dir, extra_headers=headers)
"""

import logging
import random
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def generate_vcomponent_url(base_url: str, vcomponent_id: int) -> str:
    """
    Generate the VComponent preview URL with cache-busting param.

    Args:
        base_url: Site base URL (e.g., https://automation-testing.web4cms.milestoneinternet.info)
        vcomponent_id: VComponent ID from GetSiteVComponents response

    Returns:
        Full URL like: https://.../vcomponents?t=0.115515&vcomponentid=21016536
    """
    base_url = base_url.rstrip("/")
    t = random.random()
    params = {"t": t, "vcomponentid": vcomponent_id}
    url = f"{base_url}/vcomponents?{urlencode(params)}"
    return url


def fetch_vcomponent_html_and_screenshot(
    url: str,
    output_dir: Path,
    vcomponent_id: int,
    extra_headers: Optional[dict] = None,
    viewport_width: int = 1280,
    viewport_height: int = 800,
) -> Optional[tuple[str, str]]:
    """
    Open the VComponent URL, save the HTML and a PNG screenshot.

    Uses Playwright to render the page (handles JS-rendered content).

    Args:
        url: Full VComponent preview URL
        output_dir: Directory to save html and png (e.g., output/site/vcomponents/21016536)
        vcomponent_id: Used for filenames
        extra_headers: Optional headers (e.g., Authorization for auth)
        viewport_width: Browser viewport width
        viewport_height: Browser viewport height

    Returns:
        tuple of (html_path, png_path) or None if failed.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(
            "Playwright not installed. Run: poetry run pip install playwright && poetry run python -m playwright install chromium"
        ) from e

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{vcomponent_id}.html"
    png_path = output_dir / f"{vcomponent_id}.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context_kwargs = {
                "viewport": {"width": viewport_width, "height": viewport_height},
                "ignore_https_errors": True,
            }
            if extra_headers:
                context_kwargs["extra_http_headers"] = extra_headers
            context = browser.new_context(**context_kwargs)

            page = context.new_page()
            # Use "load" instead of "networkidle" - networkidle can hang on pages with polling/websockets
            page.goto(url, wait_until="load", timeout=60000)

            # Save HTML (rendered content)
            html_content = page.content()
            html_path.write_text(html_content, encoding="utf-8")
            logger.info(f"Saved HTML to {html_path}")

            # Screenshot
            page.screenshot(path=str(png_path), full_page=True)
            logger.info(f"Saved screenshot to {png_path}")

            context.close()
            browser.close()

        return (str(html_path), str(png_path))
    except Exception as e:
        logger.error(f"Failed to fetch VComponent page {url}: {e}", exc_info=True)
        raise  # Propagate so caller can show actual error


def fetch_vcomponent_with_page(page, url: str, output_dir, vcomponent_id: int) -> Optional[tuple[str, str]]:
    """
    Fetch one VComponent using an existing Playwright page. Use this when processing many
    components to avoid spawning a new browser per component (which can leave zombie processes).
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{vcomponent_id}.html"
    png_path = output_dir / f"{vcomponent_id}.png"
    try:
        # Use domcontentloaded - faster, avoids hanging on pages with slow/broken resources
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)  # Brief wait for images before screenshot
        html_content = page.content()
        html_path.write_text(html_content, encoding="utf-8")
        if not html_path.exists():
            raise OSError(f"HTML file was not created: {html_path}")
        page.screenshot(path=str(png_path), full_page=True, timeout=15000)
        if not png_path.exists():
            raise OSError(f"Screenshot file was not created: {png_path}")
        return (str(html_path), str(png_path))
    except Exception as e:
        logger.warning(f"VComponent {vcomponent_id} failed: {e}")
        raise
