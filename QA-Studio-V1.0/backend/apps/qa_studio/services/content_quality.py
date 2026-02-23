"""Content Quality scan: broken links, broken images, empty content, duplicates, etc."""
import base64
import datetime
import time
import urllib.request
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

MAX_LINKS_TO_CHECK = 25
PLACEHOLDER_PATTERNS = [
    r"lorem\s+ipsum",
    r"sample\s+text",
    r"coming\s+soon",
    r"placeholder",
    r"content\s+here",
    r"add\s+content",
    r"insert\s+text",
    r"\[.*\]",  # [Header], [Content] etc.
]

CONTENT_QUALITY_SCRIPT = """
() => {
  function getSelector(el) {
    if (!el || !el.tagName) return 'unknown';
    if (el.id) return '#' + el.id;
    var tag = (el.tagName || 'div').toLowerCase();
    var c = el.className && typeof el.className === 'string' ? (el.className.trim().split(/\\s+/)[0] || '').replace(/^[\\.#]/, '') : '';
    return c ? tag + '.' + c : tag;
  }
  function isVisible(el) {
    if (!el) return false;
    var s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  
  var result = {
    links: [],
    images: [],
    emptyBlocks: [],
    textBlocks: [],
    truncated: [],
    placeholders: []
  };
  
  var baseUrl = window.location.href;
  
  // 1. Collect anchor links (for Python to check status)
  document.querySelectorAll('a[href^="http"]').forEach(function(a) {
    var href = (a.getAttribute('href') || '').trim();
    if (!href) return;
    result.links.push({ href: href, selector: getSelector(a), text: (a.textContent || '').trim().substring(0, 80), rect: a.getBoundingClientRect() });
  });
  result.links = result.links.slice(0, 50);
  
  // 2. Broken images / media
  document.querySelectorAll('img, video').forEach(function(el) {
    var r = el.getBoundingClientRect();
    if (r.width < 2 && r.height < 2) return;
    var src = el.tagName === 'IMG' ? (el.src || el.getAttribute('src')) : (el.currentSrc || el.src || el.getAttribute('src'));
    if (!src) return;
    var broken = false;
    if (el.tagName === 'IMG') {
      broken = (el.complete && el.naturalWidth === 0) || (!el.complete && el.readyState >= 2);
    } else {
      broken = el.readyState >= 2 && (el.videoWidth === 0 || el.videoHeight === 0);
    }
    if (broken) {
      result.images.push({ src: src, selector: getSelector(el), tag: el.tagName, rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
    }
  });
  
  // 3. Empty content blocks (avoid false positives: layout wrappers, decorative, structural)
  function hasVisibleChildContent(el) {
    var contentTags = ['img', 'video', 'canvas', 'svg', 'iframe', 'object', 'button', 'input'];
    for (var i = 0; i < contentTags.length; i++) {
      var nodes = el.querySelectorAll(contentTags[i]);
      for (var j = 0; j < nodes.length; j++) {
        if (isVisible(nodes[j])) return true;
      }
    }
    var buttons = el.querySelectorAll('[role="button"], [role="link"], a[href]');
    for (var k = 0; k < buttons.length; k++) {
      if (isVisible(buttons[k]) && (buttons[k].textContent || '').trim().length > 0) return true;
    }
    return false;
  }
  function isLayoutWrapper(el) {
    var s = window.getComputedStyle(el);
    var cn = (el.className && typeof el.className === 'string' ? el.className : '').toLowerCase();
    var id = (el.id || '').toLowerCase();
    var str = cn + ' ' + id;
    if (/\\bwrapper\\b|\\bcontainer\\b|\\blayout\\b|\\bbg\\b|\\bhero\\b|\\bpattern\\b|\\brow\\b|\\bcol\\b|\\bflex\\b|\\bgrid\\b/.test(str)) return true;
    if (s.backgroundImage && s.backgroundImage !== 'none') return true;
    if (/flex|grid/.test(s.display)) return true;
    if (s.minHeight && parseFloat(s.minHeight) > 0) return true;
    return false;
  }
  function isContentExpectation(el) {
    var tag = (el.tagName || '').toLowerCase();
    var role = (el.getAttribute('role') || '').toLowerCase();
    var cn = (el.className || typeof el.className === 'string' ? el.className : '').toLowerCase();
    if (tag === 'article' || tag === 'main') return true;
    if (role === 'main') return true;
    if (/content-|editable|cms-|rich-text/.test(cn)) return true;
    if (tag === 'section' && el.querySelector('h1, h2, h3, h4, h5, h6')) return true;
    if (tag === 'p' || /^h[1-6]$/.test(tag)) return true;
    return false;
  }
  function isDecorativeOrStructural(el) {
    var cn = (el.className && typeof el.className === 'string' ? el.className : '').toLowerCase();
    var tag = (el.tagName || '').toLowerCase();
    if (/parallax|animation|video-container|slide|carousel|swiper|hero|background|spacer|divider|decorative/.test(cn)) return true;
    if (el.querySelector('video, canvas, [class*="animation"]')) return true;
    return false;
  }
  function inViewport(r) {
    return r.top < window.innerHeight && r.bottom > 0 && r.left < window.innerWidth && r.right > 0;
  }
  document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, article, main, section').forEach(function(el) {
    if (!isVisible(el)) return;
    var text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
    if (text.length >= 2) return;
    var r = el.getBoundingClientRect();
    if (r.width < 40 || r.height < 25) return;
    if (!inViewport(r)) return;
    if (hasVisibleChildContent(el)) return;
    if (isLayoutWrapper(el)) return;
    if (isDecorativeOrStructural(el)) return;
    var emptyType = 'layout_wrapper';
    var reasoning = '';
    var tag = (el.tagName || '').toLowerCase();
    if (isContentExpectation(el)) {
      var hasNestedSections = el.querySelectorAll('section, article').length > 0;
      if (hasNestedSections && !el.querySelector('p, h1, h2, h3, h4, h5, h6')) {
        emptyType = 'decorative_section';
        reasoning = 'Container has no direct text but contains nested sections or serves structural layout role.';
      } else if (tag === 'article' || tag === 'main') {
        emptyType = 'broken_content_block';
        reasoning = 'Content container (article/main) has no visible content.';
      } else if (tag === 'section' || /^h[1-6]$/.test(tag) || tag === 'p') {
        emptyType = 'missing_editorial_content';
        reasoning = 'Editorial content block (heading, paragraph, or section) appears empty.';
      } else {
        emptyType = 'decorative_section';
        reasoning = 'Container has no direct text but contains visible child elements or serves structural layout role.';
      }
    } else {
      emptyType = 'layout_wrapper';
      reasoning = 'Container has no direct text but contains visible child elements or serves structural layout role.';
      return;
    }
    if (emptyType === 'layout_wrapper') return;
    result.emptyBlocks.push({
      selector: getSelector(el),
      tag: el.tagName,
      rect: { x: r.x, y: r.y, w: r.width, h: r.height },
      empty_type: emptyType,
      reasoning: reasoning,
      visible_children_detected: false
    });
  });
  result.emptyBlocks = result.emptyBlocks.slice(0, 15);
  
  // 4. Collect text blocks for duplicate detection (with parent/section context)
  function getParentContainer(el) {
    var p = el.parentElement;
    var depth = 0;
    while (p && depth < 10) {
      var sel = '';
      if (p.id) sel = '#' + p.id;
      else {
        var c = p.className && typeof p.className === 'string' ? (p.className.trim().split(/\\s+/)[0] || '').replace(/^[\\.#]/, '') : '';
        sel = (p.tagName || 'div').toLowerCase() + (c ? '.' + c : '');
      }
      var tag = (p.tagName || '').toLowerCase();
      var role = p.getAttribute('role') || '';
      var cn = (p.className || '').toLowerCase();
      if (tag === 'nav' || role === 'navigation' || /\\bnav\\b/.test(cn)) return { selector: sel, section: 'nav' };
      if (tag === 'aside' || role === 'complementary' || /\\bsidebar\\b/.test(cn)) return { selector: sel, section: 'sidebar' };
      if (tag === 'footer') return { selector: sel, section: 'footer' };
      if (/\\bcard\\b|\\bgrid-item\\b|\\blist-item\\b|\\bcarousel-item\\b|\\bslide\\b|\\btab-panel\\b/.test(cn)) return { selector: sel, section: 'component' };
      if (p.tagName === 'LI' && (p.parentElement && /ul|ol/.test((p.parentElement.tagName || '').toLowerCase()))) return { selector: sel, section: 'list' };
      p = p.parentElement;
      depth++;
    }
    return { selector: '', section: 'main' };
  }
  document.querySelectorAll('h1, h2, h3, h4, h5, h6, p').forEach(function(el) {
    if (!isVisible(el)) return;
    var text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
    if (text.length > 10) {
      var pc = getParentContainer(el);
      var words = text.split(/\\s+/).length;
      result.textBlocks.push({
        text: text,
        tag: el.tagName,
        selector: getSelector(el),
        rect: el.getBoundingClientRect(),
        parent_container_selector: pc.selector,
        section: pc.section,
        word_count: words
      });
    }
  });
  
  // 5. Truncated / clipped text (visible-text validation, design-intent filter, overlay-aware)
  function isOverlay(el) {
    if (!el || el === document.body) return false;
    var s = window.getComputedStyle(el);
    var pos = s.position;
    var z = parseInt(s.zIndex, 10);
    var r = el.getBoundingClientRect();
    var vw = window.innerWidth;
    var tag = (el.tagName || '').toLowerCase();
    var role = (el.getAttribute('role') || '').toLowerCase();
    var id = (el.id || '').toLowerCase();
    var cn = (el.className && typeof el.className === 'string' ? el.className : '').toLowerCase();
    var str = id + ' ' + cn + ' ' + role + ' ' + tag;
    var overlayKeywords = /cookie|consent|modal|dialog|banner|popup|overlay|notice|gdpr|opt-?in/i;
    if (pos === 'fixed' || pos === 'sticky') return true;
    if (z >= 1000 && r.width > vw * 0.4) return true;
    if (overlayKeywords.test(str) && (pos === 'fixed' || pos === 'sticky' || z > 100)) return true;
    return false;
  }
  function isDescendantOf(child, ancestor) {
    var p = child;
    while (p) {
      if (p === ancestor) return true;
      p = p.parentElement;
    }
    return false;
  }
  function isDesignIntentContainer(el) {
    var p = el;
    for (var d = 0; d < 8 && p; d++) {
      var cn = (p.className && typeof p.className === 'string' ? p.className : '').toLowerCase();
      if (/\\bcard\\b|\\bhero\\b|\\bslider\\b|\\bcarousel\\b|\\bgrid-item\\b|\\btile\\b|\\bbanner\\b|\\bgallery\\b|\\bslide\\b|\\bpanel\\b/.test(cn)) return true;
      var s = window.getComputedStyle(p);
      if (d < 3 && s.transform !== 'none' && s.transform !== '') return true;
      if (d < 3 && /animation|@keyframes/.test(s.animation + (s.animationName || ''))) return true;
      p = p.parentElement;
    }
    return false;
  }
  function isSliderOrCarouselContainer(el) {
    var p = el;
    for (var d = 0; d < 6 && p; d++) {
      var cn = (p.className && typeof p.className === 'string' ? p.className : '').toLowerCase();
      var id = (p.id || '').toLowerCase();
      var str = cn + ' ' + id;
      if (/\\bslider\\b|\\bcarousel\\b|\\bswiper\\b|\\bslick\\b|\\bscroll\\b|\\bvideo\\b|\\bgallery\\b|\\bhomevideoslider\\b/.test(str)) return true;
      p = p.parentElement;
    }
    return false;
  }
  function isAnimationOrCounterElement(el) {
    var cn = (el.className && typeof el.className === 'string' ? el.className : '').toLowerCase();
    var id = (el.id || '').toLowerCase();
    return /\\bdigit\\b|\\bcounter\\b|\\banimate\\b|\\bmotion\\b|\\bflip\\b|\\bticker\\b|\\bnumber\\b|\\bstat\\b/.test(cn + ' ' + id);
  }
  function hasAnimationSignals(el) {
    var p = el;
    for (var d = 0; d < 5 && p; d++) {
      var s = window.getComputedStyle(p);
      if (s.animationName && s.animationName !== 'none') return true;
      if (s.transitionDuration && s.transitionDuration !== '0s' && s.transitionDuration !== '0ms') return true;
      if (s.transform !== 'none' && s.transform !== '') return true;
      p = p.parentElement;
    }
    return false;
  }
  function isTransformOrMaskContainer(el) {
    var p = el.parentElement;
    for (var d = 0; d < 4 && p; d++) {
      var s = window.getComputedStyle(p);
      if ((s.maskImage && s.maskImage !== 'none') || (s.webkitMaskImage && s.webkitMaskImage !== 'none')) return true;
      if (s.clipPath && s.clipPath !== 'none') return true;
      if (s.transform && s.transform !== 'none' && /scale|translate/.test(s.transform)) return true;
      var cn = (p.className && typeof p.className === 'string' ? p.className : '').toLowerCase();
      if (/parallax|hero|mask|overflow/.test(cn)) return true;
      p = p.parentElement;
    }
    return false;
  }
  function isNumericOnly(text) {
    return /^[\\d\\s.,+%$-]+$/.test((text || '').trim());
  }
  function hasEllipsisOrLineClamp(el) {
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_ELEMENT);
    var node;
    while (node = walker.nextNode()) {
      var s = window.getComputedStyle(node);
      if (s.textOverflow === 'ellipsis') return true;
      if (s.webkitLineClamp && parseInt(s.webkitLineClamp, 10) > 0) return true;
    }
    var s = window.getComputedStyle(el);
    return s.textOverflow === 'ellipsis' || (s.webkitLineClamp && parseInt(s.webkitLineClamp, 10) > 0);
  }
  function hasMeaningfulText(el) {
    var text = (el.textContent || '').trim();
    if (text.length < 15) return false;
    var imgs = el.querySelectorAll('img');
    if (imgs.length > 0 && text.length < 50) return false;
    return true;
  }
  document.querySelectorAll('*').forEach(function(el) {
    var s = window.getComputedStyle(el);
    if ((s.overflow !== 'hidden' && s.overflowY !== 'hidden') && (s.overflow !== 'hidden' && s.overflowX !== 'hidden')) return;
    var sh = el.scrollHeight, ch = el.clientHeight, sw = el.scrollWidth, cw = el.clientWidth;
    if ((sh <= ch + 5) && (sw <= cw + 5)) return;
    var r = el.getBoundingClientRect();
    if (r.width < 40 || r.height < 25) return;
    if (isDesignIntentContainer(el)) {
      result.truncated.push({
        selector: getSelector(el),
        tag: el.tagName,
        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
        clipped: (sh - ch) + 'px vertical, ' + Math.max(0, sw - cw) + 'px horizontal',
        clipping_type: 'design_overflow',
        reasoning: 'Overflow detected but appears intentional layout behavior; no user-visible clipping.',
        container_selector: getSelector(el.parentElement)
      });
      return;
    }
    var ratioH = ch > 0 ? sh / ch : 1, ratioW = cw > 0 ? sw / cw : 1;
    var text = (el.textContent || '').trim();
    if (ratioH > 3 || ratioW > 3) {
      var isCounter = isNumericOnly(text) || isAnimationOrCounterElement(el);
      result.truncated.push({
        selector: getSelector(el),
        tag: el.tagName,
        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
        clipped: (sh - ch) + 'px vertical, ' + Math.max(0, sw - cw) + 'px horizontal',
        clipping_type: isCounter ? 'counter_animation' : 'animation_overflow',
        reasoning: isCounter
          ? 'Overflow detected but appears to originate from animation or slider masking behavior. Counter or digit animation pattern detected.'
          : 'Overflow detected but appears to originate from animation or slider masking behavior. Large overflow ratio suggests stacked frames or virtualized content.',
        container_selector: getSelector(el.parentElement)
      });
      return;
    }
    if (isSliderOrCarouselContainer(el)) {
      result.truncated.push({
        selector: getSelector(el),
        tag: el.tagName,
        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
        clipped: (sh - ch) + 'px vertical, ' + Math.max(0, sw - cw) + 'px horizontal',
        clipping_type: 'animation_overflow',
        reasoning: 'Overflow detected but appears to originate from animation or slider masking behavior.',
        container_selector: getSelector(el.parentElement)
      });
      return;
    }
    if (hasAnimationSignals(el) || isAnimationOrCounterElement(el)) {
      result.truncated.push({
        selector: getSelector(el),
        tag: el.tagName,
        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
        clipped: (sh - ch) + 'px vertical, ' + Math.max(0, sw - cw) + 'px horizontal',
        clipping_type: 'animation_overflow',
        reasoning: 'Overflow detected but appears to originate from animation or slider masking behavior.',
        container_selector: getSelector(el.parentElement)
      });
      return;
    }
    if (isTransformOrMaskContainer(el)) {
      result.truncated.push({
        selector: getSelector(el),
        tag: el.tagName,
        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
        clipped: (sh - ch) + 'px vertical, ' + Math.max(0, sw - cw) + 'px horizontal',
        clipping_type: 'animation_overflow',
        reasoning: 'Overflow detected but appears to originate from animation or slider masking behavior. Transform or mask container.',
        container_selector: getSelector(el.parentElement)
      });
      return;
    }
    var points = [
      { x: r.left + r.width / 2, y: r.top + r.height / 2 },
      { x: r.left + 5, y: r.top + 5 },
      { x: r.right - 5, y: r.top + 5 },
      { x: r.left + 5, y: r.bottom - 5 },
      { x: r.right - 5, y: r.bottom - 5 }
    ];
    var overlayAt = null;
    for (var i = 0; i < points.length; i++) {
      var pt = document.elementFromPoint(points[i].x, points[i].y);
      if (!pt) continue;
      if (pt !== el && !isDescendantOf(pt, el)) {
        if (isOverlay(pt)) {
          overlayAt = getSelector(pt);
          break;
        }
      }
    }
    if (overlayAt) {
      result.truncated.push({
        selector: getSelector(el),
        tag: el.tagName,
        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
        clipped: (sh - ch) + 'px vertical',
        clipping_type: 'overlay',
        overlay_selector: overlayAt,
        reasoning: 'Content appears covered by overlay element. Underlying layout does not show true clipping.'
      });
      return;
    }
    if (hasEllipsisOrLineClamp(el)) {
      result.truncated.push({
        selector: getSelector(el),
        tag: el.tagName,
        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
        clipped: 'ellipsis/line-clamp',
        clipping_type: 'intentional_truncation',
        reasoning: 'Text uses ellipsis or line-clamp. May be accessible via hover/expand.',
        container_selector: getSelector(el.parentElement)
      });
      return;
    }
    if (!hasMeaningfulText(el)) return;
    result.truncated.push({
      selector: getSelector(el),
      tag: el.tagName,
      rect: { x: r.x, y: r.y, w: r.width, h: r.height },
      clipped: (sh - ch) + 'px vertical, ' + Math.max(0, sw - cw) + 'px horizontal',
      clipping_type: 'real',
      reasoning: 'Content container clips text; scroll dimensions exceed visible area.',
      container_selector: getSelector(el.parentElement)
    });
  });
  result.truncated = result.truncated.slice(0, 20);
  
  // 6. Placeholder / dummy content
  var placeholders = ['lorem ipsum', 'sample text', 'coming soon', 'placeholder', 'content here', 'add content', 'insert text'];
  document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, div').forEach(function(el) {
    if (!isVisible(el)) return;
    var text = (el.textContent || '').trim().toLowerCase();
    if (text.length < 5) return;
    for (var i = 0; i < placeholders.length; i++) {
      if (text.indexOf(placeholders[i]) !== -1) {
        var r = el.getBoundingClientRect();
        result.placeholders.push({ selector: getSelector(el), tag: el.tagName, text: text.substring(0, 100), rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
        break;
      }
    }
  });
  result.placeholders = result.placeholders.slice(0, 10);
  
  return result;
}
"""


