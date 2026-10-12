import argparse
import csv
import os
import re

from playwright.sync_api import sync_playwright

import config


QA_PAGES_FILE = config.QA_PAGES_FILE
RESULTS_DIR = config.REPORTS_DIR
REPORT_FILE = os.path.join(RESULTS_DIR, "responsive_report.csv")
SCREENSHOT_DIR = os.path.join(config.SCREENSHOTS_DIR, "responsive")
# Clean full-page captures per page/width, used later for Figma vs staging (Phase 7).
FULL_SCREENSHOT_DIR = os.path.join(SCREENSHOT_DIR, "full_page")

VIEWPORTS = [
    {"name": "320", "width": 320, "height": 800},
    {"name": "360", "width": 360, "height": 800},
    {"name": "375", "width": 375, "height": 812},
    {"name": "390", "width": 390, "height": 844},
    {"name": "393", "width": 393, "height": 852},
    {"name": "412", "width": 412, "height": 915},
    {"name": "414", "width": 414, "height": 896},
    {"name": "430", "width": 430, "height": 932},
    {"name": "480", "width": 480, "height": 853},
    {"name": "600", "width": 600, "height": 960},
    {"name": "768", "width": 768, "height": 1024},
    {"name": "800", "width": 800, "height": 1280},
    {"name": "900", "width": 900, "height": 1280},
    {"name": "1024", "width": 1024, "height": 768},
    {"name": "1152", "width": 1152, "height": 864},
    {"name": "1280", "width": 1280, "height": 720},
    {"name": "1366", "width": 1366, "height": 768},
    {"name": "1440", "width": 1440, "height": 900},
    {"name": "1536", "width": 1536, "height": 864},
    {"name": "1600", "width": 1600, "height": 900},
    {"name": "1680", "width": 1680, "height": 1050},
    {"name": "1920", "width": 1920, "height": 1080},
    {"name": "2048", "width": 2048, "height": 1536},
    {"name": "2560", "width": 2560, "height": 1440},
]

RESPONSIVE_TIMEOUT_MS = 25000
OVERFLOW_TOLERANCE_PX = 2
MEDIA_CUT_TOLERANCE_PX = 8

# Navigation expectations per breakpoint. Widths in between are allowed to
# use either style; the report records which one each page actually shows.
MOBILE_MENU_MAX_WIDTH = 767
DESKTOP_MENU_MIN_WIDTH = 1280
MIN_DESKTOP_NAV_LINKS = 2
MENU_OPEN_WAIT_MS = 900


def load_pages():
    if os.path.exists(QA_PAGES_FILE):
        with open(QA_PAGES_FILE, "r", encoding="utf-8") as file:
            pages = [
                line.strip()
                for line in file
                if line.strip()
            ]
        if pages:
            return list(dict.fromkeys(pages))

    return ["https://www.515concretefloorpolishing.com/"]


def safe_filename(value):
    cleaned = re.sub(r"https?://", "", value)
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned or "page"


def wait_for_page_content(page):
    page.wait_for_load_state("domcontentloaded")

    page.evaluate(
        """
        async () => {
            const timeoutMs = 15000;
            const started = Date.now();
            const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

            const waitWithTimeout = (promise) => Promise.race([
                promise,
                sleep(timeoutMs)
            ]);

            if (document.fonts) {
                await waitWithTimeout(document.fonts.ready);
            }

            // Scroll screen by screen so every section passes through the viewport.
            // Scroll-reveal scripts (wow.js, AOS, etc.) only reveal a section when it is
            // actually seen; big jumps leave skipped sections invisible.
            const step = Math.max(200, Math.round(window.innerHeight * 0.8));
            for (let top = step; top < document.body.scrollHeight; top += step) {
                if (Date.now() - started > timeoutMs) break;
                window.scrollTo({ top, left: 0, behavior: 'auto' });
                await sleep(120);
            }
            window.scrollTo({ top: document.body.scrollHeight, left: 0, behavior: 'auto' });
            await sleep(800);

            window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
            await sleep(250);
        }
        """
    )


