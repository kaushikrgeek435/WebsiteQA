import csv
import os
import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import config


# ============================================================
# SETTINGS
# ============================================================

QA_PAGES_FILE = config.QA_PAGES_FILE

RESULTS_DIR = config.REPORTS_DIR

REPORT_FILE = os.path.join(
    RESULTS_DIR,
    "slider_report.csv"
)


# ============================================================
# SLIDER SELECTORS
# ============================================================

SLIDER_CONTAINER_SELECTORS = [
    ".testimonials-slider",
    ".testimonials-swiper",
    ".swiper",
    ".swiper-container",
    ".slick-slider",
    ".splide",
    ".owl-carousel",
    ".carousel",
    "[class*='slider']",
    "[class*='carousel']",
]


# ============================================================
# SLIDE SELECTORS
# ============================================================

SLIDE_SELECTORS = [
    ".testimonials-item",
    ".swiper-slide",
    ".slick-slide",
    ".splide__slide",
    ".owl-item",
    ".carousel-item",
    "[class*='slide']",
]


# ============================================================
# ACTIVE SLIDE SELECTORS
# ============================================================

ACTIVE_SLIDE_SELECTORS = [
    ".swiper-slide-active",
    ".slick-current",
    ".splide__slide.is-active",
    ".owl-item.active",
    ".carousel-item.active",
    "[aria-current='true']",
    "[aria-selected='true']",
]


# ============================================================
# NEXT BUTTON SELECTORS
# ============================================================

NEXT_BUTTON_SELECTORS = [
    ".swiper-nav-btn-next",
    ".swiper-button-next",
    ".slick-next",
    ".splide__arrow--next",
    ".owl-next",
    ".carousel-control-next",
    "[aria-label*='next' i]",
    "[title*='next' i]",
    "[class*='next' i]",
]


# ============================================================
# PREVIOUS BUTTON SELECTORS
# ============================================================

PREVIOUS_BUTTON_SELECTORS = [
    ".swiper-nav-btn-prev",
    ".swiper-button-prev",
    ".slick-prev",
    ".splide__arrow--prev",
    ".owl-prev",
    ".carousel-control-prev",
    "[aria-label*='prev' i]",
    "[aria-label*='previous' i]",
    "[title*='prev' i]",
    "[title*='previous' i]",
    "[class*='prev' i]",
]


# ============================================================
# DOT / PAGINATION SELECTORS
# ============================================================

DOT_SELECTORS = [
    ".swiper-pagination-bullet",
    ".slick-dots button",
    ".splide__pagination__page",
    ".owl-dots button",
    ".carousel-indicators button",
]


# ============================================================
# READ QA PAGES
# ============================================================

