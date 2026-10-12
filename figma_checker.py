import argparse
import csv
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

from playwright.sync_api import sync_playwright

from figma_visual_diff import diff_sections
from responsive_checker import wait_for_page_content


# Which Figma frame designs which staging page, per project.
CONFIG_FILE = "figma_pages.json"
DEFAULT_VIEWPORT_HEIGHT = 1080

# Frame widths that mark a design as mobile / tablet / desktop.
MOBILE_MIN_WIDTH = 300
TABLET_MIN_WIDTH = 600
DESKTOP_MIN_WIDTH = 1200
# Auto-detected device frames must be page-sized, not a card or popup component.
PAGE_FRAME_MIN_HEIGHT = 1000

OUTPUT_DIR = os.path.join("results", "figma_comparison")
REPORT_FILE = os.path.join(OUTPUT_DIR, "element_comparison.csv")

FIGMA_API = "https://api.figma.com/v1"
FIGMA_TIMEOUT_S = 90
PAGE_TIMEOUT_MS = 30000

FONT_SIZE_TOLERANCE_PX = 1
LINE_HEIGHT_TOLERANCE_PX = 1
LETTER_SPACING_TOLERANCE_PX = 0.5
COLOR_CHANNEL_TOLERANCE = 3
POSITION_TOLERANCE_PX = 4
SPACING_TOLERANCE_PX = 4
# Gaps bigger than this between two texts usually contain non-text content.
MAX_TEXT_GAP_PX = 120
# Share of a section's pixels that may differ before the visual diff flags it.
VISUAL_DIFF_WARNING_RATIO = 0.05
# A later design section may sit this much above an earlier one before it counts as reordered
# (sections can overlap, e.g. a header over a hero).
SECTION_ORDER_TOLERANCE_PX = 20
SIZE_TOLERANCE_PX = 2
RADIUS_TOLERANCE_PX = 1
# A Figma box and a page box are treated as the same container only when their
# sizes are within this ratio; otherwise box properties are not compared.
BOX_SIZE_RATIO = (0.75, 1.33)
# Section-sized boxes grow with their content, so their size is evidence only.
SECTION_HEIGHT_PX = 400
FUZZY_TEXT_RATIO = 0.9

# Dummy copy in a design file that staging should replace with real content.
DESIGN_PLACEHOLDER_TEXT = re.compile(r"lorem ipsum|^author name$|^(first|full) name (last name|surname)$")

FIELDNAMES = [
    "page", "figma_node", "viewport", "element", "selector", "property",
    "figma_value", "staging_value", "difference", "status", "confidence",
    "evidence",
]


class FigmaUnavailable(Exception):
    pass


# ==========================================
# FIGMA
# ==========================================

def parse_figma_url(url):
    match = re.search(r"figma\.com/(?:design|file)/([A-Za-z0-9]+)", url)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    node_id = (query.get("node-id") or [""])[0].replace("-", ":")
    if not match or not node_id:
        raise FigmaUnavailable(
            f"Could not read file key and node-id from Figma URL: {url}"
        )
    return match.group(1), node_id


def figma_get(path, token):
    request = urllib.request.Request(
        f"{FIGMA_API}{path}", headers={"X-Figma-Token": token}
    )
    try:
        with urllib.request.urlopen(request, timeout=FIGMA_TIMEOUT_S) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        hints = {
            403: "token is invalid/expired or has no access to this file",
            404: "file or node not found",
            429: "Figma API rate limit hit - wait and retry (cached data is reused once fetched)",
        }
        raise FigmaUnavailable(
            f"Figma API {exc.code} for {path}: {hints.get(exc.code, exc.reason)}"
        )
    except urllib.error.URLError as exc:
        raise FigmaUnavailable(f"Figma API not reachable: {exc.reason}")


def fetch_figma(file_key, node_id, refresh=False):
    # Figma's API is rate limited, so the frame JSON and PNG are cached and
    # only re-downloaded with --refresh.
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_node = node_id.replace(":", "-")
    json_path = os.path.join(OUTPUT_DIR, f"figma_{file_key}_{safe_node}.json")
    png_path = os.path.join(OUTPUT_DIR, f"figma_{file_key}_{safe_node}.png")

    need_json = refresh or not os.path.exists(json_path)
    need_png = refresh or not os.path.exists(png_path)
    token = os.environ.get("FIGMA_TOKEN", "").strip()

    if need_json and not token:
        raise FigmaUnavailable(
            "FIGMA_TOKEN environment variable is not set and no cached Figma "
            "data exists. Create a personal access token in Figma "
            "(Settings > Security > Personal access tokens, scope: file content "
            "read-only) and run:  $env:FIGMA_TOKEN = \"<token>\""
        )

    if need_json:
        ids = urllib.parse.quote(node_id)
        data = figma_get(f"/files/{file_key}/nodes?ids={ids}", token)
        node = (data.get("nodes") or {}).get(node_id)
        if not node or not node.get("document"):
            raise FigmaUnavailable(f"Figma returned no document for node {node_id}")
        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(node["document"], file)

    if need_png and token:
        ids = urllib.parse.quote(node_id)
        data = figma_get(f"/images/{file_key}?ids={ids}&format=png&scale=1", token)
        image_url = (data.get("images") or {}).get(node_id)
        if image_url:
            urllib.request.urlretrieve(image_url, png_path)

    with open(json_path, "r", encoding="utf-8") as file:
        frame = json.load(file)

    return frame, png_path if os.path.exists(png_path) else ""


def figma_color(node):
    for fill in node.get("fills", []):
        if fill.get("visible", True) and fill.get("type") == "SOLID":
            color = fill["color"]
            alpha = color.get("a", 1) * fill.get("opacity", 1)
            return (
                round(color["r"] * 255),
                round(color["g"] * 255),
                round(color["b"] * 255),
                round(alpha, 2),
            )
    return None


def solid_rgba(paint):
    color = paint["color"]
    alpha = color.get("a", 1) * paint.get("opacity", 1)
    return (round(color["r"] * 255), round(color["g"] * 255), round(color["b"] * 255), round(alpha, 2))


def figma_paint(node):
    """Visible box styling of a Figma layer, or None when it paints nothing."""
    fills = [fill for fill in node.get("fills", []) if fill.get("visible", True)]
    strokes = [stroke for stroke in node.get("strokes", [])
               if stroke.get("visible", True) and stroke.get("type") == "SOLID"]
    stroke_weight = node.get("strokeWeight", 0) if strokes else 0
    shadow = any(effect.get("type") == "DROP_SHADOW" and effect.get("visible", True)
                 for effect in node.get("effects", []))
    if not fills and not stroke_weight and not shadow:
        return None

    # Figma lists fills bottom-to-top; the last one is what is seen.
    top_fill = fills[-1] if fills else None
    if top_fill is None:
        fill_kind, fill = "none", None
    elif top_fill.get("type") == "SOLID":
        fill_kind, fill = "solid", solid_rgba(top_fill)
    elif top_fill.get("type") == "IMAGE":
        fill_kind, fill = "image", None
    else:
        fill_kind, fill = "gradient", None

    radius = node.get("cornerRadius")
    if radius is None and node.get("rectangleCornerRadii"):
        radius = node["rectangleCornerRadii"][0]

    return {
        "fill_kind": fill_kind,
        "fill": fill,
        "stroke": solid_rgba(strokes[0]) if stroke_weight else None,
        "stroke_weight": stroke_weight,
        "radius": radius or 0,
        "shadow": shadow,
    }


def figma_layer_paint(node):
    # A frame's background is often a child rectangle stretched across it.
    paint = figma_paint(node)
    if paint:
        return paint
    box = node.get("absoluteBoundingBox") or {}
    area = box.get("width", 0) * box.get("height", 0)
    for child in node.get("children", []):
        child_box = child.get("absoluteBoundingBox") or {}
        if (child.get("type") == "RECTANGLE" and child.get("visible", True) and area
                and child_box.get("width", 0) * child_box.get("height", 0) >= 0.9 * area):
            return figma_paint(child)
    return None