def detect_overflow(page):
    # Only flags visible content that is partially cut off by the viewport edge.
    # Ignored on purpose (normal patterns, not layout bugs):
    #   - content clipped inside an on-screen overflow container (sliders/carousels)
    #   - content entirely off-screen (closed off-canvas menus, hidden slides)
    return page.evaluate(
        r"""
        ([tolerance, mediaTolerance]) => {
            // Settle entrance animations (e.g. wow/animate.css) so elements are measured
            // in their final position, not mid-slide.
            if (document.getAnimations) {
                for (const animation of document.getAnimations()) {
                    try {
                        const timing = animation.effect && animation.effect.getComputedTiming();
                        if (timing && timing.endTime !== Infinity) animation.finish();
                    } catch (e) { /* ignore */ }
                }
            }

            const viewportWidth = document.documentElement.clientWidth;
            const mediaTags = ['img', 'video', 'iframe', 'canvas', 'svg', 'button', 'input', 'select', 'textarea'];
            const candidates = new Map();
            const flagged = [];
            let offscreenCount = 0;

            const isVisible = (el, style) => {
                if (style.display === 'none' || style.visibility === 'hidden') return false;
                if (parseFloat(style.opacity) === 0) return false;
                const rect = el.getBoundingClientRect();
                return rect.width >= 1 && rect.height >= 1;
            };

            const isOffscreen = (rect) => rect.right <= tolerance || rect.left >= viewportWidth - tolerance;

            // True when an ancestor hides the element on purpose: either it clips
            // overflow while sitting inside the viewport, or it is itself off-screen.
            const isContained = (el) => {
                for (let parent = el.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
                    const rect = parent.getBoundingClientRect();
                    if (rect.width >= 1 && isOffscreen(rect)) return true;
                    const style = window.getComputedStyle(parent);
                    if (style.overflowX !== 'visible' && rect.left >= -tolerance && rect.right <= viewportWidth + tolerance) return true;
                }
                return false;
            };

            // Measure what users actually see: rendered text boxes and media/controls.
            // Wrapper boxes (e.g. a grid .row with negative margins) are not measured,
            // because their own edges going past the viewport hide nothing.
            const addCandidate = (el, rect, isText) => {
                const existing = candidates.get(el);
                if (!existing) {
                    candidates.set(el, { left: rect.left, right: rect.right, isText });
                } else {
                    existing.left = Math.min(existing.left, rect.left);
                    existing.right = Math.max(existing.right, rect.right);
                }
            };

            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            const range = document.createRange();
            for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                const parent = node.parentElement;
                if (!parent || !node.textContent.trim()) continue;
                if (['script', 'style', 'noscript'].includes(parent.tagName.toLowerCase())) continue;
                range.selectNodeContents(node);
                for (const rect of range.getClientRects()) {
                    if (rect.width >= 1 && rect.height >= 1) addCandidate(parent, rect, true);
                }
            }

            for (const el of document.body.querySelectorAll(mediaTags.join(','))) {
                if (el.tagName.toLowerCase() !== 'svg' && el.closest('svg')) continue;
                addCandidate(el, el.getBoundingClientRect(), false);
            }

            for (const [el, box] of candidates) {
                const style = window.getComputedStyle(el);
                if (!isVisible(el, style)) continue;
                if (el.closest('[aria-hidden="true"], [inert]')) continue;

                if (isOffscreen(box)) {
                    offscreenCount += 1;
                    continue;
                }

                const cutRight = box.right - viewportWidth;
                const cutLeft = -box.left;
                const cutPx = Math.max(cutRight, cutLeft);
                // Decorative media often bleeds a few px past the edge by design.
                const limit = box.isText ? tolerance : mediaTolerance;
                if (cutPx <= limit) continue;
                if (isContained(el)) continue;

                const text = (el.innerText || el.getAttribute('alt') || '').replace(/\s+/g, ' ').trim();
                if (/^skip to (main )?content$/i.test(text)) continue;
                if (flagged.some((item) => item.element.contains(el) || el.contains(item.element))) continue;

                flagged.push({
                    element: el,
                    tag: el.tagName,
                    id: el.id || '',
                    className: (el.className && el.className.baseVal !== undefined ? el.className.baseVal : (el.className || '')).toString().slice(0, 80),
                    left: Math.round(box.left),
                    right: Math.round(box.right),
                    cutPx: Math.round(cutPx),
                    text: text.slice(0, 60)
                });
            }

            flagged.slice(0, 10).forEach((item, index) => {
                item.element.setAttribute('data-qa-responsive-issue', String(index));
            });

            const viewportMeta = document.querySelector('meta[name="viewport"]');
            return {
                viewportWidth,
                documentWidth: document.documentElement.scrollWidth,
                bodyWidth: document.body ? document.body.scrollWidth : 0,
                hasH1: !!document.querySelector('h1'),
                viewportMeta: viewportMeta ? (viewportMeta.getAttribute('content') || '') : '',
                offscreenCount,
                cutOffCount: flagged.length,
                overflowElements: flagged.slice(0, 10).map(({ element, ...rest }) => rest)
            };
        }
        """,
        [OVERFLOW_TOLERANCE_PX, MEDIA_CUT_TOLERANCE_PX],
    )


