"""Responsiveness scan using Playwright: multi-device viewports, overflow detection, screenshots."""
import base64
import datetime
import time
from dataclasses import dataclass, field
from typing import List

from playwright.sync_api import sync_playwright

# Viewport presets: (width, height, label)
DEVICES = [
    (375, 667, "Mobile"),
    (768, 1024, "Tablet"),
    (1920, 1080, "Desktop"),
]

RESPONSIVE_CHECKS_SCRIPT = """
() => {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const body = document.body;
  const html = document.documentElement;
  const scrollWidth = Math.max(body.scrollWidth, html.scrollWidth, body.offsetWidth, html.offsetWidth);
  const scrollHeight = Math.max(body.scrollHeight, html.scrollHeight);
  
  const issues = [];
  
  // 1. Horizontal overflow
  if (scrollWidth > vw) {
    const overflowElements = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
    let node;
    while (node = walker.nextNode()) {
      const rect = node.getBoundingClientRect();
      if (rect.right > vw || rect.left < 0 && rect.width > vw) {
        const style = window.getComputedStyle(node);
        const overflowX = style.overflowX;
        if (node.scrollWidth > node.clientWidth || node.offsetWidth > vw) {
          let sel = '';
          if (node.id) sel = '#' + node.id;
          else if (node.className && typeof node.className === 'string') {
            const c = (node.className.trim().split(/\\s+/)[0] || '').replace(/^[\\.#]/, '');
            if (c) sel = (node.tagName || 'div').toLowerCase() + '.' + c;
          }
          if (!sel) sel = (node.tagName || 'div').toLowerCase();
          overflowElements.push({
            selector: sel,
            tag: node.tagName,
            rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
            scrollWidth: node.scrollWidth,
            clientWidth: node.clientWidth,
            overflowX: overflowX
          });
        }
      }
    }
    issues.push({
      id: 'horizontal-overflow',
      severity: 'critical',
      title: 'Horizontal overflow',
      description: 'Content extends beyond viewport (scrollWidth: ' + scrollWidth + 'px > viewport: ' + vw + 'px). Causes horizontal scrolling on small screens.',
      recommendation: 'Use max-width: 100%, overflow-x: auto on containers, or fix element widths.',
      helpUrl: 'https://www.w3.org/WAI/WCAG21/Understanding/reflow.html',
      standard: 'WCAG 1.4.10 Reflow (Level AA)',
      elements: overflowElements.slice(0, 5)
    });
  }
  
  // 2. Viewport meta
  const viewport = document.querySelector('meta[name="viewport"]');
  if (!viewport) {
    issues.push({
      id: 'missing-viewport-meta',
      severity: 'critical',
      title: 'Missing viewport meta',
      description: 'No viewport meta tag. Mobile browsers may render as desktop and zoom incorrectly.',
      recommendation: 'Add <meta name="viewport" content="width=device-width, initial-scale=1">',
      helpUrl: 'https://developer.mozilla.org/en-US/docs/Web/HTML/Viewport_meta_tag',
      standard: 'W3C Mobile Best Practices',
      elements: []
    });
  } else if (!viewport.getAttribute('content') || !viewport.getAttribute('content').includes('width=')) {
    issues.push({
      id: 'invalid-viewport-meta',
      severity: 'warning',
      title: 'Invalid viewport meta',
      description: 'Viewport meta may lack width=device-width.',
      recommendation: 'Use content="width=device-width, initial-scale=1"',
      helpUrl: 'https://developer.mozilla.org/en-US/docs/Web/HTML/Viewport_meta_tag',
      standard: 'W3C Mobile Best Practices',
      elements: []
    });
  }
  
  // 3. Touch targets too small (< 44x44)
  const touchSelectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
  const touchEls = document.querySelectorAll(touchSelectors);
  const smallTargets = [];
  touchEls.forEach(el => {
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0 && (rect.width < 44 || rect.height < 44)) {
      let sel = el.id ? '#' + el.id : (el.tagName || 'div').toLowerCase();
      if (el.className && typeof el.className === 'string') {
        const c = (el.className.trim().split(/\\s+/)[0] || '').replace(/^[\\.#]/, '');
        if (c) sel += '.' + c;
      }
      smallTargets.push({
        selector: sel,
        tag: el.tagName,
        rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
        text: (el.textContent || '').trim().substring(0, 50)
      });
    }
  });
  if (smallTargets.length > 0) {
    issues.push({
      id: 'small-touch-targets',
      severity: 'warning',
      title: 'Touch targets too small',
      description: smallTargets.length + ' interactive element(s) smaller than 44x44px (WCAG 2.5.5). May be hard to tap on touch devices.',
      recommendation: 'Increase min-width/min-height to at least 44px for touch targets.',
      helpUrl: 'https://www.w3.org/WAI/WCAG21/Understanding/target-size.html',
      standard: 'WCAG 2.5.5 Target Size (Level AAA)',
      elements: smallTargets.slice(0, 8)
    });
  }
  
  // 4. Layout overlap – sibling elements overlapping (position static/relative)
  function rectsOverlap(a, b) {
    return !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom);
  }
  function getSelector(el) {
    if (el.id) return '#' + el.id;
    var c = el.className && typeof el.className === 'string' ? (el.className.trim().split(/\\s+/)[0] || '').replace(/^[\\.#]/, '') : '';
    return (el.tagName || 'div').toLowerCase() + (c ? '.' + c : '');
  }
  const overlapPairs = [];
  const allEls = document.querySelectorAll('body *');
  outerOverlap: for (var i = 0; i < Math.min(allEls.length, 200); i++) {
    for (var j = i + 1; j < Math.min(allEls.length, 200); j++) {
      var a = allEls[i], b = allEls[j];
      if (a.contains(b) || b.contains(a)) continue;
      var parent = a.parentElement;
      if (!parent || parent !== b.parentElement) continue;
      var ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
      if (ra.width < 5 || ra.height < 5 || rb.width < 5 || rb.height < 5) continue;
      var sa = window.getComputedStyle(a), sb = window.getComputedStyle(b);
      var posA = sa.position, posB = sb.position;
      if (posA === 'absolute' || posA === 'fixed' || posB === 'absolute' || posB === 'fixed') continue;
      if (rectsOverlap(ra, rb)) {
        overlapPairs.push({ selector: getSelector(a) + ' vs ' + getSelector(b), tag: a.tagName, rect: { x: Math.min(ra.x, rb.x), y: Math.min(ra.y, rb.y), w: Math.max(ra.right, rb.right) - Math.min(ra.left, rb.left), h: Math.max(ra.bottom, rb.bottom) - Math.min(ra.top, rb.top) } });
        if (overlapPairs.length >= 5) break outerOverlap;
      }
    }
  }
  if (overlapPairs.length > 0) {
    issues.push({
      id: 'layout-overlap',
      severity: 'warning',
      title: 'Layout overlap',
      description: overlapPairs.length + ' overlapping sibling element(s) detected. Elements may be stacked incorrectly at this viewport.',
      recommendation: 'Check z-index, margins, or flex/grid alignment. Ensure no unintentional overlap.',
      helpUrl: 'https://www.w3.org/WAI/WCAG21/Understanding/reflow.html',
      standard: 'WCAG 1.4.10 Reflow (Level AA)',
      elements: overlapPairs.slice(0, 5)
    });
  }
  
  // 5. Hidden content – overflow:hidden with clipped content
  const clippedEls = [];
  document.querySelectorAll('*').forEach(function(el) {
    var style = window.getComputedStyle(el);
    if (style.overflow === 'hidden' || style.overflowX === 'hidden' || style.overflowY === 'hidden') {
      var sh = el.scrollHeight, sw = el.scrollWidth, ch = el.clientHeight, cw = el.clientWidth;
      if ((sh > ch + 2) || (sw > cw + 2)) {
        var r = el.getBoundingClientRect();
        if (r.width > 20 && r.height > 20) clippedEls.push({ selector: getSelector(el), tag: el.tagName, rect: { x: r.x, y: r.y, w: r.width, h: r.height }, hidden: (sh - ch) + 'px vertical, ' + (sw - cw) + 'px horizontal' });
      }
    }
  });
  if (clippedEls.length > 0) {
    issues.push({
      id: 'hidden-content',
      severity: 'warning',
      title: 'Hidden content',
      description: clippedEls.length + ' container(s) with overflow:hidden are clipping content. Text or UI may be cut off.',
      recommendation: 'Use overflow:auto for scrollable areas, or increase container size. Avoid hiding important content.',
      helpUrl: 'https://www.w3.org/WAI/WCAG21/Understanding/reflow.html',
      standard: 'WCAG 1.4.10 Reflow (Level AA)',
      elements: clippedEls.slice(0, 5)
    });
  }
  
  // 6. Element clipping – elements extending beyond viewport or parent
  const clipRects = [];
  document.querySelectorAll('img, video, canvas, [style*="width"], [style*="min-width"]').forEach(function(el) {
    var r = el.getBoundingClientRect();
    if (r.width > vw || r.height > vh) {
      clipRects.push({ selector: getSelector(el), tag: el.tagName, rect: { x: r.x, y: r.y, w: r.width, h: r.height }, note: Math.round(r.width) + 'x' + Math.round(r.height) + ' exceeds viewport' });
    }
  });
  if (clipRects.length > 0 && !issues.some(function(i){ return i.id === 'horizontal-overflow'; })) {
    issues.push({
      id: 'element-clipping',
      severity: 'critical',
      title: 'Element clipping',
      description: clipRects.length + ' element(s) extend beyond viewport. Content may be cut off on smaller screens.',
      recommendation: 'Use max-width: 100% and height: auto for media. Ensure containers constrain large elements.',
      helpUrl: 'https://developer.mozilla.org/en-US/docs/Web/CSS/object-fit',
      standard: 'Responsive Images Best Practice',
      elements: clipRects.slice(0, 5)
    });
  }
  
  // 7. Grid breakage – grid items overflowing container
  const gridOverflows = [];
  document.querySelectorAll('*').forEach(function(cont) {
    var ds = window.getComputedStyle(cont).display;
    if (ds !== 'grid' && ds !== 'inline-grid') return;
    var cr = cont.getBoundingClientRect();
    if (cr.width < 50) return;
    var children = cont.children;
    for (var c = 0; c < children.length; c++) {
      var child = children[c];
      var r = child.getBoundingClientRect();
      if (r.right > cr.right + 5 || r.bottom > cr.bottom + 5 || r.left < cr.left - 5 || r.top < cr.top - 5) {
        gridOverflows.push({ selector: getSelector(cont) + ' > ' + getSelector(child), tag: child.tagName, rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
        if (gridOverflows.length >= 5) return;
      }
    }
  });
  if (gridOverflows.length > 0) {
    issues.push({
      id: 'grid-breakage',
      severity: 'warning',
      title: 'Grid breakage',
      description: gridOverflows.length + ' grid item(s) overflow their container. CSS Grid may be broken at this viewport.',
      recommendation: 'Use minmax(), fr units, or media queries to prevent grid overflow. Check grid-template-columns/rows.',
      helpUrl: 'https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Grid_Layout',
      standard: 'CSS Grid Layout',
      elements: gridOverflows.slice(0, 5)
    });
  }
  
  // 8. Component collapse – flex/grid children squished or collapsed
  const collapsed = [];
  document.querySelectorAll('*').forEach(function(cont) {
    var ds = window.getComputedStyle(cont).display;
    if (ds !== 'flex' && ds !== 'inline-flex') return;
    var dir = window.getComputedStyle(cont).flexDirection;
    if (dir !== 'row' && dir !== 'row-reverse') return;
    var children = cont.children;
    if (children.length < 2) return;
    var cr = cont.getBoundingClientRect();
    if (cr.width < 100) return;
    for (var c = 0; c < children.length; c++) {
      var r = children[c].getBoundingClientRect();
      if (r.width > 0 && r.width < 30 && r.height > 20) {
        collapsed.push({ selector: getSelector(cont) + ' child', tag: children[c].tagName, rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
        if (collapsed.length >= 5) return;
      }
    }
  });
  if (collapsed.length > 0) {
    issues.push({
      id: 'component-collapse',
      severity: 'warning',
      title: 'Component collapse',
      description: collapsed.length + ' flex item(s) appear overly narrow (<30px). Layout may have collapsed at this viewport.',
      recommendation: 'Set min-width on flex children or use flex-wrap. Check media query breakpoints.',
      helpUrl: 'https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Flexible_Box_Layout',
      standard: 'CSS Flexbox',
      elements: collapsed.slice(0, 5)
    });
  }
  
  return {
    viewportWidth: vw,
    viewportHeight: vh,
    scrollWidth,
    scrollHeight,
    hasOverflow: scrollWidth > vw,
    issues
  };
}
"""