def covered_by_image(node, depth=3):
    """True when a descendant image layer covers most of the node (photo banners)."""
    box = node.get("absoluteBoundingBox") or {}
    area = box.get("width", 0) * box.get("height", 0)
    if not area:
        return False

    def walk(current, level):
        for child in current.get("children", []):
            if child.get("visible") is False:
                continue
            child_box = child.get("absoluteBoundingBox") or {}
            has_image = any(fill.get("type") == "IMAGE" and fill.get("visible", True)
                            for fill in child.get("fills", []))
            if has_image and child_box.get("width", 0) * child_box.get("height", 0) >= 0.8 * area:
                return True
            if level < depth and walk(child, level + 1):
                return True
        return False

    return walk(node, 1)


def same_rgb(first, second, tolerance=COLOR_CHANNEL_TOLERANCE):
    return max(abs(a - b) for a, b in zip(first[:3], second[:3])) <= tolerance


def figma_container(ancestors, frame, origin):
    """Innermost ancestor that visibly paints a box behind the text."""
    frame_paint = figma_paint(frame)
    backdrop = frame_paint["fill"] if frame_paint and frame_paint["fill"] else (255, 255, 255, 1)
    found = None
    for node in ancestors:
        paint = figma_layer_paint(node)
        if not paint:
            continue
        # Frames get a white fill by default; a fill identical to what is
        # behind it with no border/shadow is invisible, so it is not a box.
        invisible = (
            paint["fill_kind"] == "solid" and paint["fill"][3] >= 0.99
            and same_rgb(paint["fill"], backdrop)
            and not paint["stroke_weight"] and not paint["shadow"]
        )
        if paint["fill_kind"] == "solid" and paint["fill"][3] >= 0.99:
            backdrop = paint["fill"]
        if invisible:
            continue
        if covered_by_image(node):
            paint = {**paint, "fill_kind": "image", "fill": None}
        box = node.get("absoluteBoundingBox") or {}
        found = {
            "id": node.get("id", ""),
            "name": node.get("name", ""),
            **paint,
            # Colour actually seen behind the text (own fill or what shows through).
            "visible_fill": backdrop,
            "x": box.get("x", 0) - origin["x"],
            "y": box.get("y", 0) - origin["y"],
            "width": box.get("width", 0),
            "height": box.get("height", 0),
        }
    return found


def extract_text_nodes(frame):
    origin = frame.get("absoluteBoundingBox") or {"x": 0, "y": 0}
    texts = []

    def walk(node, section, ancestors):
        if node.get("visible") is False:
            return
        if node.get("type") == "TEXT" and node.get("characters", "").strip():
            box = node.get("absoluteBoundingBox") or {}
            texts.append({
                "container": figma_container(ancestors, frame, origin),
                "id": node.get("id", ""),
                "name": node.get("name", ""),
                "section": section.get("name", ""),
                "section_id": section.get("id", ""),
                "text": node["characters"],
                "norm": normalize_text(node["characters"]),
                "style": node.get("style", {}),
                "color": figma_color(node),
                "mixed_styles": any(node.get("characterStyleOverrides") or []),
                "x": box.get("x", 0) - origin["x"],
                "y": box.get("y", 0) - origin["y"],
                "width": box.get("width", 0),
                "height": box.get("height", 0),
            })
        for child in node.get("children", []):
            walk(child, section, ancestors + [node])

    # Direct children of the page frame are treated as its sections.
    for child in frame.get("children", []):
        walk(child, child, [])

    return texts


# ==========================================
# STAGING
# ==========================================

def collect_staging_elements(page):
    # Every element that owns a visible text node, with its computed text styles
    # and document-relative box. Hidden ones are kept (flagged) so the report can
    # tell "missing" apart from "present but hidden" (inactive slide/tab).
    return page.evaluate(
        r"""
        () => {
            const viewportWidth = document.documentElement.clientWidth;
            const elements = [];

            const parseColor = (value) => {
                const numbers = (value || '').match(/[\d.]+/g);
                if (!numbers || numbers.length < 3) return null;
                return [+numbers[0], +numbers[1], +numbers[2], numbers.length > 3 ? +numbers[3] : 1];
            };
            const sameRgb = (a, b) => [0, 1, 2].every((i) => Math.abs(a[i] - b[i]) <= 3);

            // Innermost ancestor that visibly paints a box (background, border or
            // shadow). Wrappers painted the same colour as what is behind them are
            // skipped, mirroring the Figma side.
            const elementIndex = new Map();
            const boxIds = new WeakMap();
            let nextBoxId = 1;
            const containerOf = (el) => {
                const chain = [];
                for (let node = el; node && node !== document.body; node = node.parentElement) chain.push(node);
                chain.reverse();
                let backdrop = parseColor(getComputedStyle(document.body).backgroundColor);
                if (!backdrop || backdrop[3] === 0) backdrop = [255, 255, 255, 1];
                let found = null;
                for (const node of chain) {
                    const s = getComputedStyle(node);
                    const bg = parseColor(s.backgroundColor);
                    const filled = !!(bg && bg[3] > 0);
                    const image = s.backgroundImage !== 'none';
                    const borderWidth = parseFloat(s.borderTopWidth) || 0;
                    const borderColor = parseColor(s.borderTopColor);
                    const border = borderWidth > 0 && s.borderTopStyle !== 'none' && !!borderColor && borderColor[3] > 0;
                    const shadow = s.boxShadow !== 'none';
                    if (!filled && !image && !border && !shadow) continue;
                    const invisible = filled && bg[3] >= 0.99 && !image && !border && !shadow && sameRgb(bg, backdrop);
                    if (filled && bg[3] >= 0.99) backdrop = bg;
                    if (invisible) continue;
                    if (!boxIds.has(node)) boxIds.set(node, nextBoxId++);
                    const r = node.getBoundingClientRect();

                    // Photo banners: an <img>/<video> covering the box hides its fill.
                    const coveringMedia = Array.from(node.querySelectorAll('img, video, picture')).some((media) => {
                        const m = media.getBoundingClientRect();
                        return m.width * m.height >= 0.8 * r.width * r.height;
                    });
                    // A shadow can sit on a same-width wrapper (e.g. <header>) rather
                    // than on the inner painted box.
                    let wrapperShadow = false;
                    for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
                        const p = parent.getBoundingClientRect();
                        if (Math.abs(p.width - r.width) > 2 || p.height > r.height * 3) break;
                        if (getComputedStyle(parent).boxShadow !== 'none') { wrapperShadow = true; break; }
                    }

                    found = {
                        key: boxIds.get(node),
                        tag: node.tagName.toLowerCase(),
                        className: (node.getAttribute('class') || '').trim().slice(0, 80),
                        fillKind: coveringMedia ? 'image'
                            : image ? (/gradient/.test(s.backgroundImage) ? 'gradient' : 'image')
                            : (filled ? 'solid' : 'none'),
                        fill: filled ? s.backgroundColor : '',
                        visibleFill: `rgba(${backdrop.join(', ')})`,
                        borderWidth: border ? borderWidth : 0,
                        borderColor: border ? s.borderTopColor : '',
                        radius: parseFloat(s.borderTopLeftRadius) || 0,
                        shadow: shadow || wrapperShadow,
                        x: r.left + window.scrollX,
                        y: r.top + window.scrollY,
                        width: r.width,
                        height: r.height,
                    };
                }
                return found;
            };

            for (const el of document.body.querySelectorAll('*')) {
                const tag = el.tagName.toLowerCase();
                if (['script', 'style', 'noscript', 'template', 'option'].includes(tag)) continue;
                if (el.closest('svg')) continue;

                // Form controls show their design text as a placeholder or the
                // selected option rather than as a child text node.
                let text = '';
                let placeholder = false;
                if ((tag === 'input' || tag === 'textarea') && el.placeholder) {
                    text = el.placeholder;
                    placeholder = true;
                } else if (tag === 'select' && el.selectedOptions.length) {
                    text = el.selectedOptions[0].text;
                } else if (Array.from(el.childNodes).some(
                    (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
                )) {
                    text = el.innerText || el.textContent || '';
                }
                text = text.replace(/\s+/g, ' ').trim();
                if (!text || text.length > 2000) continue;

                const style = window.getComputedStyle(el, placeholder ? '::placeholder' : null);
                const rect = el.getBoundingClientRect();
                const visible = el.checkVisibility({ opacityProperty: true, visibilityProperty: true })
                    && rect.width >= 1 && rect.height >= 1
                    && rect.right > 0 && rect.left < viewportWidth;

                // Figma text boxes start at the glyphs, so measure where the text
                // starts: after form-control border + padding, or at the first text
                // node (skipping icons placed inside the same link/button).
                let textInset = 0;
                // Top/bottom of the text's line boxes (Figma text boxes are line
                // boxes too), so vertical gaps compare like for like. Null for
                // form controls, whose text has no measurable line box.
                let textTop = null;
                let textBottom = null;
                if (['input', 'textarea', 'select'].includes(tag)) {
                    const boxStyle = window.getComputedStyle(el);
                    textInset = (parseFloat(boxStyle.borderLeftWidth) || 0) + (parseFloat(boxStyle.paddingLeft) || 0);
                } else {
                    const textNode = Array.from(el.childNodes).find(
                        (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
                    );
                    const range = document.createRange();
                    range.selectNodeContents(textNode);
                    const textRect = range.getBoundingClientRect();
                    if (textRect.width >= 1) textInset = Math.max(0, textRect.left - rect.left);

                    range.selectNodeContents(el);
                    const lines = Array.from(range.getClientRects()).filter((line) => line.width >= 1 && line.height >= 1);
                    if (lines.length) {
                        const lineHeight = parseFloat(style.lineHeight);
                        const first = lines[0];
                        const last = lines.reduce((low, line) => (line.bottom > low.bottom ? line : low), first);
                        const leading = (line) => (lineHeight ? (lineHeight - line.height) / 2 : 0);
                        textTop = first.top - leading(first) + window.scrollY;
                        textBottom = last.bottom + leading(last) + window.scrollY;
                    }
                }

                // Menu links highlight the current page; design frames often reuse
                // one nav with a fixed link highlighted.
                const link = el.closest('a');
                const item = link ? link.closest('li') : null;
                const navLink = !!(link && item);
                const navActive = navLink && (
                    /(^|[\s_])(active|current)/i.test(`${link.className} ${item.className}`)
                    || link.getAttribute('aria-current') === 'page'
                );

                // Nearest collected ancestor, so nested text (e.g. <strong> inside
                // a matched <p>) is not reported as unexpected content.
                // querySelectorAll is in document order, so ancestors come first.
                let parentIndex = -1;
                for (let parent = el.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
                    if (elementIndex.has(parent)) { parentIndex = elementIndex.get(parent); break; }
                }
                elementIndex.set(el, elements.length);

                elements.push({
                    tag,
                    index: elements.length,
                    parentIndex,
                    navLink,
                    navActive,
                    id: el.id || '',
                    className: (el.getAttribute('class') || '').trim().slice(0, 80),
                    text,
                    visible,
                    x: rect.left + window.scrollX + textInset,
                    y: rect.top + window.scrollY,
                    textTop,
                    textBottom,
                    container: visible ? containerOf(el) : null,
                    width: rect.width,
                    height: rect.height,
                    fontFamily: style.fontFamily,
                    fontSize: style.fontSize,
                    fontWeight: style.fontWeight,
                    lineHeight: style.lineHeight,
                    letterSpacing: style.letterSpacing,
                    color: style.color,
                    textAlign: style.textAlign,
                });
            }

            return {
                elements,
                viewportWidth,
                documentHeight: document.documentElement.scrollHeight,
            };
        }
        """
    )