def describe_element(item):
    label = item.get("tag", "unknown")
    if item.get("id"):
        label += f"#{item['id']}"
    elif item.get("className"):
        label += "." + ".".join(item["className"].split()[:2])
    text = item.get("text", "")
    return (
        f"{label} x={item.get('left')}..{item.get('right')} "
        f"cut={item.get('cutPx')}px" + (f" \"{text}\"" if text else "")
    )


# Rule book checks (QA_RULE_BOOK.md): RESP-01 slider arrows centered, RESP-02 button
# text on one line, RESP-03 text not under a button, RESP-04 desktop menu on one row.
ARROW_CENTER_TOLERANCE_PX = 6
DESKTOP_MENU_RULE_MIN_WIDTH = 1024

RULE_BOOK_SCRIPT = r"""
([arrowTolerance, desktopMinWidth]) => {
    const vw = document.documentElement.clientWidth;
    const issues = [];
    const textOf = el => (el.innerText || el.value || el.getAttribute('aria-label') || '')
        .replace(/\s+/g, ' ').trim().slice(0, 50);
    const visible = el => {
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2 || r.right <= 0 || r.left >= vw) return false;
        for (let n = el; n && n !== document.body; n = n.parentElement) {
            const s = getComputedStyle(n);
            if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
        }
        return true;
    };
    const flag = (rule, el, message) => {
        el.setAttribute('data-qa-rule-issue', String(issues.length));
        issues.push({ rule, message, text: textOf(el) });
    };
    // Groups rects into rows by their vertical center.
    const countRows = rects => {
        const rows = [];
        for (const r of rects) {
            const c = r.top + r.height / 2;
            if (!rows.some(x => Math.abs(x - c) < Math.max(4, r.height / 2))) rows.push(c);
        }
        return rows.length;
    };
    const overlap = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2
        && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2;

    // RESP-02 / RESP-03: buttons.
    const buttons = [...document.querySelectorAll(
        'button, input[type=submit], input[type=button], .button, .btn, [role=button], ' +
        '.wc-forward, .elementor-button, .wp-block-button__link'
    )].filter(b => visible(b) && !b.closest('nav, .swiper, .slick-slider, .splide, .owl-carousel')
        && !(b.parentElement && b.parentElement.closest('.button, .btn, button, .elementor-button')));
    for (const b of buttons) {
        const label = textOf(b);
        if (!label || label.length > 40 || /\n/.test(b.innerText || '')) continue;
        if (b.tagName !== 'INPUT') {
            const range = document.createRange();
            range.selectNodeContents(b);
            const lines = [...range.getClientRects()].filter(r => r.width > 1 && r.height > 4);
            if (lines.length > 1 && countRows(lines) > 1) {
                flag('RESP-02', b, `button text wraps to ${countRows(lines)} lines`);
                continue;
            }
        }
        const br = b.getBoundingClientRect();
        const box = b.parentElement && b.parentElement.parentElement;
        if (!box) continue;
        const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            if (!node.textContent.trim() || b.contains(node) || !visible(node.parentElement)) continue;
            const range = document.createRange();
            range.selectNodeContents(node);
            if ([...range.getClientRects()].some(r => overlap(r, br))) {
                flag('RESP-03', b, `text "${node.textContent.trim().slice(0, 30)}" runs under the button`);
                break;
            }
        }
    }

    // RESP-01: slider arrows centered on their track.
    const tracks = '.swiper-wrapper, .slick-list, .splide__track, .owl-stage-outer, .flickity-viewport';
    const arrows = [...document.querySelectorAll(
        '.swiper-button-prev, .swiper-button-next, .swiper-nav-btn, .slick-prev, .slick-next, ' +
        '.owl-prev, .owl-next, .splide__arrow, .flickity-prev-next-button, .elementor-swiper-button'
    )].filter(visible);
    for (const a of arrows) {
        let track = null;
        for (let p = a.parentElement, i = 0; p && i < 5 && !track; p = p.parentElement, i++) {
            track = [...p.querySelectorAll(tracks)].find(t => visible(t) && !t.contains(a));
        }
        if (!track) continue;
        const ar = a.getBoundingClientRect(), tr = track.getBoundingClientRect();
        const arrowCenter = ar.top + ar.height / 2, trackCenter = tr.top + tr.height / 2;
        // Arrows placed above/below the track by design are not judged.
        if (arrowCenter < tr.top || arrowCenter > tr.bottom) continue;
        const offset = Math.round(arrowCenter - trackCenter);
        if (Math.abs(offset) > Math.max(arrowTolerance, tr.height * 0.1)) {
            flag('RESP-01', a, `slider arrow ${offset > 0 ? offset + 'px below' : -offset + 'px above'} the track center`);
            continue;
        }
        const slides = [...track.querySelectorAll(':scope > * > *, :scope > *')]
            .filter(s => visible(s) && s.getBoundingClientRect().width < tr.width * 0.6);
        // Only the part of a slide inside the track's visible window counts.
        const shown = s => {
            const r = s.getBoundingClientRect();
            return { left: Math.max(r.left, tr.left), right: Math.min(r.right, tr.right),
                     top: Math.max(r.top, tr.top), bottom: Math.min(r.bottom, tr.bottom) };
        };
        if (slides.length >= 2 && slides.some(s => overlap(shown(s), ar))) {
            flag('RESP-01', a, 'slider arrow overlaps a visible slide');
        }
    }

    // RESP-04: desktop header/footer menu on one row.
    if (vw >= desktopMinWidth) {
        const menus = [...document.querySelectorAll(
            'nav ul, header ul[class*=menu], footer ul[class*=menu], header ul[class*=nav], footer ul[class*=nav]'
        )].filter(ul => !ul.parentElement.closest('ul') && visible(ul));
        for (const ul of menus) {
            const items = [...ul.children].filter(li => li.tagName === 'LI' && visible(li)
                && li.querySelector(':scope > a'));
            if (items.length < 3) continue;
            const rects = items.map(li => li.getBoundingClientRect());
            const lefts = new Set(rects.map(r => Math.round(r.left)));
            if (lefts.size < 2) continue;  // vertical list, not a horizontal menu
            const rows = countRows(rects);
            if (rows > 1 && rows < items.length) {
                const where = ul.closest('footer') ? 'footer' : 'header';
                flag('RESP-04', ul, `${where} menu wraps to ${rows} rows (${items.length} items)`);
            }
        }
    }
    return issues;
}
"""


