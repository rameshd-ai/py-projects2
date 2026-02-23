"""Accessibility scan using Playwright + axe-core."""
import time
import urllib.request
from dataclasses import dataclass, field
from typing import List

from playwright.sync_api import sync_playwright

AXE_CORE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.3/axe.min.js"


def _fetch_axe_script() -> str:
    """Fetch axe-core script so we can inject as inline (avoids CSP blocking external script)."""
    req = urllib.request.Request(AXE_CORE_CDN, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")


TAB_FOCUS_CUSTOM_SCRIPT = """
() => {
  const selector = 'h1, h2, h3, h4, h5, h6, p, img';
  const els = document.querySelectorAll(selector);
  const notFocusable = [];
  const focusableSelectors = 'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])';

  function isVisible(el) {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function isFocusable(el) {
    if (el.tabIndex >= 0) return true;
    if (el.matches && el.matches(focusableSelectors)) return true;
    if (el.hasAttribute && el.hasAttribute('tabindex') && el.getAttribute('tabindex') !== '-1') return true;
    return false;
  }

  function getSelector(el) {
    if (el.id) return '#' + el.id;
    const parts = [];
    let e = el;
    while (e && e.nodeType === 1) {
      let sel = e.tagName.toLowerCase();
      if (e.id) { parts.unshift(sel + '#' + e.id); break; }
      if (e.className && typeof e.className === 'string') {
        const c = e.className.trim().split(/\\s+/).filter(Boolean)[0];
        if (c) sel += '.' + c;
      }
      parts.unshift(sel);
      if (parts.length >= 3) break;
      e = e.parentElement;
    }
    return parts.join(' > ');
  }

  els.forEach(function(el) {
    if (!isVisible(el)) return;
    if (el.tagName === 'IMG') {
      if (!el.alt || el.alt.trim() === '') return;
    }
    if (!isFocusable(el)) {
      notFocusable.push({
        html: el.outerHTML.substring(0, 500),
        target: [getSelector(el)]
      });
    }
  });

  return notFocusable;
}
"""


@dataclass
class AccessibilityReport:
    """Structured accessibility scan report."""

    url: str
    success: bool
    error: str = ""
    violations: List[dict] = field(default_factory=list)
    passes: List[dict] = field(default_factory=list)
    incomplete: List[dict] = field(default_factory=list)
    inapplicable: List[dict] = field(default_factory=list)
    custom_tests: List[dict] = field(default_factory=list)
    timestamp: str = ""
    axe_version: str = ""


def run_accessibility_scan(url: str, timeout_ms: int = 60000) -> AccessibilityReport:
    """
    Run axe-core accessibility scan on the given URL using Playwright.
    Returns a detailed report with violations, passes, and incomplete results.
    """
    import datetime

    report = AccessibilityReport(
        url=url,
        success=False,
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    ignore_https_errors=True,
                    bypass_csp=True,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
                page = context.new_page()
                page.goto(url, wait_until="load", timeout=timeout_ms)
                # Allow JavaScript-rendered content to appear before scanning
                time.sleep(3)
                axe_script = _fetch_axe_script()
                page.add_script_tag(content=axe_script)
                result = page.evaluate(
                    """() => {
                    return new Promise((resolve, reject) => {
                        if (typeof axe === 'undefined') {
                            reject(new Error('axe-core not loaded'));
                            return;
                        }
                        axe.run(document, { resultTypes: ['violations', 'passes', 'incomplete', 'inapplicable'] })
                            .then(resolve)
                            .catch(reject);
                    });
                }"""
                )
                report.success = True
                report.violations = result.get("violations", [])
                report.passes = result.get("passes", [])
                report.incomplete = result.get("incomplete", [])
                report.inapplicable = result.get("inapplicable", [])
                if result.get("testEngine"):
                    report.axe_version = result["testEngine"].get("version", "")

                nodes_not_focusable = page.evaluate(TAB_FOCUS_CUSTOM_SCRIPT)
                if nodes_not_focusable:
                    report.custom_tests.append({
                        "id": "tab-focus-visible-text",
                        "impact": "moderate",
                        "description": "Tab focus should reach all visible text elements (headings, paragraphs) and images with alt text for keyboard navigation.",
                        "help": "Add tabindex='0' to these elements so keyboard users can tab to them, or ensure content is within focusable containers.",
                        "helpUrl": "https://www.w3.org/WAI/WCAG21/Understanding/keyboard.html",
                        "nodes": nodes_not_focusable,
                        "summary": f"{len(nodes_not_focusable)} visible text/image element(s) are not reachable via Tab.",
                    })
                page.close()
                context.close()
            finally:
                browser.close()
    except Exception as e:
        report.error = str(e)
        report.success = False

    return report


def report_to_dict(report: AccessibilityReport) -> dict:
    """Convert report to JSON-serializable dict."""
    custom_violations = report.custom_tests
    total_violations = report.violations + custom_violations
    return {
        "url": report.url,
        "success": report.success,
        "error": report.error,
        "violations": total_violations,
        "passes": report.passes,
        "incomplete": report.incomplete,
        "inapplicable": report.inapplicable,
        "custom_tests": report.custom_tests,
        "timestamp": report.timestamp,
        "axe_version": report.axe_version,
        "summary": {
            "violations_count": len(total_violations),
            "passes_count": len(report.passes),
            "incomplete_count": len(report.incomplete),
            "inapplicable_count": len(report.inapplicable),
        },
    }