def page_slug(url):
    return re.sub(r"[^A-Za-z0-9]+", "_", urllib.parse.urlparse(url).path).strip("_") or "home"


def capture_staging(url, width, height):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    screenshot = os.path.join(OUTPUT_DIR, f"staging_{page_slug(url)}_{width}.png")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            wait_for_page_content(page)
            # The page may use smooth scrolling; sticky headers report positions
            # relative to the current scroll, so measure only once truly at the top.
            page.evaluate(
                """() => {
                    document.documentElement.style.scrollBehavior = 'auto';
                    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
                }"""
            )
            page.wait_for_function("() => window.scrollY === 0", timeout=5000)
            page.wait_for_timeout(300)
            data = collect_staging_elements(page)
            try:
                page.screenshot(path=screenshot, full_page=True)
            except Exception:
                screenshot = ""
        finally:
            browser.close()

    for element in data["elements"]:
        element["norm"] = normalize_text(element["text"])
    data["screenshot"] = screenshot
    return data


# ==========================================
# MATCHING
# ==========================================

def normalize_text(text):
    replacements = {
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "–": "-", "—": "-", " ": " ", " ": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip().lower()


def closest_by_position(candidates, figma_node, frame_height, document_height):
    # Repeated labels (e.g. "Learn More") are disambiguated by relative page position.
    target = figma_node["y"] / max(frame_height, 1)
    return sorted(
        candidates,
        key=lambda el: abs(el["y"] / max(document_height, 1) - target),
    )


def match_text(figma_node, elements, frame_height, document_height):
    """Returns (element, confidence, how) or (None, "", "")."""
    for pool, hidden in (
        ([el for el in elements if el["visible"]], False),
        ([el for el in elements if not el["visible"]], True),
    ):
        exact = [el for el in pool if el["norm"] == figma_node["norm"]]
        if exact:
            ranked = closest_by_position(exact, figma_node, frame_height, document_height)
            confidence = "high" if len(ranked) == 1 else "medium"
            return ranked[0], confidence, "hidden" if hidden else "exact"

        fuzzy = []
        for el in pool:
            matcher = SequenceMatcher(None, figma_node["norm"], el["norm"])
            if matcher.real_quick_ratio() < FUZZY_TEXT_RATIO:
                continue
            if matcher.quick_ratio() < FUZZY_TEXT_RATIO:
                continue
            if matcher.ratio() >= FUZZY_TEXT_RATIO:
                fuzzy.append(el)
        if fuzzy:
            ranked = closest_by_position(fuzzy, figma_node, frame_height, document_height)
            return ranked[0], "low" if hidden else "medium", "hidden" if hidden else "fuzzy"

    # One Figma layer like "Privacy Policy | Terms of Service" is often several links.
    parts = [part.strip() for part in re.split(r"\s*\|\s*", figma_node["norm"]) if part.strip()]
    if len(parts) > 1:
        visible = [el for el in elements if el["visible"]]
        found = [[el for el in visible if el["norm"] == part] for part in parts]
        if all(found):
            ranked = closest_by_position(found[0], figma_node, frame_height, document_height)
            return ranked[0], "medium", "split"

    return None, "", ""


# ==========================================
# COMPARISON
# ==========================================

def text_matches(norm, element_norm):
    if norm == element_norm or norm in element_norm:
        return True
    matcher = SequenceMatcher(None, norm, element_norm)
    return matcher.real_quick_ratio() >= FUZZY_TEXT_RATIO and matcher.ratio() >= FUZZY_TEXT_RATIO


def match_paragraphs(figma_node, elements, frame_height, document_height):
    """
    A Figma text layer holding several paragraphs is often built as one <p> per
    paragraph. Returns (element of the first paragraph, paragraphs not found) or (None, []).
    """
    parts = [part.strip() for part in re.split(r"[\r\n]+", figma_node["text"])]
    parts = [part for part in parts if len(normalize_text(part)) >= 3]
    if len(parts) < 2:
        return None, []
    visible = [element for element in elements if element["visible"]]
    found = [
        [element for element in visible if text_matches(normalize_text(part), element["norm"])]
        for part in parts
    ]
    if not any(found):
        return None, []
    first = next(index for index, candidates in enumerate(found) if candidates)
    ranked = closest_by_position(found[first], figma_node, frame_height, document_height)
    missing = [part for part, candidates in zip(parts, found) if not candidates]
    return ranked[0], missing


def css_px(value):
    match = re.match(r"^(-?[\d.]+)px$", (value or "").strip())
    return float(match.group(1)) if match else None


def css_rgba(value):
    numbers = re.findall(r"[\d.]+", value or "")
    if len(numbers) < 3:
        return None
    alpha = float(numbers[3]) if len(numbers) > 3 else 1.0
    return (round(float(numbers[0])), round(float(numbers[1])), round(float(numbers[2])), round(alpha, 2))


def format_rgba(color):
    red, green, blue, alpha = color
    hex_value = f"#{red:02X}{green:02X}{blue:02X}"
    return hex_value if alpha >= 1 else f"{hex_value} a={alpha}"


def first_font_family(value):
    return (value or "").split(",")[0].strip().strip("\"'")


def font_family_name(value):
    # next/font renames families, e.g. "__Roboto_285791" / "__Roboto_Fallback_285791".
    name = first_font_family(value)
    match = re.match(r"^__(.+?)(?:_Fallback)?_[0-9a-f]{5,}$", name)
    return match.group(1).replace("_", " ") if match else name


def compare_number(figma_value, staging_value, tolerance, unit="px"):
    difference = round(staging_value - figma_value, 2)
    status = "PASS" if abs(difference) <= tolerance else "WARNING"
    return (
        f"{figma_value:g}{unit}", f"{staging_value:g}{unit}",
        f"{difference:+g}{unit}", status,
    )


def compare_properties(figma_node, element, active_colors):
    """Yields (property, figma_value, staging_value, difference, status)."""
    style = figma_node["style"]

    figma_family = style.get("fontFamily")
    staging_family = font_family_name(element["fontFamily"])
    if figma_family:
        same = figma_family.casefold() == staging_family.casefold()
        yield (
            "font-family", figma_family, element["fontFamily"],
            "" if same else "different family",
            "PASS" if same else "WARNING",
        )

    staging_size = css_px(element["fontSize"])
    if style.get("fontSize") is not None and staging_size is not None:
        yield ("font-size", *compare_number(style["fontSize"], staging_size, FONT_SIZE_TOLERANCE_PX))

    if style.get("fontWeight") is not None:
        yield ("font-weight", *compare_number(float(style["fontWeight"]), float(element["fontWeight"]), 0, unit=""))

    staging_line = css_px(element["lineHeight"])
    if style.get("lineHeightUnit") == "INTRINSIC_%" or style.get("lineHeightPx") is None:
        yield ("line-height", "auto", element["lineHeight"], "", "INFO")
    elif staging_line is None:
        yield ("line-height", f"{style['lineHeightPx']:g}px", element["lineHeight"], "staging uses 'normal'", "INFO")
    else:
        yield ("line-height", *compare_number(round(style["lineHeightPx"], 2), staging_line, LINE_HEIGHT_TOLERANCE_PX))

    staging_spacing = css_px(element["letterSpacing"])
    if element["letterSpacing"] == "normal":
        staging_spacing = 0.0
    if staging_spacing is not None:
        yield ("letter-spacing", *compare_number(
            round(style.get("letterSpacing", 0), 2), staging_spacing, LETTER_SPACING_TOLERANCE_PX,
        ))

    staging_color = css_rgba(element["color"])
    if figma_node["color"] and staging_color:
        worst = max(abs(a - b) for a, b in zip(figma_node["color"][:3], staging_color[:3]))
        alpha_diff = abs(figma_node["color"][3] - staging_color[3])
        same = worst <= COLOR_CHANNEL_TOLERANCE and alpha_diff <= 0.05
        difference = "" if same else f"max channel diff {worst}" + (f", alpha diff {alpha_diff:.2f}" if alpha_diff > 0.05 else "")
        status = "PASS" if same else "WARNING"
        if not same and element["navLink"] and (
            element["navActive"] or figma_node["color"][:3] in active_colors
        ):
            status = "INFO"
            difference += "; current-page menu highlight - design frame highlights a different link"
        yield ("color", format_rgba(figma_node["color"]), format_rgba(staging_color), difference, status)
    elif not figma_node["color"]:
        yield ("color", "no solid fill", element["color"], "", "INFO")

    # Left edge is only a fair comparison for left-aligned text; DOM boxes of
    # centred/right text usually span the container while Figma boxes hug the text.
    x_figma = round(figma_node["x"], 1)
    x_staging = round(element["x"], 1)
    left_aligned = (
        style.get("textAlignHorizontal", "LEFT") == "LEFT"
        and element["textAlign"] in ("left", "start")
    )
    if left_aligned:
        yield ("x", *compare_number(x_figma, x_staging, POSITION_TOLERANCE_PX))
    else:
        yield ("x", f"{x_figma:g}px", f"{x_staging:g}px", f"{x_staging - x_figma:+g}px", "INFO")

    # Vertical offsets accumulate down the page, so y is reported as evidence only.
    y_figma = round(figma_node["y"], 1)
    y_staging = round(element["y"], 1)
    yield ("y", f"{y_figma:g}px", f"{y_staging:g}px", f"{y_staging - y_figma:+g}px", "INFO")


def describe_selector(element):
    if element["id"]:
        return f"{element['tag']}#{element['id']}"
    classes = element["className"].split()[:2]
    return element["tag"] + "".join(f".{name}" for name in classes)


def box_selector(box):
    classes = box["className"].split()[:2]
    return box["tag"] + "".join(f".{name}" for name in classes)


def format_fill(kind, color):
    return format_rgba(color) if kind == "solid" and color else kind


def compare_container(figma_box, dom_box, figma_text, element):
    """Yields (property, figma_value, staging_value, difference, status) for one box."""
    low, high = BOX_SIZE_RATIO
    width_ratio = dom_box["width"] / max(figma_box["width"], 1)
    height_ratio = dom_box["height"] / max(figma_box["height"], 1)
    if not (low <= width_ratio <= high and low <= height_ratio <= high):
        yield (
            "box-mapping",
            f"{figma_box['width']:.0f}x{figma_box['height']:.0f}px",
            f"{dom_box['width']:.0f}x{dom_box['height']:.0f}px",
            "sizes too different to be sure it is the same box; box styles not compared",
            "INFO",
        )
        return

    # Compare the background colour actually seen: the box's own fill, or the
    # colour showing through when one side paints it on a wrapper instead.
    figma_kind, dom_kind = figma_box["fill_kind"], dom_box["fillKind"]
    dom_fill = css_rgba(dom_box["fill"]) if dom_kind == "solid" else None
    if "image" in (figma_kind, dom_kind) or "gradient" in (figma_kind, dom_kind):
        yield ("box-background", figma_kind, dom_kind, "image/gradient backgrounds are not compared", "INFO")
    else:
        figma_seen = figma_box["fill"] if figma_kind == "solid" else figma_box["visible_fill"]
        dom_seen = dom_fill if dom_kind == "solid" else css_rgba(dom_box["visibleFill"])
        worst = max(abs(a - b) for a, b in zip(figma_seen[:3], dom_seen[:3]))
        alpha_diff = abs(figma_seen[3] - dom_seen[3])
        same = worst <= COLOR_CHANNEL_TOLERANCE and alpha_diff <= 0.05
        yield (
            "box-background", format_rgba(figma_seen), format_rgba(dom_seen),
            "" if same else f"max channel diff {worst}" + (f", alpha diff {alpha_diff:.2f}" if alpha_diff > 0.05 else ""),
            "PASS" if same else "WARNING",
        )

    # A border the same colour as its own background cannot be seen; ignore it.
    figma_border, dom_border = figma_box["stroke_weight"], dom_box["borderWidth"]
    dom_border_color = css_rgba(dom_box["borderColor"]) if dom_border else None
    if figma_border and figma_box["fill"] and same_rgb(figma_box["stroke"], figma_box["fill"]):
        figma_border = 0
    if dom_border and dom_fill and same_rgb(dom_border_color, dom_fill):
        dom_border = 0
    if figma_border or dom_border:
        same = bool(
            figma_border and dom_border and abs(figma_border - dom_border) <= 0.5
            and same_rgb(figma_box["stroke"], dom_border_color)
        )
        yield (
            "box-border",
            f"{figma_border:g}px {format_rgba(figma_box['stroke'])}" if figma_border else "none",
            f"{dom_border:g}px {format_rgba(dom_border_color)}" if dom_border else "none",
            "" if same else "border differs",
            "PASS" if same else "WARNING",
        )

    # Pill shapes are often 9999px in CSS and e.g. 100px in Figma; clamp both
    # to half the shorter side, which is what is actually drawn.
    figma_radius = min(figma_box["radius"], min(figma_box["width"], figma_box["height"]) / 2)
    dom_radius = min(dom_box["radius"], min(dom_box["width"], dom_box["height"]) / 2)
    if figma_radius or dom_radius:
        yield ("box-radius", *compare_number(round(figma_radius, 1), round(dom_radius, 1), RADIUS_TOLERANCE_PX))

    if figma_box["shadow"] or dom_box["shadow"]:
        same = figma_box["shadow"] == dom_box["shadow"]
        yield (
            "box-shadow", "yes" if figma_box["shadow"] else "none", "yes" if dom_box["shadow"] else "none",
            "" if same else "shadow missing or added", "PASS" if same else "WARNING",
        )

    section_sized = figma_box["height"] > SECTION_HEIGHT_PX
    for prop, figma_size, dom_size in (
        ("box-width", figma_box["width"], dom_box["width"]),
        ("box-height", figma_box["height"], dom_box["height"]),
    ):
        figma_value, staging_value, difference, status = compare_number(
            round(figma_size, 1), round(dom_size, 1), SIZE_TOLERANCE_PX,
        )
        yield (prop, figma_value, staging_value, difference, "INFO" if section_sized else status)

    # Inner spacing: where the box's first text starts inside it.
    left_aligned = (
        figma_text["style"].get("textAlignHorizontal", "LEFT") == "LEFT"
        and element["textAlign"] in ("left", "start")
    )
    figma_value, staging_value, difference, status = compare_number(
        round(figma_text["x"] - figma_box["x"], 1), round(element["x"] - dom_box["x"], 1), POSITION_TOLERANCE_PX,
    )
    yield ("box-padding-left", figma_value, staging_value, difference, status if left_aligned else "INFO")
    if element["textTop"] is not None:
        yield ("box-padding-top", *compare_number(
            round(figma_text["y"] - figma_box["y"], 1), round(element["textTop"] - dom_box["y"], 1), POSITION_TOLERANCE_PX,
        ))


def compare_boxes(matched):
    """Yields (figma_text, element, confidence, figma_box, dom_box, results) per Figma box."""
    groups = {}
    for figma_text, element, confidence in matched:
        if figma_text["container"]:
            groups.setdefault(figma_text["container"]["id"], []).append((figma_text, element, confidence))

    for items in groups.values():
        # The box's top-most text anchors it to the page element around that text.
        figma_text, element, confidence = min(items, key=lambda item: item[0]["y"])
        figma_box = figma_text["container"]
        dom_box = element.get("container")
        if dom_box is None:
            results = [(
                "box-mapping", format_fill(figma_box["fill_kind"], figma_box["fill"]), "no painted container",
                "no box with a background/border/shadow found around this text on staging", "INFO",
            )]
        else:
            results = list(compare_container(figma_box, dom_box, figma_text, element))
        yield figma_text, element, confidence, figma_box, dom_box, results


def lower_confidence(first, second):
    order = ["low", "medium", "high"]
    return min(first, second, key=lambda value: order.index(value) if value in order else 0)


def extract_leaf_layers(frame):
    """Visible non-text leaf layers (images, icons, dividers, shapes) of a frame."""
    origin = frame.get("absoluteBoundingBox") or {"x": 0, "y": 0}
    layers = []

    def walk(node):
        if node.get("visible") is False:
            return
        children = node.get("children", [])
        if not children and node.get("type") != "TEXT":
            box = node.get("absoluteBoundingBox") or {}
            if max(box.get("width", 0), box.get("height", 0)) >= 8:
                layers.append({
                    "x": box.get("x", 0) - origin["x"],
                    "y": box.get("y", 0) - origin["y"],
                    "width": box.get("width", 0),
                    "height": box.get("height", 0),
                })
        for child in children:
            walk(child)

    for child in frame.get("children", []):
        walk(child)
    return layers


def figma_layer_between(upper, lower, layers):
    """True when another visible Figma layer sits in the gap between two texts."""
    top = upper["y"] + upper["height"]
    bottom = lower["y"]
    left = max(upper["x"], lower["x"])
    right = min(upper["x"] + upper["width"], lower["x"] + lower["width"])
    for layer in layers:
        if layer["y"] + layer["height"] <= top + 1 or layer["y"] >= bottom - 1:
            continue
        # Backgrounds behind both texts are not "between" them.
        if layer["y"] <= upper["y"] + 1 and layer["y"] + layer["height"] >= bottom + lower["height"] - 1:
            continue
        if min(layer["x"] + layer["width"], right) - max(layer["x"], left) > 0:
            return True
    return False


def compare_spacing(matched, texts, layers):
    """Yields (upper, lower, confidence, results) for vertically stacked text in one column."""
    by_id = {item[0]["id"]: item for item in matched if item[1]["textTop"] is not None}

    for upper_figma in texts:
        upper = by_id.get(upper_figma["id"])
        if not upper:
            continue
        # Nearest design text directly below in the same column and section,
        # whether or not it was matched; pairs are only measured when adjacent.
        below = [
            text for text in texts
            if text["section_id"] == upper_figma["section_id"]
            and text["y"] >= upper_figma["y"] + upper_figma["height"] - 1
            and min(text["x"] + text["width"], upper_figma["x"] + upper_figma["width"])
            - max(text["x"], upper_figma["x"]) > 0
        ]
        if not below:
            continue
        lower = by_id.get(min(below, key=lambda text: text["y"])["id"])
        if not lower or lower[1] is upper[1]:
            continue
        if figma_layer_between(upper_figma, lower[0], layers):
            continue

        figma_gap = lower[0]["y"] - (upper_figma["y"] + upper_figma["height"])
        site_gap = lower[1]["textTop"] - upper[1]["textBottom"]
        figma_value, staging_value, difference, status = compare_number(
            round(figma_gap, 1), round(site_gap, 1), SPACING_TOLERANCE_PX,
        )
        note = ""
        # A fixed-height Figma text box does not hug its text, so its gap is unreliable.
        if "NONE" in (upper_figma["style"].get("textAutoResize"), lower[0]["style"].get("textAutoResize")):
            status = "INFO" if status == "WARNING" else status
            note = "Figma text box has a fixed height; gap may not reflect the visible spacing"
        elif max(figma_gap, site_gap) > MAX_TEXT_GAP_PX:
            status = "INFO" if status == "WARNING" else status
            note = "Large gap - likely spans non-text content on staging; evidence only"
        yield upper, lower, lower_confidence(upper[2], lower[2]), (figma_value, staging_value, difference, status, note)


def section_offsets(figma_frame, matched):
    """
    Each Figma section with how far it sits lower (+) / higher (-) on staging,
    taken from the median offset of its matched texts. Sections without text
    (e.g. a photo strip) reuse the previous section's offset.
    """
    origin = figma_frame.get("absoluteBoundingBox") or {"x": 0, "y": 0}
    offsets_by_section = {}
    tops_by_section = {}
    figma_tops_by_section = {}
    for figma_text, element, _ in matched:
        staging_top = staging_text_top(element)
        offsets_by_section.setdefault(figma_text["section_id"], []).append(staging_top - figma_text["y"])
        tops_by_section.setdefault(figma_text["section_id"], []).append(staging_top)
        figma_tops_by_section.setdefault(figma_text["section_id"], []).append(figma_text["y"])

    sections = []
    for child in figma_frame.get("children", []):
        box = child.get("absoluteBoundingBox")
        if child.get("visible") is False or not box:
            continue
        tops = sorted(tops_by_section.get(child.get("id", ""), []))
        figma_tops = sorted(figma_tops_by_section.get(child.get("id", ""), []))
        sections.append({
            "name": child.get("name", ""),
            "id": child.get("id", ""),
            "y": box["y"] - origin["y"],
            "height": box["height"],
            "anchored": bool(tops),
            "staging_median_y": tops[len(tops) // 2] if tops else None,
            "figma_median_y": figma_tops[len(figma_tops) // 2] if figma_tops else None,
        })
    sections.sort(key=lambda section: section["y"])

    previous = 0.0
    for section in sections:
        values = sorted(offsets_by_section.get(section["id"], []))
        if values:
            previous = values[len(values) // 2]
        section["offset"] = previous
    return sections


def staging_text_top(element):
    return element["textTop"] if element["textTop"] is not None else element["y"]


def section_order_rows(sections, staging_url, viewport):
    """One row per page: do the design's sections appear in the same order on staging?"""
    # Ordered by where each section's text sits, not its top edge: a header can
    # overlap a hero that starts at y=0 while the hero's text is lower down.
    anchored = sorted(
        (section for section in sections if section["anchored"]),
        key=lambda section: section["figma_median_y"],
    )
    out_of_order = [
        f"\"{later['name']}\" (Figma text y {later['figma_median_y']:.0f}) appears above "
        f"\"{earlier['name']}\" (Figma text y {earlier['figma_median_y']:.0f})"
        for earlier, later in zip(anchored, anchored[1:])
        if later["staging_median_y"] < earlier["staging_median_y"] - SECTION_ORDER_TOLERANCE_PX
    ]
    unanchored = [section["name"] for section in sections if not section["anchored"]]
    evidence = "Order judged from the median position of each section's matched text."
    if unanchored:
        evidence += f" Not checked (no matched text): {', '.join(unanchored)}."
    return [{
        "page": staging_url, "figma_node": "page sections", "viewport": viewport,
        "element": "[page] section order", "selector": "", "property": "section_order",
        "figma_value": " > ".join(section["name"] for section in anchored),
        "staging_value": "same order" if not out_of_order else "order differs",
        "difference": "; ".join(out_of_order),
        "status": "WARNING" if out_of_order else "PASS",
        "confidence": "medium", "evidence": evidence,
    }]


def section_at(sections, y):
    """Figma section whose staging position (Figma y + offset) contains y."""
    for section in sections:
        top = section["y"] + section["offset"]
        if top <= y < top + section["height"]:
            return section
    return None


def unexpected_content_rows(texts, elements, matched, sections, staging_url, viewport):
    """Visible staging text with no counterpart in the design."""
    matched_indexes = {element["index"] for _, element, _ in matched}
    by_index = {element["index"]: element for element in elements}
    design_norms = [text["norm"] for text in texts]
    placeholder_sections = {text["section_id"] for text in texts if DESIGN_PLACEHOLDER_TEXT.search(text["norm"])}
    reported = set()
    reported_spots = set()
    rows = []

    def ancestor_in(element, indexes):
        parent = element["parentIndex"]
        while parent != -1:
            if parent in indexes:
                return True
            parent = by_index[parent]["parentIndex"]
        return False

    def in_design(norm):
        # Pieces of a design text (split links, inline emphasis) count as present.
        for design in design_norms:
            if norm in design:
                return True
            matcher = SequenceMatcher(None, norm, design)
            if matcher.real_quick_ratio() >= FUZZY_TEXT_RATIO and matcher.ratio() >= FUZZY_TEXT_RATIO:
                return True
        return False

    for element in elements:
        if not element["visible"] or element["width"] < 4 or element["height"] < 4:
            continue
        if len(re.findall(r"[a-z]", element["norm"])) < 2:
            continue
        if element["index"] in matched_indexes or ancestor_in(element, matched_indexes):
            continue
        if ancestor_in(element, reported) or in_design(element["norm"]):
            continue
        # The same text at the same spot (e.g. a duplicated widget layer) is one finding.
        spot = (element["norm"], round(element["x"]), round(staging_text_top(element)))
        if spot in reported_spots:
            continue
        reported_spots.add(spot)
        reported.add(element["index"])

        section = section_at(sections, staging_text_top(element))
        if section and section["id"] in placeholder_sections:
            status = "INFO"
            evidence = "Section uses placeholder copy in the design; likely the real content replacing it."
        else:
            status = "WARNING"
            evidence = "Visible on staging but no matching text in the Figma frame (added content or design not updated)."
        rows.append({
            "page": staging_url,
            "figma_node": f"section: {section['name']}" if section else "outside design sections",
            "viewport": viewport,
            "element": element["text"][:80],
            "selector": describe_selector(element),
            "property": "unexpected_content",
            "figma_value": "not in design",
            "staging_value": element["text"][:200],
            "difference": f"staging y {staging_text_top(element):.0f}",
            "status": status, "confidence": "medium", "evidence": evidence,
        })
    return rows


def visual_diff_rows(figma_png, staging, sections, staging_url, viewport):
    if not figma_png or not staging.get("screenshot"):
        return []
    width = viewport.split("x")[0]
    output_path = os.path.join(OUTPUT_DIR, f"visual_diff_{page_slug(staging_url)}_{width}.png")
    try:
        results = diff_sections(figma_png, staging["screenshot"], sections, output_path)
    except Exception as exc:
        return [error_row(staging_url, "visual diff", viewport, f"Visual diff failed (automation problem): {exc}")]

    rows = []
    for result in results:
        differences = []
        if result["regions"]:
            differences.append("changed rows (Figma y): " + "; ".join(
                f"y {region['start']:.0f}-{region['end']:.0f} ({region['ratio']:.0%})" for region in result["regions"]
            ))
        if result["hot_spots"]:
            differences.append("localized changes (Figma x/y): " + "; ".join(
                f"x {spot['x']:.0f}-{spot['x'] + spot['width']:.0f}, y {spot['y']:.0f}-{spot['y'] + spot['height']:.0f}"
                for spot in result["hot_spots"]
            ))
        status = "WARNING" if result["mismatch"] >= VISUAL_DIFF_WARNING_RATIO or result["hot_spots"] else "PASS"
        notes = [f"Diff image: {output_path}"]
        if not result["anchored"]:
            status = "INFO" if status == "WARNING" else status
            notes.insert(0, "No matched text in this section; alignment estimated from the previous section")
        rows.append({
            "page": staging_url,
            "figma_node": f"{result['id']} ({result['name']})",
            "viewport": viewport,
            "element": f"[section] {result['name']}",
            "selector": "",
            "property": "visual-diff",
            "figma_value": f"y {result['y']:.0f}, height {result['height']:.0f}px",
            "staging_value": f"{result['mismatch']:.1%} of pixels changed (staging y {result['staging_y']:.0f})",
            "difference": " | ".join(differences),
            "status": status,
            "confidence": "medium" if result["anchored"] else "low",
            "evidence": "; ".join(notes),
        })
    return rows


def compare(figma_frame, figma_png, staging, staging_url, viewport):
    frame_box = figma_frame.get("absoluteBoundingBox") or {}
    frame_height = frame_box.get("height", 1)
    texts = extract_text_nodes(figma_frame)
    elements = staging["elements"]
    active_colors = {
        css_rgba(el["color"])[:3] for el in elements
        if el["navActive"] and el["visible"] and css_rgba(el["color"])
    }
    evidence_files = "; ".join(path for path in (figma_png, staging["screenshot"]) if path)

    rows = []
    sections = {}
    matched = []

    def row(figma_node, **values):
        rows.append({
            "page": staging_url,
            "figma_node": f"{figma_node['id']} ({figma_node['name']})",
            "viewport": viewport,
            "element": figma_node["text"].replace("\n", " ")[:80],
            **values,
        })

    for figma_node in texts:
        section = sections.setdefault(figma_node["section"], {"total": 0, "matched": 0, "y": figma_node["y"]})
        section["total"] += 1

        element, confidence, how = match_text(figma_node, elements, frame_height, staging["documentHeight"])
        missing_paragraphs = []
        if element is None:
            element, missing_paragraphs = match_paragraphs(figma_node, elements, frame_height, staging["documentHeight"])
            if element is not None:
                confidence, how = "medium", "paragraphs"

        if element is None and DESIGN_PLACEHOLDER_TEXT.search(figma_node["norm"]):
            row(
                figma_node, selector="", property="text_presence",
                figma_value=figma_node["text"][:120], staging_value="not compared",
                difference="", status="INFO", confidence="",
                evidence="Placeholder copy in the design (e.g. lorem ipsum); staging is expected to show real content.",
            )
            continue

        if element is None:
            row(
                figma_node, selector="", property="text_presence",
                figma_value=figma_node["text"][:120], staging_value="not found",
                difference="", status="WARNING", confidence="",
                evidence="Design text not found on staging: copy changed, missing, or rendered as an image. " + evidence_files,
            )
            continue

        if how == "hidden":
            row(
                figma_node, selector=describe_selector(element), property="text_presence",
                figma_value=figma_node["text"][:120], staging_value=element["text"][:120],
                difference="", status="INFO", confidence=confidence,
                evidence="Text exists in the DOM but is not visible at this viewport (e.g. inactive slide/tab); styles not compared.",
            )
            continue

        section["matched"] += 1
        if how == "fuzzy":
            row(
                figma_node, selector=describe_selector(element), property="text_content",
                figma_value=figma_node["text"][:200], staging_value=element["text"][:200],
                difference="wording differs", status="WARNING", confidence=confidence,
                evidence="Near-identical text: check whether the copy change is intended.",
            )
        if missing_paragraphs:
            row(
                figma_node, selector=describe_selector(element), property="text_content",
                figma_value=" / ".join(missing_paragraphs)[:200], staging_value="paragraph not found",
                difference=f"{len(missing_paragraphs)} paragraph(s) of this design text missing on staging",
                status="WARNING", confidence=confidence,
                evidence="Design text has several paragraphs; the others were found as separate elements.",
            )
        notes = [f"match={how}"]
        if how == "fuzzy":
            notes.append(f"staging text: \"{element['text'][:80]}\"")
        if figma_node["mixed_styles"]:
            confidence = "medium" if confidence == "high" else confidence
            notes.append("Figma text has mixed character styles; compared base style")
        evidence = "; ".join(notes)
        matched.append((figma_node, element, confidence))

        for prop, figma_value, staging_value, difference, status in compare_properties(figma_node, element, active_colors):
            row(
                figma_node, selector=describe_selector(element), property=prop,
                figma_value=figma_value, staging_value=staging_value,
                difference=difference, status=status, confidence=confidence,
                evidence=evidence,
            )

    for figma_text, element, confidence, figma_box, dom_box, results in compare_boxes(matched):
        for prop, figma_value, staging_value, difference, status in results:
            rows.append({
                "page": staging_url,
                "figma_node": f"{figma_box['id']} ({figma_box['name']})",
                "viewport": viewport,
                "element": f"[box] {figma_box['name']}: \"{figma_text['text'][:40]}\"".replace("\n", " "),
                "selector": box_selector(dom_box) if dom_box else "",
                "property": prop,
                "figma_value": figma_value, "staging_value": staging_value,
                "difference": difference, "status": status, "confidence": confidence,
                "evidence": f"Container around text \"{figma_text['text'][:40]}\"".replace("\n", " "),
            })

    for upper, lower, confidence, (figma_value, staging_value, difference, status, note) in compare_spacing(matched, texts, extract_leaf_layers(figma_frame)):
        rows.append({
            "page": staging_url,
            "figma_node": f"{upper[0]['id']} -> {lower[0]['id']}",
            "viewport": viewport,
            "element": f"\"{upper[0]['text'][:35]}\" -> \"{lower[0]['text'][:35]}\"".replace("\n", " "),
            "selector": f"{describe_selector(upper[1])} -> {describe_selector(lower[1])}",
            "property": "spacing-below",
            "figma_value": figma_value, "staging_value": staging_value,
            "difference": difference, "status": status, "confidence": confidence,
            "evidence": note or "Vertical gap between the two text blocks",
        })

    page_sections = section_offsets(figma_frame, matched)
    rows.extend(section_order_rows(page_sections, staging_url, viewport))
    rows.extend(unexpected_content_rows(texts, elements, matched, page_sections, staging_url, viewport))
    rows.extend(visual_diff_rows(figma_png, staging, page_sections, staging_url, viewport))

    for name, counts in sorted(sections.items(), key=lambda item: item[1]["y"]):
        if counts["matched"] == counts["total"]:
            status = "PASS"
        elif counts["matched"] == 0 and counts["total"] >= 2:
            status = "WARNING"
        else:
            status = "INFO"
        rows.append({
            "page": staging_url, "figma_node": f"section: {name}", "viewport": viewport,
            "element": name, "selector": "", "property": "section_presence",
            "figma_value": f"{counts['total']} text layers",
            "staging_value": f"{counts['matched']} found visible",
            "difference": "", "status": status, "confidence": "",
            "evidence": "Section possibly missing on staging" if status == "WARNING" else "",
        })

    return rows


# ==========================================
# REPORT
# ==========================================

def save_report(rows):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(REPORT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES, restval="")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nFigma comparison report saved: {REPORT_FILE}")
    return REPORT_FILE


def error_row(staging_url, figma_node, viewport, message):
    return {
        "page": staging_url, "figma_node": figma_node, "viewport": viewport,
        "element": "", "selector": "", "property": "audit",
        "figma_value": "", "staging_value": "", "difference": "",
        "status": "ERROR", "confidence": "", "evidence": message,
    }


def default_viewport_height(width):
    if width < TABLET_MIN_WIDTH:
        return 844
    if width < DESKTOP_MIN_WIDTH:
        return 1024
    return DEFAULT_VIEWPORT_HEIGHT


def device_for_width(width):
    if width < TABLET_MIN_WIDTH:
        return "mobile"
    if width < DESKTOP_MIN_WIDTH:
        return "tablet"
    return "desktop"


def run_comparison(figma_url, staging_url, viewport_width=None,
                   viewport_height=None, refresh=False):
    try:
        file_key, node_id = parse_figma_url(figma_url)
        figma_frame, figma_png = fetch_figma(file_key, node_id, refresh=refresh)
    except FigmaUnavailable as exc:
        return [error_row(staging_url, figma_url, "", f"Figma data unavailable (automation problem): {exc}")]

    # The browser width follows the Figma frame, so a 390px mobile frame is
    # compared against the page rendered at 390px.
    frame_box = figma_frame.get("absoluteBoundingBox") or {}
    width = viewport_width or round(frame_box.get("width", 1920))
    viewport_height = viewport_height or default_viewport_height(width)
    viewport = f"{width}x{viewport_height}"
    print(f"Figma frame   : {figma_frame.get('name', node_id)} "
          f"({frame_box.get('width', '?')} x {frame_box.get('height', '?')})")
    print(f"Viewport      : {viewport}")

    try:
        staging = capture_staging(staging_url, width, viewport_height)
    except Exception as exc:
        return [error_row(staging_url, node_id, viewport, f"Staging page could not be inspected (automation problem): {exc}")]

    return compare(figma_frame, figma_png, staging, staging_url, viewport)


def load_targets(config_path, project_name=None):
    """Figma frame / staging page pairs for one project in the config file."""
    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)
    project_name = project_name or config.get("default_project")
    projects = config.get("projects", {})
    if project_name not in projects:
        raise KeyError(f"project '{project_name}' not found; available: {', '.join(projects) or 'none'}")
    project = projects[project_name]
    base_url = project["staging_base_url"].rstrip("/")
    figma_file_url = project["figma_file_url"].split("?")[0]
    targets = []
    for page in project["pages"]:
        # "frames": {"desktop": node, "tablet": node, "mobile": node}; "node" = desktop only.
        frames = page.get("frames") or {"desktop": page["node"]}
        for device, node in frames.items():
            targets.append({
                "name": f"{page['name']} ({device})",
                "page_name": page["name"],
                "device": device,
                "node": node.replace("-", ":"),
                "figma_url": f"{figma_file_url}?node-id={node.replace(':', '-')}",
                "staging_url": base_url + page["path"],
            })
    if not targets:
        raise ValueError(f"project '{project_name}' has no pages")
    return project_name, figma_file_url, targets


def frame_name_matches(frame_name, page_name):
    words = lambda value: re.findall(r"[a-z0-9]+", value.lower())
    frame_words, page_words = words(frame_name), words(page_name)
    if not page_words or len(frame_words) < len(page_words):
        return False
    # Page name must appear as whole words, e.g. "Home - Mobile" / "Mobile Home" for "Home".
    return any(
        frame_words[start:start + len(page_words)] == page_words
        for start in range(len(frame_words) - len(page_words) + 1)
    )


def discover_device_frames(file_listing, targets):
    """
    Mobile/tablet page designs in the Figma file that the config does not list:
    page-sized frames narrower than desktop whose name contains a configured page name.
    """
    configured = {target["node"] for target in targets}
    pages = {}
    for target in targets:
        pages.setdefault(target["page_name"], target)

    found = []
    for figma_page in file_listing.get("document", {}).get("children", []):
        for frame in figma_page.get("children", []):
            box = frame.get("absoluteBoundingBox") or {}
            width, height = box.get("width", 0), box.get("height", 0)
            if frame.get("type") != "FRAME" or frame.get("id") in configured:
                continue
            if not (MOBILE_MIN_WIDTH <= width < DESKTOP_MIN_WIDTH and height >= PAGE_FRAME_MIN_HEIGHT):
                continue
            for page_name, target in pages.items():
                if frame_name_matches(frame.get("name", ""), page_name):
                    device = device_for_width(width)
                    found.append({
                        **target,
                        "name": f"{page_name} ({device}, auto-detected)",
                        "device": device,
                        "node": frame["id"],
                        "figma_url": target["figma_url"].split("?")[0] + f"?node-id={frame['id'].replace(':', '-')}",
                        "frame_label": f"{figma_page.get('name', '')} / {frame.get('name', '')} ({width:.0f}x{height:.0f})",
                    })
                    break
    return found


def fetch_file_listing(figma_file_url, refresh=False):
    """Top-level frames of every Figma page (one API call, cached)."""
    file_key = re.search(r"figma\.com/(?:design|file)/([A-Za-z0-9]+)", figma_file_url).group(1)
    path = os.path.join(OUTPUT_DIR, f"figma_{file_key}_frames.json")
    if os.path.exists(path) and not refresh:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    token = os.environ.get("FIGMA_TOKEN", "").strip()
    if not token:
        raise FigmaUnavailable("FIGMA_TOKEN is not set; cannot scan the file for mobile/tablet frames")
    listing = figma_get(f"/files/{file_key}?depth=2", token)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(listing, file)
    return listing


def use_output_dir(path):
    # Each project gets its own folder so one project's run never overwrites another's.
    global OUTPUT_DIR, REPORT_FILE
    OUTPUT_DIR = path
    REPORT_FILE = os.path.join(OUTPUT_DIR, "element_comparison.csv")


def main():
    print("\n" + "=" * 70)
    print("PHASE 7 - FIGMA VS STAGING")
    print("=" * 70)

    parser = argparse.ArgumentParser(description="Compare a Figma frame with its staging page")
    parser.add_argument("--project", help=f"Project in {CONFIG_FILE} (default: its default_project)")
    parser.add_argument("--config", default=CONFIG_FILE, help="Page-mapping config file")
    parser.add_argument("--figma-url", help="Single Figma frame URL (with node-id) instead of a configured project")
    parser.add_argument("--staging-url", help="Staging page URL for --figma-url")
    parser.add_argument("--width", type=int, help="Viewport width (default: Figma frame width)")
    parser.add_argument("--height", type=int, help="Viewport height (default: by device - 844 mobile, 1024 tablet, 1080 desktop)")
    parser.add_argument("--refresh", action="store_true", help="Re-download Figma data instead of using the cache")
    args = parser.parse_args()

    if args.figma_url or args.staging_url:
        if not (args.figma_url and args.staging_url):
            parser.error("--figma-url and --staging-url must be given together")
        targets = [{"name": "custom", "figma_url": args.figma_url, "staging_url": args.staging_url}]
    else:
        try:
            project_name, figma_file_url, targets = load_targets(args.config, args.project)
        except (OSError, ValueError, KeyError) as exc:
            parser.error(f"Could not read pages from {args.config}: {exc}")
        use_output_dir(os.path.join("results", "figma_comparison", project_name))
        print(f"Project       : {project_name} ({len(targets)} configured frames)")
        print(f"Output folder : {OUTPUT_DIR}")

        # Any mobile/tablet design for a configured page is checked too, even
        # when nobody has added it to the config yet.
        try:
            discovered = discover_device_frames(fetch_file_listing(figma_file_url, args.refresh), targets)
        except FigmaUnavailable as exc:
            discovered = []
            print(f"Device frames : not scanned ({exc})")
        else:
            if discovered:
                for target in discovered:
                    print(f"Device frames : auto-detected {target['frame_label']} -> {target['staging_url']}")
                print("                Add them under \"frames\" in the config to make the mapping explicit.")
            else:
                configured_devices = sorted({target["device"] for target in targets})
                print(f"Device frames : no unlisted mobile/tablet page designs in the Figma file "
                      f"(configured: {', '.join(configured_devices)})")
        targets += discovered

    statuses = ["PASS", "WARNING", "INFO", "ERROR"]
    rows = []
    per_page = []
    for number, target in enumerate(targets, start=1):
        print(f"\n[{number}/{len(targets)}] {target['name']}")
        print(f"Figma URL     : {target['figma_url']}")
        print(f"Staging URL   : {target['staging_url']}")
        page_rows = run_comparison(target["figma_url"], target["staging_url"], args.width, args.height, args.refresh)
        rows.extend(page_rows)
        per_page.append((target, page_rows))

    save_report(rows)

    print("\nFIGMA VS STAGING SUMMARY")
    print("=" * 70)
    print(f"{'Page':<40}" + "".join(f"{status:>9}" for status in statuses))
    for target, page_rows in per_page:
        counts = [sum(row["status"] == status for row in page_rows) for status in statuses]
        print(f"{target['name']:<40}" + "".join(f"{count:>9}" for count in counts))
    totals = [sum(row["status"] == status for row in rows) for status in statuses]
    print(f"{'TOTAL':<40}" + "".join(f"{count:>9}" for count in totals))
    for row in rows:
        if row["status"] == "ERROR":
            print(f"\nERROR {row['page']}: {row['evidence']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