def detect_rule_book_issues(page):
    return page.evaluate(
        RULE_BOOK_SCRIPT, [ARROW_CENTER_TOLERANCE_PX, DESKTOP_MENU_RULE_MIN_WIDTH]
    )


MENU_STATE_SCRIPT = r"""
() => {
    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = window.innerHeight;

    if (document.getAnimations) {
        for (const animation of document.getAnimations()) {
            try {
                const timing = animation.effect && animation.effect.getComputedTiming();
                if (timing && timing.endTime !== Infinity) animation.finish();
            } catch (e) { /* ignore */ }
        }
    }

    // Visible = rendered, not transparent anywhere up the tree, mostly inside the
    // viewport, and actually on top at its centre (not covered by another layer).
    const isReallyVisible = (el) => {
        const rect = el.getBoundingClientRect();
        if (rect.width < 4 || rect.height < 4) return false;
        for (let node = el; node && node !== document.documentElement; node = node.parentElement) {
            const style = window.getComputedStyle(node);
            if (style.display === 'none' || style.visibility === 'hidden') return false;
            if (parseFloat(style.opacity) < 0.05) return false;
        }
        const visibleWidth = Math.min(rect.right, viewportWidth) - Math.max(rect.left, 0);
        const visibleHeight = Math.min(rect.bottom, viewportHeight) - Math.max(rect.top, 0);
        if (visibleWidth < rect.width * 0.5 || visibleHeight < rect.height * 0.5) return false;
        const x = Math.min(Math.max(rect.left + rect.width / 2, 0), viewportWidth - 1);
        const y = Math.min(Math.max(rect.top + rect.height / 2, 0), viewportHeight - 1);
        const hit = document.elementFromPoint(x, y);
        return !!hit && (hit === el || el.contains(hit) || hit.contains(el));
    };

    const header = document.querySelector('header, [role="banner"]')
        || (document.querySelector('nav') || {}).parentElement
        || document.body;

    // Nav links: text links inside navigation containers of the header,
    // excluding phone/email CTAs and the logo link.
    const navLinks = Array.from(header.querySelectorAll(
        'nav a[href], [role="navigation"] a[href], .menu a[href], .nav-menu a[href], .navbar-nav a[href]'
    )).filter((link) => {
        const href = (link.getAttribute('href') || '').trim().toLowerCase();
        if (href.startsWith('tel:') || href.startsWith('mailto:')) return false;
        return (link.innerText || '').replace(/\s+/g, ' ').trim().length > 0;
    });

    const togglePattern = /hamburger|burger|menu-toggle|menu-btn|menu-button|navbar-toggler|mobile-menu|nav-toggle|offcanvas|open menu|toggle menu|toggle navigation|main menu|^menu$/i;
    const toggleCandidates = Array.from(header.querySelectorAll(
        'button, [role="button"], a[aria-controls], a[aria-expanded], [class*="hamburger" i], [class*="menu-toggle" i], [class*="navbar-toggler" i]'
    )).filter((el) => {
        if (navLinks.includes(el)) return false;
        const signature = [
            String(el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className),
            el.id,
            el.getAttribute('aria-label') || '',
            el.getAttribute('aria-controls') || '',
            el.getAttribute('title') || '',
            (el.innerText || '').trim().slice(0, 30),
        ].join(' ');
        return togglePattern.test(signature) || el.hasAttribute('aria-expanded') && /menu|nav/i.test(signature);
    });

    document.querySelectorAll('[data-qa-menu-toggle]').forEach((el) => el.removeAttribute('data-qa-menu-toggle'));
    const toggle = toggleCandidates.find(isReallyVisible) || null;
    if (toggle) toggle.setAttribute('data-qa-menu-toggle', '1');

    const visibleLinks = navLinks.filter(isReallyVisible);
    return {
        toggleVisible: !!toggle,
        toggleLabel: toggle
            ? (toggle.getAttribute('aria-label') || (toggle.innerText || '').trim() || toggle.tagName.toLowerCase() + '.' + String(toggle.className).split(' ')[0]).slice(0, 40)
            : '',
        toggleExpanded: toggle ? toggle.getAttribute('aria-expanded') : null,
        navLinksTotal: navLinks.length,
        navLinksVisible: visibleLinks.length,
        sampleLinks: visibleLinks.slice(0, 4).map((link) => (link.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 25)),
    };
}
"""