def load_qa_pages():

    if not os.path.exists(QA_PAGES_FILE):

        print(
            f"ERROR: {QA_PAGES_FILE} not found."
        )

        print(
            "Run crawler.py first."
        )

        return []

    with open(
        QA_PAGES_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        pages = [
            line.strip()
            for line in file
            if line.strip()
        ]

    # Remove duplicates
    pages = list(
        dict.fromkeys(pages)
    )

    return pages


# ============================================================
# IDENTIFY SLIDER TYPE
# ============================================================

def identify_slider_type(container):

    classes = (
        container.get_attribute("class")
        or ""
    ).lower()

    try:

        descendant_classes = " ".join(
            container.locator(
                ".swiper, .swiper-container, .swiper-slide"
            ).evaluate_all(
                "elements => elements.map(el => el.className)"
            )
        ).lower()

    except Exception:

        descendant_classes = ""

    classes = f"{classes} {descendant_classes}"

    if "swiper" in classes:
        return "Swiper"

    if "slick" in classes:
        return "Slick"

    if "splide" in classes:
        return "Splide"

    if "owl-" in classes:
        return "Owl Carousel"

    if "carousel" in classes:
        return "Bootstrap/Generic Carousel"

    if "slider" in classes:
        return "Generic Slider"

    return "Generic Carousel"


# ============================================================
# FIND SLIDES
# ============================================================

def find_slides(container):

    for selector in SLIDE_SELECTORS:

        try:

            locator = container.locator(
                selector
            )

            count = locator.count()

            if count >= 2:

                visible_count = sum(
                    locator.nth(index).is_visible()
                    for index in range(count)
                )

                if visible_count >= 2:

                    return locator

        except Exception:

            continue

    # --------------------------------------------------------
    # Generic fallback:
    # Look for direct children.
    # --------------------------------------------------------

    try:

        children = container.locator(
            ":scope > *"
        )

        count = children.count()

        if count >= 2:

            return children

    except Exception:
        pass

    return None


# ============================================================
# GET ACTIVE SLIDE IDENTITY
# ============================================================

def get_active_slide(container):

    for selector in ACTIVE_SLIDE_SELECTORS:

        try:

            locator = container.locator(
                selector
            )

            if locator.count() > 0:

                active = locator.first

                # Try useful identifying attributes
                for attribute in [
                    "data-swiper-slide-index",
                    "data-index",
                    "aria-label",
                    "id"
                ]:

                    value = active.get_attribute(
                        attribute
                    )

                    if value:
                        return f"{attribute}={value}"

                # Use text as fallback
                try:

                    text = active.inner_text(
                        timeout=1000
                    ).strip()

                    if text:

                        return (
                            "text="
                            + re.sub(
                                r"\s+",
                                " ",
                                text
                            )[:100]
                        )

                except Exception:
                    pass

                return "active-slide-found"

        except Exception:

            continue

    return None


# ============================================================
# GET VISIBLE SLIDE STATE
# ============================================================

def get_visible_slide_state(slides):

    """Return meaningful content from the cards currently on screen.

    A testimonial carousel can show several cards at once, so an active-slide
    class alone is not reliable evidence that the carousel moved.
    """

    if not slides:
        return None

    try:

        state = slides.evaluate_all(
            """
            elements => elements
                .filter(el => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        rect.width > 0 && rect.height > 0 &&
                        rect.right > 0 && rect.left < window.innerWidth &&
                        rect.bottom > 0 && rect.top < window.innerHeight;
                })
                .map(el => ({
                    index: el.getAttribute('data-swiper-slide-index') ||
                        el.getAttribute('data-index') || '',
                    text: (el.innerText || el.textContent || '')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .slice(0, 160)
                }))
                .filter(item => item.index || item.text)
            """
        )

        if state:
            return str(state)

    except Exception:
        pass

    return None


# ============================================================
# WAIT FOR A VISIBLE STATE CHANGE
# ============================================================

def state_changed_after_click(page, slides, before_state):

    for _ in range(8):

        page.wait_for_timeout(250)

        after_state = get_visible_slide_state(slides)

        if (
            before_state
            and after_state
            and before_state != after_state
        ):

            return True

    return False


# ============================================================
# GET A DEDUPLICATION FINGERPRINT
# ============================================================

def get_slide_fingerprint(slides):

    try:

        values = slides.evaluate_all(
            """
            elements => elements.map(el =>
                (el.getAttribute('data-swiper-slide-index') || '') + '|' +
                (el.innerText || el.textContent || '')
                    .replace(/\\s+/g, ' ')
                    .trim()
                    .slice(0, 100)
            )
            """
        )

        if values:
            return tuple(values)

    except Exception:
        pass

    return None


# ============================================================
# FIND CONTROL
# ============================================================

def find_control(
    container,
    selectors
):

    for selector in selectors:

        try:

            locator = container.locator(
                selector
            )

            count = locator.count()

            for index in range(count):

                button = locator.nth(index)

                if button.is_visible():

                    return button

        except Exception:

            continue

    return None


# ============================================================
# FIND PAGINATION / DOTS
# ============================================================

def find_dots(container):

    for selector in DOT_SELECTORS:

        try:

            locator = container.locator(
                selector
            )

            count = locator.count()

            if count >= 2:

                return locator

        except Exception:

            continue

    return None


# ============================================================
# SCORE A POSSIBLE DUPLICATE
# ============================================================

def candidate_score(container):

    """Prefer the wrapper that owns the component's controls."""

    score = 0

    if find_control(container, NEXT_BUTTON_SELECTORS):
        score += 2

    if find_control(container, PREVIOUS_BUTTON_SELECTORS):
        score += 2

    if find_dots(container):
        score += 1

    return score


# ============================================================
# SAFE CLICK
# ============================================================

def safe_click(
    button
):

    try:

        button.scroll_into_view_if_needed(
            timeout=3000
        )

    except Exception:
        pass

    try:

        button.click(
            timeout=5000
        )

        return True

    except Exception:

        return False


# ============================================================
# CHECK WHETHER A CONTAINER IS INTERACTIVE
# ============================================================

def is_interactive_slider(container, slides):

    try:

        if not slides or slides.count() < 2:

            return False

        return (
            find_control(container, NEXT_BUTTON_SELECTORS)
            or find_control(container, PREVIOUS_BUTTON_SELECTORS)
            or find_dots(container)
        ) is not None

    except Exception:

        return False


# ============================================================
# CHECK ONE SLIDER
# ============================================================

def check_slider(
    page,
    page_url,
    slider_index,
    container
):

    slider_type = identify_slider_type(
        container
    )

    slides = find_slides(
        container
    )

    # --------------------------------------------------------
    # Slide count
    # --------------------------------------------------------

    if slides:

        try:

            slide_count = slides.count()

        except Exception:

            slide_count = 0

    else:

        slide_count = 0

    # --------------------------------------------------------
    # Ignore things that look like sliders but don't contain
    # at least 2 slides.
    # --------------------------------------------------------

    if slide_count < 2:

        return {

            "page": page_url,

            "slider_number": slider_index,

            "slider_type": slider_type,

            "slides": slide_count,

            "next": "N/A",

            "previous": "N/A",

            "pagination": "N/A",

            "result": "INFO",

            "details": (
                "Slider-like container found, "
                "but fewer than 2 slides detected"
            )

        }

    print(
        f"   Slider {slider_index}: "
        f"{slider_type} | "
        f"{slide_count} slides"
    )

    # The page scan finishes at the top of the page. Put the carousel in the
    # viewport before taking a visible-card snapshot.
    try:

        container.scroll_into_view_if_needed(
            timeout=3000
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # NEXT
    # --------------------------------------------------------

    next_button = find_control(
        container,
        NEXT_BUTTON_SELECTORS
    )

    next_result = "NOT FOUND"

    if next_button:

        before_next = get_visible_slide_state(
            slides
        )

        if safe_click(
            next_button
        ):

            if (
                state_changed_after_click(
                    page,
                    slides,
                    before_next
                )
            ):

                next_result = "PASS"

            else:

                next_result = (
                    "ERROR - Visible content did not change"
                )

        else:

            next_result = (
                "ERROR - Next click failed"
            )

    # --------------------------------------------------------
    # PREVIOUS
    # --------------------------------------------------------

    previous_button = find_control(
        container,
        PREVIOUS_BUTTON_SELECTORS
    )

    previous_result = "NOT FOUND"

    if previous_button:

        before_previous = get_visible_slide_state(
            slides
        )

        if safe_click(
            previous_button
        ):

            if (
                state_changed_after_click(
                    page,
                    slides,
                    before_previous
                )
            ):

                previous_result = "PASS"

            else:

                previous_result = (
                    "ERROR - Visible content did not change"
                )

        else:

            previous_result = (
                "ERROR - Previous click failed"
            )

    # --------------------------------------------------------
    # PAGINATION / DOTS
    # --------------------------------------------------------

    dots = find_dots(
        container
    )

    if dots:

        try:

            dot_count = dots.count()

            # The first dot is active after the previous-arrow check. Use the
            # next dot so this is a real transition, while avoiding distant
            # dots that a responsive pagination layout may keep offscreen.
            target_dot = dots.nth(1)

            before_pagination = get_visible_slide_state(
                slides
            )

            if safe_click(target_dot):

                if state_changed_after_click(
                    page,
                    slides,
                    before_pagination
                ):

                    pagination_result = (
                        f"PASS - {dot_count} dots"
                    )

                else:

                    pagination_result = (
                        "ERROR - Visible content did not change"
                    )

            else:

                pagination_result = "ERROR - Pagination click failed"

        except Exception:

            pagination_result = "ERROR - Pagination check failed"

    else:

        pagination_result = (
            "INFO - No pagination dots detected"
        )

    # --------------------------------------------------------
    # Overall result
    # --------------------------------------------------------

    if (
        next_result.startswith("ERROR")
        or previous_result.startswith("ERROR")
        or pagination_result.startswith("ERROR")
    ):

        overall_result = "ERROR"

    elif (
        next_result == "PASS"
        and previous_result == "PASS"
        and pagination_result.startswith("PASS")
    ):

        overall_result = "PASS"

    elif (
        next_result == "NOT FOUND"
        and previous_result == "NOT FOUND"
    ):

        overall_result = "WARNING"

    else:

        overall_result = "WARNING"

    # --------------------------------------------------------
    # Details
    # --------------------------------------------------------

    details = (
        f"Slides={slide_count}; "
        f"Next={next_result}; "
        f"Previous={previous_result}; "
        f"Pagination={pagination_result}"
    )

    return {

        "page": page_url,

        "slider_number": slider_index,

        "slider_type": slider_type,

        "slides": slide_count,

        "next": next_result,

        "previous": previous_result,

        "pagination": pagination_result,

        "result": overall_result,

        "details": details

    }


# ============================================================
# CHECK ONE PAGE
# ============================================================

def check_page(
    browser,
    page_url
):

    print(
        f"\nChecking page: {page_url}"
    )

    page = browser.new_page()

    results = []

    try:

        # ----------------------------------------------------
        # Open page
        # ----------------------------------------------------

        try:

            page.goto(
                page_url,
                wait_until="domcontentloaded",
                timeout=30000
            )

        except PlaywrightTimeoutError:

            print(
                "   Page load timeout - continuing"
            )

        # Give JavaScript sliders time to initialize
        page.wait_for_timeout(
            1500
        )

        # ----------------------------------------------------
        # Scroll through page
        # This helps lazy-loaded sliders initialize.
        # ----------------------------------------------------

        try:

            page.evaluate(
                """
                async () => {
                    await new Promise(resolve => {
                        let total = 0;
                        const distance = 500;

                        const timer = setInterval(() => {
                            window.scrollBy(
                                0,
                                distance
                            );

                            total += distance;

                            if (
                                total >=
                                document.body.scrollHeight
                            ) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
                """
            )

            page.wait_for_timeout(
                1000
            )

            page.evaluate(
                "window.scrollTo(0, 0)"
            )

        except Exception:
            pass

        # ----------------------------------------------------
        # Find slider containers
        # ----------------------------------------------------

        containers = []

        seen_elements = set()

        for selector in SLIDER_CONTAINER_SELECTORS:

            try:

                locator = page.locator(
                    selector
                )

                count = locator.count()

                for index in range(count):

                    container = locator.nth(
                        index
                    )

                    try:

                        if not container.is_visible():
                            continue

                    except Exception:
                        continue

                    # ------------------------------------------------
                    # Create simple identity
                    # ------------------------------------------------

                    try:

                        identity = container.evaluate(
                            """
                            el => ({
                                tag: el.tagName,
                                id: el.id,
                                cls: el.className
                            })
                            """
                        )

                        identity = str(
                            identity
                        )

                    except Exception:

                        identity = str(
                            index
                        )

                    if identity in seen_elements:
                        continue

                    seen_elements.add(
                        identity
                    )

                    containers.append(
                        container
                    )

            except Exception:

                continue

        # ----------------------------------------------------
        # Deduplicate nested/wrapper selectors. A carousel is
        # frequently matched as its Swiper element and as one or
        # more parent elements whose class contains "slider".
        # Identical slide content means it is one component; keep
        # the wrapper that has the most relevant controls.
        # ----------------------------------------------------

        fingerprinted_containers = {}
        unique_containers = []

        for container in containers:

            slides = find_slides(container)

            if not is_interactive_slider(container, slides):

                continue

            fingerprint = get_slide_fingerprint(slides)

            if not fingerprint:

                unique_containers.append(container)

                continue

            existing = fingerprinted_containers.get(fingerprint)

            if (
                not existing
                or candidate_score(container) > candidate_score(existing)
            ):

                fingerprinted_containers[fingerprint] = container

        unique_containers.extend(
            fingerprinted_containers.values()
        )

        # ----------------------------------------------------
        # No sliders
        # ----------------------------------------------------

        if not unique_containers:

            print(
                "   No slider/carousel detected"
            )

            results.append({

                "page": page_url,

                "slider_number": 0,

                "slider_type": "None",

                "slides": 0,

                "next": "N/A",

                "previous": "N/A",

                "pagination": "N/A",

                "result": "INFO",

                "details": (
                    "No slider/carousel detected"
                )

            })

            return results

        # ----------------------------------------------------
        # Check each slider
        # ----------------------------------------------------

        print(
            f"   Sliders detected: "
            f"{len(unique_containers)}"
        )

        for index, container in enumerate(
            unique_containers,
            start=1
        ):

            try:

                result = check_slider(
                    page,
                    page_url,
                    index,
                    container
                )

                results.append(
                    result
                )

            except Exception as error:

                print(
                    f"   Slider {index} error: "
                    f"{error}"
                )

                results.append({

                    "page": page_url,

                    "slider_number": index,

                    "slider_type": "Unknown",

                    "slides": 0,

                    "next": "ERROR",

                    "previous": "ERROR",

                    "pagination": "ERROR",

                    "result": "ERROR",

                    "details": str(
                        error
                    )

                })

    except Exception as error:

        print(
            f"   Page error: {error}"
        )

        results.append({

            "page": page_url,

            "slider_number": 0,

            "slider_type": "Page Error",

            "slides": 0,

            "next": "ERROR",

            "previous": "ERROR",

            "pagination": "ERROR",

            "result": "ERROR",

            "details": str(
                error
            )

        })

    finally:

        page.close()

    return results


# ============================================================
# RUN ALL QA PAGES
# ============================================================

def check_sliders(
    pages
):

    all_results = []

    print(
        "\n" + "=" * 70
    )

    print(
        "PHASE 5F - SLIDER / CAROUSEL CHECKER"
    )

    print(
        "=" * 70
    )

    print(
        f"\nPages to check: {len(pages)}"
    )

    print(
        "Mode: QA PAGES ONLY"
    )

    print(
        f"Source: {QA_PAGES_FILE}"
    )

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True
        )

        for page_url in pages:

            results = check_page(
                browser,
                page_url
            )

            all_results.extend(
                results
            )

        browser.close()

    return all_results


# ============================================================
# SAVE REPORT
# ============================================================

def save_slider_report(
    results
):

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    with open(
        REPORT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        fieldnames = [
            "page",
            "slider_number",
            "slider_type",
            "slides",
            "next",
            "previous",
            "pagination",
            "result",
            "details"
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(
            results
        )

    print(
        f"\nSlider report saved:"
    )

    print(
        REPORT_FILE
    )


# ============================================================
# MAIN
# ============================================================

def main():

    pages = load_qa_pages()

    if not pages:

        print(
            "\nNo QA pages found."
        )

        return

    results = check_sliders(
        pages
    )

    save_slider_report(
        results
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    pass_count = sum(
        1
        for item in results
        if item["result"] == "PASS"
    )

    warning_count = sum(
        1
        for item in results
        if item["result"] == "WARNING"
    )

    error_count = sum(
        1
        for item in results
        if item["result"] == "ERROR"
    )

    info_count = sum(
        1
        for item in results
        if item["result"] == "INFO"
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "SLIDER CHECK SUMMARY"
    )

    print(
        "=" * 70
    )

    print(
        f"Total records : {len(results)}"
    )

    print(
        f"PASS          : {pass_count}"
    )

    print(
        f"WARNING       : {warning_count}"
    )

    print(
        f"ERROR         : {error_count}"
    )

    print(
        f"INFO          : {info_count}"
    )

    print(
        "\nDone!"
    )


if __name__ == "__main__":

    main()