@dataclass
class ResponsivenessReport:
    """Responsiveness scan report per URL."""

    url: str
    success: bool
    error: str = ""
    devices: List[dict] = field(default_factory=list)  # per-device results
    timestamp: str = ""


def run_responsiveness_scan(url: str, timeout_ms: int = 60000) -> ResponsivenessReport:
    """
    Run responsiveness scan on URL at multiple viewport sizes.
    Returns report with issues and base64 screenshots when issues found.
    """
    report = ResponsivenessReport(
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
                # Allow JavaScript-rendered content (React, lazy load, etc.) to appear
                time.sleep(3)

                for vw, vh, label in DEVICES:
                    page.set_viewport_size({"width": vw, "height": vh})
                    result = page.evaluate(RESPONSIVE_CHECKS_SCRIPT)

                    issues_list = result.get("issues", [])
                    # Make descriptions viewport-aware (avoid "on mobile" when viewing Desktop)
                    for iss in issues_list:
                        iss["_viewport"] = label
                        if iss.get("id") == "small-touch-targets":
                            if label == "Mobile":
                                iss["description"] = iss.get("description", "").replace(
                                    "May be hard to tap on touch devices.", "Hard to tap on mobile."
                                )
                            elif label == "Tablet":
                                iss["description"] = iss.get("description", "").replace(
                                    "May be hard to tap on touch devices.", "Hard to tap on tablet/touch devices."
                                )
                            else:
                                iss["description"] = iss.get("description", "").replace(
                                    "May be hard to tap on touch devices.", "May be hard to tap on touch devices (e.g. tablets, touch laptops)."
                                )
                    device_result = {
                        "label": label,
                        "viewport": {"width": vw, "height": vh},
                        "scrollWidth": result.get("scrollWidth", 0),
                        "scrollHeight": result.get("scrollHeight", 0),
                        "hasOverflow": result.get("hasOverflow", False),
                        "issues": issues_list,
                    }

                    # Take screenshot with markers on affected elements if any issue found
                    if device_result["issues"]:
                        try:
                            # Collect all element rects from issues for highlighting
                            rects = []
                            for iss in device_result["issues"]:
                                for el in iss.get("elements", []):
                                    r = el.get("rect")
                                    if r and isinstance(r, dict) and "x" in r and "y" in r:
                                        rects.append({"x": r["x"], "y": r["y"], "w": max(r.get("w", 2), 2), "h": max(r.get("h", 2), 2)})
                            if rects:
                                page.evaluate(
                                    """(rects) => {
                                      const overlay = document.createElement('div');
                                      overlay.id = 'qa-studio-marker-overlay';
                                      overlay.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647;';
                                      rects.forEach((r, i) => {
                                        const box = document.createElement('div');
                                        box.style.cssText = 'position:absolute;left:' + r.x + 'px;top:' + r.y + 'px;width:' + r.w + 'px;height:' + r.h + 'px;border:3px solid #dc2626;background:rgba(220,38,38,0.15);box-sizing:border-box;';
                                        overlay.appendChild(box);
                                      });
                                      document.body.appendChild(overlay);
                                    }""",
                                    rects,
                                )
                            screenshot_bytes = page.screenshot(type="png", full_page=False)
                            if rects:
                                page.evaluate("""() => { const o = document.getElementById('qa-studio-marker-overlay'); if (o) o.remove(); }""")
                            device_result["screenshot"] = base64.b64encode(screenshot_bytes).decode("utf-8")
                        except Exception:
                            device_result["screenshot"] = None
                    else:
                        device_result["screenshot"] = None

                    report.devices.append(device_result)

                report.success = True
                page.close()
                context.close()
            finally:
                browser.close()
    except Exception as e:
        report.error = str(e)
        report.success = False

    return report


def report_to_dict(report: ResponsivenessReport) -> dict:
    """Convert to JSON-serializable dict."""
    total_issues = 0
    total_failed = 0
    total_passed = 0
    for d in report.devices:
        issue_count = len(d.get("issues", []))
        if issue_count > 0:
            total_failed += 1
        else:
            total_passed += 1
        total_issues += issue_count

    return {
        "url": report.url,
        "success": report.success,
        "error": report.error,
        "devices": report.devices,
        "timestamp": report.timestamp,
        "summary": {
            "devices_scanned": len(report.devices),
            "devices_passed": total_passed,
            "devices_failed": total_failed,
            "total_issues": total_issues,
        },
    }


def aggregate_from_results(results: dict) -> dict:
    """Build aggregate (passed, failed, warning) from url->report results."""
    total_urls = 0
    passed = 0
    failed = 0
    warning = 0
    for url, r in results.items():
        if not r or r.get("error"):
            continue
        total_urls += 1
        s = r.get("summary", {})
        dev_passed = s.get("devices_passed", 0)
        dev_failed = s.get("devices_failed", 0)
        total_issues = s.get("total_issues", 0)
        if dev_failed == 0 and total_issues == 0:
            passed += 1
        elif total_issues > 0:
            failed += 1
        else:
            passed += 1
    return {
        "total": total_urls,
        "passed": passed,
        "failed": failed,
        "warning": warning,
    }