def detect_menu(page):
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(150)
    return page.evaluate(MENU_STATE_SCRIPT)


def classify_menu_mode(menu):
    links = menu["navLinksVisible"] >= MIN_DESKTOP_NAV_LINKS
    if menu["toggleVisible"] and links:
        return "both"
    if menu["toggleVisible"]:
        return "mobile"
    if links:
        return "desktop"
    return "none"


def expected_menu_mode(width):
    if width <= MOBILE_MENU_MAX_WIDTH:
        return "mobile"
    if width >= DESKTOP_MENU_MIN_WIDTH:
        return "desktop"
    return "either"


def test_mobile_menu_opens(page):
    """Click the visible hamburger and confirm nav links become visible.

    Returns (opened: bool | None, note). None means the click itself could not
    be performed (automation problem, not a website failure).
    """
    toggle = page.locator('[data-qa-menu-toggle="1"]').first
    try:
        toggle.click(timeout=5000)
    except Exception as exc:
        return None, f"could not click menu button ({str(exc).splitlines()[0][:80]})"

    page.wait_for_timeout(MENU_OPEN_WAIT_MS)
    after = page.evaluate(MENU_STATE_SCRIPT)
    if after["navLinksVisible"] >= MIN_DESKTOP_NAV_LINKS:
        return True, (
            f"menu opened, {after['navLinksVisible']} links visible "
            f"({', '.join(after['sampleLinks'])})"
        )
    return False, (
        f"menu button clicked but only {after['navLinksVisible']} of "
        f"{after['navLinksTotal']} nav links became visible"
    )