def _check_link_status(url: str, timeout: int = 8) -> int | None:
    """HEAD request, return status code or None on error."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 QA-Studio"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except Exception:
        return None


def _resolve_url(href: str, base: str) -> str:
    try:
        return urljoin(base, href)
    except Exception:
        return href


@dataclass
class ContentQualityReport:
    url: str
    success: bool
    error: str = ""
    checks: dict = field(default_factory=dict)
    timestamp: str = ""


def run_content_quality_scan(url: str, timeout_ms: int = 60000) -> ContentQualityReport:
    report = ContentQualityReport(
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
                time.sleep(3)
                raw = page.evaluate(CONTENT_QUALITY_SCRIPT)
            finally:
                browser.close()
    except Exception as e:
        report.error = str(e)
        return report

    report.success = True
    checks = {}
    rects_for_screenshot = []

    # 1. Broken links
    links = raw.get("links", [])[:MAX_LINKS_TO_CHECK]
    broken_links = []
    for item in links:
        resolved = _resolve_url(item["href"], url)
        status = _check_link_status(resolved)
        if status is not None and status >= 400:
            broken_links.append({
                "href": resolved,
                "selector": item.get("selector", ""),
                "text": item.get("text", ""),
                "status": status,
                "rect": item.get("rect"),
            })
            if item.get("rect"):
                r = item["rect"]
                rects_for_screenshot.append({"x": r.get("x", 0), "y": r.get("y", 0), "w": max(r.get("width", r.get("w", 2)), 2), "h": max(r.get("height", r.get("h", 2)), 2)})
    if broken_links:
        checks["broken_links"] = {
            "severity": "major",
            "count": len(broken_links),
            "issues": broken_links[:10],
        }

    # 2. Broken images
    images = raw.get("images", [])
    if images:
        for img in images:
            r = img.get("rect")
            if r:
                rects_for_screenshot.append({"x": r.get("x", 0), "y": r.get("y", 0), "w": max(r.get("w", 2), 2), "h": max(r.get("h", 2), 2)})
        checks["broken_images"] = {
            "severity": "major",
            "count": len(images),
            "issues": images[:10],
        }

    # 3. Empty content blocks (layout_wrapper ignored; decorative_section informational; editorial/broken failures)
    empty_raw = raw.get("emptyBlocks", [])
    empty_editorial = []  # missing_editorial_content, broken_content_block → failures
    empty_decorative = []  # decorative_section → informational
    for e in empty_raw:
        et = e.get("empty_type", "missing_editorial_content")
        if et == "layout_wrapper":
            continue
        issue = {
            "selector": e.get("selector"),
            "tag": e.get("tag"),
            "rect": e.get("rect"),
            "empty_type": et,
            "reasoning": e.get("reasoning", "Container appears empty."),
            "visible_children_detected": e.get("visible_children_detected", False),
        }
        severity = "informational" if et == "decorative_section" else ("major" if et == "broken_content_block" else "moderate")
        issue["severity"] = severity
        if et == "decorative_section":
            empty_decorative.append(issue)
        else:
            empty_editorial.append(issue)
    if empty_editorial:
        for e in empty_editorial[:5]:
            r = e.get("rect")
            if r:
                rects_for_screenshot.append({"x": r.get("x", 0), "y": r.get("y", 0), "w": max(r.get("w", 2), 2), "h": max(r.get("h", 2), 2)})
        sev_order = {"major": 0, "moderate": 1}
        top_sev = min(empty_editorial, key=lambda x: sev_order.get(x.get("severity", "moderate"), 2))
        checks["empty_content"] = {
            "severity": top_sev.get("severity", "moderate"),
            "count": len(empty_editorial),
            "issues": empty_editorial[:10],
        }
    if empty_decorative:
        checks["empty_content_info"] = {
            "severity": "informational",
            "count": len(empty_decorative),
            "issues": empty_decorative[:8],
            "message": "Container has no direct text but contains visible child elements or serves structural layout role.",
        }

    # 4. Duplicate content (with component/label/editorial classification)
    blocks = raw.get("textBlocks", [])
    by_text: dict = {}
    for b in blocks:
        t = b.get("text", "")
        norm = t.lower().strip()[:300].replace("\n", " ")
        if len(norm) < 10:
            continue
        by_text.setdefault(norm, []).append(b)

    component_duplicates = []
    issue_duplicates = []  # label, editorial, or large – count as failures

    for norm, occurrences in by_text.items():
        if len(occurrences) < 2:
            continue
        sections = [o.get("section", "main") for o in occurrences]
        parents = [o.get("parent_container_selector", "") for o in occurrences]
        word_counts = [o.get("word_count", 0) for o in occurrences]
        first = occurrences[0]

        # Component-pattern: same section + similar parent (nav, sidebar, footer, component, list)
        ui_sections = {"nav", "sidebar", "footer", "component", "list"}
        all_ui = all(s in ui_sections for s in sections)
        same_selector = len(set(o.get("selector", "") for o in occurrences)) == 1
        similar_parents = len(set(p.split(".")[0] if p else "" for p in parents)) <= 2

        if all_ui or (same_selector and similar_parents):
            component_duplicates.append({
                "duplicate_type": "component",
                "text": first.get("text", "")[:80] + ("..." if len(first.get("text", "")) > 80 else ""),
                "selector": first.get("selector"),
                "parent_container_selector": first.get("parent_container_selector"),
                "severity": "informational",
                "reasoning": "Repeated text detected within repeated UI component pattern. Likely intentional layout.",
                "occurrences": len(occurrences),
            })
            continue

        # Label heuristic: short text (≤5 words)
        max_words = max(word_counts) if word_counts else 0
        if max_words <= 5:
            issue_duplicates.append({
                "duplicate_type": "label",
                "text": first.get("text", "")[:80],
                "selector": first.get("selector"),
                "parent_container_selector": first.get("parent_container_selector"),
                "severity": "minor",
                "reasoning": "Short label or category text repeated across page.",
                "rect": first.get("rect"),
            })
            continue

        # Large content: long paragraphs duplicated
        if max_words > 50:
            issue_duplicates.append({
                "duplicate_type": "editorial",
                "text": first.get("text", "")[:100] + "...",
                "selector": first.get("selector"),
                "parent_container_selector": first.get("parent_container_selector"),
                "severity": "major",
                "reasoning": "Large content block duplicated. May indicate copy-paste error or template issue.",
                "rect": first.get("rect"),
            })
            continue

        # Editorial: duplicate across unrelated sections (main content, different parents)
        issue_duplicates.append({
            "duplicate_type": "editorial",
            "text": first.get("text", "")[:80] + ("..." if len(first.get("text", "")) > 80 else ""),
            "selector": first.get("selector"),
            "parent_container_selector": first.get("parent_container_selector"),
            "severity": "moderate",
            "reasoning": "Duplicate text across distinct sections. Consider consolidating or differentiating.",
            "rect": first.get("rect"),
        })

    if issue_duplicates:
        sev_order = {"major": 0, "moderate": 1, "minor": 2}
        top_sev = min(issue_duplicates, key=lambda x: sev_order.get(x.get("severity", "minor"), 3))
        checks["duplicate_content"] = {
            "severity": top_sev.get("severity", "minor"),
            "count": len(issue_duplicates),
            "issues": issue_duplicates[:10],
        }
        for d in issue_duplicates[:5]:
            r = d.get("rect")
            if r:
                rects_for_screenshot.append({
                    "x": r.get("x", 0), "y": r.get("y", 0),
                    "w": max(r.get("w", r.get("width", 2)), 2),
                    "h": max(r.get("h", r.get("height", 2)), 2),
                })

    if component_duplicates:
        checks["duplicate_content_info"] = {
            "severity": "informational",
            "count": len(component_duplicates),
            "issues": component_duplicates[:5],
            "message": "Repeated text detected within repeated UI component pattern. Likely intentional layout.",
        }

    # 5. Truncated text (real_clipping, overlay_coverage, design_overflow, animation_overflow, counter_animation, intentional_truncation)
    truncated_raw = raw.get("truncated", [])
    real_clipping = []
    overlay_coverage = []
    design_overflow = []
    animation_overflow = []
    intentional_truncation = []
    for t in truncated_raw:
        r = t.get("rect")
        ct = t.get("clipping_type", "real")
        if ct == "overlay":
            overlay_coverage.append({
                "clipping_type": "overlay",
                "selector": t.get("selector"),
                "tag": t.get("tag"),
                "rect": r,
                "overlay_selector": t.get("overlay_selector"),
                "clipped": t.get("clipped"),
                "severity": "informational",
                "reasoning": t.get("reasoning", "Content appears covered by overlay element. Underlying layout does not show true clipping."),
                "container_selector": t.get("container_selector"),
            })
        elif ct == "design_overflow":
            design_overflow.append({
                "clipping_type": "design_overflow",
                "selector": t.get("selector"),
                "tag": t.get("tag"),
                "rect": r,
                "clipped": t.get("clipped"),
                "severity": "informational",
                "reasoning": t.get("reasoning", "Overflow detected but appears intentional layout behavior; no user-visible clipping."),
                "container_selector": t.get("container_selector"),
            })
        elif ct == "animation_overflow":
            animation_overflow.append({
                "clipping_type": "animation_overflow",
                "selector": t.get("selector"),
                "tag": t.get("tag"),
                "rect": r,
                "clipped": t.get("clipped"),
                "severity": "informational",
                "reasoning": t.get("reasoning", "Overflow detected but appears to originate from animation or slider masking behavior."),
                "container_selector": t.get("container_selector"),
            })
        elif ct == "counter_animation":
            animation_overflow.append({
                "clipping_type": "counter_animation",
                "selector": t.get("selector"),
                "tag": t.get("tag"),
                "rect": r,
                "clipped": t.get("clipped"),
                "severity": "informational",
                "reasoning": t.get("reasoning", "Overflow detected but appears to originate from animation or slider masking behavior. Counter or digit animation pattern detected."),
                "container_selector": t.get("container_selector"),
            })
        elif ct == "intentional_truncation":
            intentional_truncation.append({
                "clipping_type": "intentional_truncation",
                "selector": t.get("selector"),
                "tag": t.get("tag"),
                "rect": r,
                "clipped": t.get("clipped"),
                "severity": "minor",
                "reasoning": t.get("reasoning", "Text uses ellipsis or line-clamp. May be accessible via hover/expand."),
                "container_selector": t.get("container_selector"),
            })
            if r:
                rects_for_screenshot.append({"x": r.get("x", 0), "y": r.get("y", 0), "w": max(r.get("w", 2), 2), "h": max(r.get("h", 2), 2)})
        else:
            real_clipping.append({
                "clipping_type": "real",
                "selector": t.get("selector"),
                "tag": t.get("tag"),
                "rect": r,
                "clipped": t.get("clipped"),
                "severity": "moderate",
                "reasoning": t.get("reasoning", "Content container clips text. Text may be cut off."),
                "container_selector": t.get("container_selector"),
            })
            if r:
                rects_for_screenshot.append({"x": r.get("x", 0), "y": r.get("y", 0), "w": max(r.get("w", 2), 2), "h": max(r.get("h", 2), 2)})
    if real_clipping or intentional_truncation:
        all_issues = real_clipping + intentional_truncation
        top_sev = "moderate" if real_clipping else "minor"
        checks["truncated_text"] = {
            "severity": top_sev,
            "count": len(all_issues),
            "issues": all_issues[:10],
        }
    if overlay_coverage:
        checks["truncated_text_info"] = {
            "severity": "informational",
            "count": len(overlay_coverage),
            "issues": overlay_coverage[:8],
            "message": "Content appears covered by overlay element (e.g. cookie banner). Underlying layout does not show true clipping.",
        }
    if design_overflow or animation_overflow:
        design_msg = "Overflow detected but appears intentional layout behavior; no user-visible clipping."
        anim_msg = "Overflow detected but appears to originate from animation or slider masking behavior."
        combined = design_overflow + animation_overflow
        if "truncated_text_info" in checks:
            info = checks["truncated_text_info"]
            info["count"] = info.get("count", 0) + len(combined)
            info["issues"] = (info.get("issues", []) + combined[:6])[:15]
            info["message"] = info.get("message", "") + " " + (design_msg if design_overflow else "") + (" " + anim_msg if animation_overflow else "")
        else:
            checks["truncated_text_info"] = {
                "severity": "informational",
                "count": len(combined),
                "issues": combined[:10],
                "message": design_msg + " " + anim_msg if design_overflow and animation_overflow else (design_msg if design_overflow else anim_msg),
            }

    # 6. Placeholder content
    placeholders = raw.get("placeholders", [])
    if placeholders:
        for p in placeholders[:5]:
            r = p.get("rect")
            if r:
                rects_for_screenshot.append({"x": r.get("x", 0), "y": r.get("y", 0), "w": max(r.get("w", 2), 2), "h": max(r.get("h", 2), 2)})
        checks["placeholder_content"] = {
            "severity": "minor",
            "count": len(placeholders),
            "issues": placeholders[:10],
        }

    report.checks = checks

    # Screenshot with markers
    if checks and rects_for_screenshot:
        try:
            with sync_playwright() as p2:
                browser = p2.chromium.launch(headless=True)
                try:
                    context = browser.new_context(
                        ignore_https_errors=True,
                        bypass_csp=True,
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    )
                    page = context.new_page()
                    page.goto(url, wait_until="load", timeout=timeout_ms)
                    time.sleep(2)
                    page.evaluate(
                        """(rects) => {
                          const overlay = document.createElement('div');
                          overlay.id = 'qa-studio-marker-overlay';
                          overlay.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647;';
                          rects.forEach((r) => {
                            const box = document.createElement('div');
                            box.style.cssText = 'position:absolute;left:' + r.x + 'px;top:' + r.y + 'px;width:' + r.w + 'px;height:' + r.h + 'px;border:3px solid #dc2626;background:rgba(220,38,38,0.15);box-sizing:border-box;';
                            overlay.appendChild(box);
                          });
                          document.body.appendChild(overlay);
                        }""",
                        rects_for_screenshot[:15],
                    )
                    screenshot_bytes = page.screenshot(type="png", full_page=False)
                    report.checks["_screenshot"] = base64.b64encode(screenshot_bytes).decode("utf-8")
                finally:
                    browser.close()
        except Exception:
            pass

    return report


def report_to_dict(report: ContentQualityReport) -> dict:
    total_issues = 0
    passed = 0
    failed = 0
    for k, v in report.checks.items():
        if k.startswith("_"):
            continue
        if k in ("duplicate_content_info", "truncated_text_info", "empty_content_info"):
            continue
        c = v.get("count", 0)
        total_issues += c
        if c > 0:
            failed += 1
        else:
            passed += 1
    return {
        "url": report.url,
        "success": report.success,
        "error": report.error,
        "checks": report.checks,
        "timestamp": report.timestamp,
        "summary": {
            "total_issues": total_issues,
            "checks_passed": 6 - failed,
            "checks_failed": failed,
            "check_counts": {k: v.get("count", 0) for k, v in report.checks.items() if not k.startswith("_")},
        },
    }