def evaluate_menu(page, width):
    """Return (status, issue_or_note, fields) for the header navigation."""
    try:
        menu = detect_menu(page)
    except Exception as exc:
        return "WARNING", f"Menu inspection failed (automation problem): {exc}", {}

    mode = classify_menu_mode(menu)
    expected = expected_menu_mode(width)
    fields = {
        "menu_mode": mode,
        "expected_menu": expected,
        "menu_button_visible": "YES" if menu["toggleVisible"] else "NO",
        "nav_links_visible": menu["navLinksVisible"],
        "mobile_menu_opens": "",
    }

    if mode == "none":
        return "ERROR", (
            "No navigation visible: no menu button and no header nav links "
            f"({menu['navLinksTotal']} nav links exist in the DOM but none are visible)"
        ), fields

    status = "PASS"
    notes = []

    if mode == "both":
        status = "WARNING"
        notes.append(
            f"Menu button and {menu['navLinksVisible']} desktop nav links are both visible"
        )
    elif expected != "either" and mode != expected:
        status = "WARNING"
        if expected == "mobile":
            notes.append(
                "Expected a mobile menu button at this width, but the desktop nav is shown "
                f"({menu['navLinksVisible']} links) - check the links fit and are tappable"
            )
        else:
            notes.append(
                "Expected desktop nav links at this width, but only a menu button is shown "
                f"(\"{menu['toggleLabel']}\") - confirm against the design"
            )

    if menu["toggleVisible"] and mode == "mobile":
        opened, note = test_mobile_menu_opens(page)
        if opened is True:
            fields["mobile_menu_opens"] = "PASS"
            notes.append(f"Mobile menu button \"{menu['toggleLabel']}\": {note}")
        elif opened is False:
            fields["mobile_menu_opens"] = "ERROR"
            status = "ERROR"
            notes.append(f"Mobile menu button \"{menu['toggleLabel']}\": {note}")
        else:
            fields["mobile_menu_opens"] = "WARNING"
            status = "WARNING" if status == "PASS" else status
            notes.append(f"Mobile menu button \"{menu['toggleLabel']}\": {note}")
    elif mode == "desktop":
        notes.append(
            f"Desktop nav visible ({menu['navLinksVisible']} links: "
            f"{', '.join(menu['sampleLinks'])})"
        )

    return status, "; ".join(notes), fields


def worse_status(current, new):
    order = {"PASS": 0, "INFO": 0, "WARNING": 1, "ERROR": 2}
    return new if order.get(new, 0) > order.get(current, 0) else current


def take_screenshot(page, url, width, height, suffix="", highlight=True,
                    marker="data-qa-responsive-issue"):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    file_name = f"{safe_filename(url)}_{width}x{height}{suffix}.png"
    path = os.path.join(SCREENSHOT_DIR, file_name)
    try:
        # Bring the first cut-off element into view and outline it as evidence.
        if highlight:
            page.evaluate(
                """
                (marker) => {
                    const el = document.querySelector(`[${marker}="0"]`);
                    if (!el) return;
                    el.scrollIntoView({ block: 'center', inline: 'nearest' });
                    el.style.outline = '3px solid red';
                    el.style.outlineOffset = '-3px';
                }
                """,
                marker,
            )
        page.screenshot(path=path, full_page=False)
        return path
    except Exception:
        return ""


def take_full_page_screenshot(page, url, width):
    """Save the whole page as a visitor sees it (no highlights, menu closed)."""
    page_dir = os.path.join(FULL_SCREENSHOT_DIR, safe_filename(url))
    os.makedirs(page_dir, exist_ok=True)
    path = os.path.join(page_dir, f"{width}.png")
    try:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
        page.screenshot(path=path, full_page=True, animations="disabled")
        return path
    except Exception:
        return ""


def clear_old_screenshots(include_full_page=False):
    if not os.path.isdir(SCREENSHOT_DIR):
        return
    for name in os.listdir(SCREENSHOT_DIR):
        if name.lower().endswith(".png"):
            os.remove(os.path.join(SCREENSHOT_DIR, name))

    if include_full_page and os.path.isdir(FULL_SCREENSHOT_DIR):
        for page_dir in os.listdir(FULL_SCREENSHOT_DIR):
            page_path = os.path.join(FULL_SCREENSHOT_DIR, page_dir)
            if not os.path.isdir(page_path):
                continue
            for name in os.listdir(page_path):
                if name.lower().endswith(".png"):
                    os.remove(os.path.join(page_path, name))


def check_viewport(page, url, viewport, full_screenshots=False):
    width = viewport["width"]
    height = viewport["height"]
    page.set_viewport_size({"width": width, "height": height})

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=RESPONSIVE_TIMEOUT_MS)
    except Exception as exc:
        return {
            "page": url,
            "viewport": f"{width}x{height}",
            "status": "ERROR",
            "result": "ERROR",
            "details": f"Page failed to load at this viewport (automation/load problem): {exc}",
            "screenshot": "",
        }

    try:
        wait_for_page_content(page)
        layout = detect_overflow(page)
    except Exception as exc:
        return {
            "page": url,
            "viewport": f"{width}x{height}",
            "status": "ERROR",
            "result": "ERROR",
            "details": f"Layout inspection failed (automation problem): {exc}",
            "screenshot": "",
        }

    # Taken before any highlight or menu click so it shows the untouched page.
    full_page_screenshot = ""
    if full_screenshots:
        full_page_screenshot = take_full_page_screenshot(page, url, width)

    viewport_width = layout["viewportWidth"]
    document_width = layout["documentWidth"]
    horizontal_scroll = document_width > viewport_width + OVERFLOW_TOLERANCE_PX
    cut_off = layout["overflowElements"]

    issues = []
    status = "PASS"

    if horizontal_scroll:
        status = "ERROR"
        issues.append(
            f"Page scrolls horizontally: documentWidth={document_width} > viewportWidth={viewport_width}"
        )

    if cut_off:
        status = "ERROR" if horizontal_scroll else "WARNING"
        issues.append(
            f"{layout['cutOffCount']} visible element(s) cut off at the viewport edge: "
            + " ; ".join(describe_element(item) for item in cut_off[:3])
        )

    if not layout["viewportMeta"]:
        status = "WARNING" if status == "PASS" else status
        issues.append("No <meta name=\"viewport\"> tag found.")

    if not layout["hasH1"]:
        status = "WARNING" if status == "PASS" else status
        issues.append("No H1 detected at this viewport.")

    layout_status = status
    try:
        rule_issues = detect_rule_book_issues(page)
    except Exception as exc:
        rule_issues = []
        issues.append(f"Rule book check failed (automation problem): {exc}")
    if rule_issues:
        status = worse_status(status, "WARNING")
        issues.append(
            "RULE BOOK: " + " ; ".join(
                f"{item['rule']} {item['message']}" + (f" \"{item['text']}\"" if item["text"] else "")
                for item in rule_issues[:5]
            )
        )

    if issues:
        details = " | ".join(issues)
    else:
        details = (
            "No horizontal scroll and no visible content cut off at the viewport edge."
        )
        if layout["offscreenCount"]:
            details += (
                f" ({layout['offscreenCount']} element(s) intentionally off-screen, "
                "e.g. closed mobile menu / hidden slides - ignored)"
            )

    screenshots = []
    if layout_status != "PASS":
        screenshots.append(take_screenshot(page, url, width, height))
    if rule_issues:
        screenshots.append(take_screenshot(
            page, url, width, height, suffix="_rules", marker="data-qa-rule-issue"
        ))

    # Navigation check runs last because it may click the menu button.
    menu_status, menu_note, menu_fields = evaluate_menu(page, width)
    if menu_note:
        details += f" | NAV: {menu_note}"
    if menu_status != "PASS":
        screenshots.append(
            take_screenshot(page, url, width, height, suffix="_menu", highlight=False)
        )
    status = worse_status(status, menu_status)

    return {
        "page": url,
        "viewport": f"{width}x{height}",
        "viewport_width": viewport_width,
        "document_width": document_width,
        "cut_off_elements": layout["cutOffCount"],
        "rule_issues": " ; ".join(sorted({item["rule"] for item in rule_issues})),
        **menu_fields,
        "status": status,
        "result": status,
        "details": details,
        "screenshot": " ; ".join(path for path in screenshots if path),
        "full_page_screenshot": full_page_screenshot,
    }


def check_responsive(pages, viewports=None, full_screenshots=False):
    viewports = viewports or VIEWPORTS
    results = []
    clear_old_screenshots(include_full_page=full_screenshots)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        try:
            for page_number, page_url in enumerate(pages, start=1):
                print(f"[{page_number}/{len(pages)}] {page_url}")
                for viewport in viewports:
                    page = browser.new_page(viewport={
                        "width": viewport["width"],
                        "height": viewport["height"],
                    })

                    try:
                        results.append(
                            check_viewport(page, page_url, viewport, full_screenshots)
                        )
                    finally:
                        page.close()
        finally:
            browser.close()

    return results


def save_report(results):
    os.makedirs(RESULTS_DIR, exist_ok=True)

    with open(REPORT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "page", "viewport", "viewport_width", "document_width",
                "cut_off_elements", "rule_issues", "menu_mode", "expected_menu",
                "menu_button_visible", "nav_links_visible", "mobile_menu_opens",
                "status", "result", "details", "screenshot", "full_page_screenshot",
            ],
            restval="",
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResponsive report saved: {REPORT_FILE}")
    return REPORT_FILE


def print_menu_breakpoints(results):
    """Print, per page, which widths show the mobile vs desktop menu."""
    print("\nMENU BREAKPOINTS")
    print("=" * 70)
    by_page = {}
    for item in results:
        if item.get("menu_mode"):
            by_page.setdefault(item["page"], []).append(
                (int(item["viewport_width"]), item["menu_mode"])
            )

    for page_url, rows in by_page.items():
        rows.sort()
        segments = []
        for width, mode in rows:
            if segments and segments[-1][2] == mode:
                segments[-1][1] = width
            else:
                segments.append([width, width, mode])
        summary = ", ".join(
            f"{mode} {start}-{end}" if start != end else f"{mode} {start}"
            for start, end, mode in segments
        )
        print(f"{page_url}\n    {summary}")


def main():
    print("\n" + "=" * 70)
    print("PHASE 6 - RESPONSIVE TESTING")
    print("=" * 70)

    parser = argparse.ArgumentParser(description="Responsive layout checker")
    parser.add_argument(
        "--viewports",
        help="Comma-separated widths to check, e.g. 320,768,1440 (default: all)",
    )
    parser.add_argument(
        "--full-screenshots",
        action="store_true",
        help=f"Also save a clean full-page screenshot per page and width to {FULL_SCREENSHOT_DIR}",
    )
    args = parser.parse_args()

    viewports = VIEWPORTS
    if args.viewports:
        wanted = {width.strip() for width in args.viewports.split(",") if width.strip()}
        viewports = [viewport for viewport in VIEWPORTS if viewport["name"] in wanted]
        unknown = wanted - {viewport["name"] for viewport in viewports}
        if unknown:
            print(f"Unknown viewport widths ignored: {', '.join(sorted(unknown))}")

    pages = load_pages()
    print(f"Pages to check: {len(pages)}")
    print(f"Viewports     : {len(viewports)}")

    print(f"Full-page screenshots: {'ON' if args.full_screenshots else 'OFF'}")

    results = check_responsive(pages, viewports, args.full_screenshots)
    save_report(results)

    counts = {
        status: sum(item["result"] == status for item in results)
        for status in ["PASS", "WARNING", "ERROR"]
    }

    print_menu_breakpoints(results)

    print("\nRESPONSIVE SUMMARY")
    print("=" * 70)
    print(f"Total checks : {len(results)}")
    print(f"PASS         : {counts['PASS']}")
    print(f"WARNING      : {counts['WARNING']}")
    print(f"ERROR        : {counts['ERROR']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
