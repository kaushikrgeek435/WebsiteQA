import csv
import os
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from config import SITE_URL, PAGES_DIR, REPORTS_DIR


# ============================================================
# SETTINGS
# ============================================================

START_URL = SITE_URL

MAX_PAGES = 500

RESULTS_DIR = PAGES_DIR

ALL_PAGES_FILE = os.path.join(
    RESULTS_DIR,
    "discovered_pages.txt"
)

QA_PAGES_FILE = os.path.join(
    RESULTS_DIR,
    "qa_pages.txt"
)

BLOG_PAGES_FILE = os.path.join(
    RESULTS_DIR,
    "blog_pages.txt"
)

CRAWL_REPORT_FILE = os.path.join(
    REPORTS_DIR,
    "crawl_report.csv"
)

FAILED_PAGES_FILE = os.path.join(
    RESULTS_DIR,
    "failed_pages.txt"
)


# ============================================================
# APPROVED QA PAGES
# ============================================================
#
# These are the main Figma/design pages.
#
# IMPORTANT:
# The website uses:
#
# /eclipse-roofing/
#
# as the base path.
#
# Therefore the paths below INCLUDE /eclipse-roofing.
#
# ============================================================

QA_PAGE_PATHS = {
    "/eclipse-roofing",
    "/eclipse-roofing/roof-installation",
    "/eclipse-roofing/services/metal-roofing",
    "/eclipse-roofing/services/asphalt-roofing-manheim-pa",
    "/eclipse-roofing/services/cedar-shingle-roofing-manheim-pa",
    "/eclipse-roofing/services/rubber-roofing",
    "/eclipse-roofing/about-us",
    "/eclipse-roofing/portfolio",
    "/eclipse-roofing/reviews",
    "/eclipse-roofing/blog",
    "/eclipse-roofing/contact-roofing-contractor",
    "/eclipse-roofing/get-a-quote",
    "/eclipse-roofing/service-area",
    # Approved blog detail page (also listed in blog_pages.txt)
    "/eclipse-roofing/roof-installation-in-denver-pa-what-homeowners-should-know",
}


# ============================================================
# PATHS THAT ARE NEVER BLOG ARTICLES
# ============================================================

NOT_BLOG_PATHS = {
    "/eclipse-roofing/",
    "/eclipse-roofing/roof-installation",
    "/eclipse-roofing/services/metal-roofing",
    "/eclipse-roofing/services/asphalt-roofing-manheim-pa",
    "/eclipse-roofing/services/cedar-shingle-roofing-manheim-pa",
    "/eclipse-roofing/services/rubber-roofing",
    "/eclipse-roofing/about-us",
    "/eclipse-roofing/portfolio",
    "/eclipse-roofing/reviews",
    "/eclipse-roofing/blog",
    "/eclipse-roofing/contact-roofing-contractor",
    "/eclipse-roofing/get-a-quote",
    "/eclipse-roofing/service-area",
    "/eclipse-roofing/privacy-policy",
    "/eclipse-roofing/terms-of-service",
    "/eclipse-roofing/cookies",
}


# ============================================================
# FILE TYPES TO IGNORE
# ============================================================

IGNORED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".bmp",
    ".avif",

    ".pdf",
    ".zip",
    ".rar",
    ".7z",

    ".mp3",
    ".mp4",
    ".webm",
    ".mov",
    ".avi",

    ".css",
    ".js",
    ".json",
    ".xml",
    ".txt",

    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
}


# ============================================================
# URL NORMALIZATION
# ============================================================

def normalize_url(url):

    url = urldefrag(url)[0]

    parsed = urlparse(url)

    path = parsed.path

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    parsed = parsed._replace(
        path=path,
        fragment=""
    )

    return parsed.geturl()


def get_path(url):

    path = urlparse(url).path

    if not path:
        return "/"

    if path.endswith("/") and path != "/":
        path = path.rstrip("/")

    return path


# ============================================================
# LINK FILTERING
# ============================================================

def is_special_link(url):

    lower_url = url.lower()

    return lower_url.startswith(
        (
            "mailto:",
            "tel:",
            "javascript:",
            "data:",
            "sms:",
            "whatsapp:"
        )
    )


def is_file_url(url):

    path = urlparse(url).path.lower()

    _, extension = os.path.splitext(path)

    return extension in IGNORED_EXTENSIONS


def is_same_domain(url, base_domain):

    try:

        domain = urlparse(url).netloc.lower()

        return domain == base_domain.lower()

    except Exception:

        return False


def is_valid_page_url(url, base_domain):

    if not url:
        return False

    if is_special_link(url):
        return False

    if is_file_url(url):
        return False

    if not is_same_domain(
        url,
        base_domain
    ):
        return False

    return True


# ============================================================
# QA PAGE CHECK
# ============================================================

def is_qa_page(url):
    """
    Return True only for the exact approved Figma QA URLs.

    Query/filter URLs such as:

        /portfolio?term=8
        /portfolio?term=9

    are NOT separate QA pages.
    """

    parsed = urlparse(url)

    # --------------------------------------------------------
    # Ignore query-string URLs
    # --------------------------------------------------------

    if parsed.query:
        return False

    # --------------------------------------------------------
    # Get normalized path
    # --------------------------------------------------------

    path = parsed.path.rstrip("/")

    if not path:
        path = "/"

    return path in QA_PAGE_PATHS
# ============================================================
# BLOG ARTICLE DETECTION
# ============================================================

def is_blog_detail_page(page, url):

    """
    Detect ONLY actual individual WordPress blog posts.

    We intentionally DO NOT use generic JSON-LD Article detection
    because this website places structured data on many pages.

    Instead we look for WordPress "single post" indicators.
    """

    path = get_path(url).lower()

    # --------------------------------------------------------
    # Never classify known QA pages as blog articles
    # --------------------------------------------------------

    if path in NOT_BLOG_PATHS:
        return False

    # --------------------------------------------------------
    # Never classify these WordPress archive pages as articles
    # --------------------------------------------------------

    excluded_prefixes = (
        "/eclipse-roofing/category/",
        "/eclipse-roofing/author/",
        "/eclipse-roofing/tag/",
        "/eclipse-roofing/page/",
    )

    for prefix in excluded_prefixes:

        if path.startswith(prefix):
            return False

    # --------------------------------------------------------
    # BEST METHOD:
    # Check WordPress body classes.
    #
    # A normal WordPress single blog post commonly has:
    #
    # body.single-post
    #
    # --------------------------------------------------------

    try:

        body_class = page.locator(
            "body"
        ).get_attribute(
            "class"
        )

        if body_class:

            classes = body_class.lower().split()

            if "single-post" in classes:
                return True

            if "single-format-standard" in classes:
                return True

    except Exception:
        pass

    # --------------------------------------------------------
    # Check for WordPress post body structure.
    #
    # We require MULTIPLE indicators instead of one generic
    # element, preventing false positives.
    # --------------------------------------------------------

    try:

        has_entry_content = (
            page.locator(
                ".entry-content"
            ).count() > 0
        )

        has_post_meta = (
            page.locator(
                ".entry-meta, .post-meta, .post-date"
            ).count() > 0
        )

        has_time = (
            page.locator(
                "article time, article [datetime]"
            ).count() > 0
        )

        has_article = (
            page.locator(
                "article"
            ).count() > 0
        )

        # Need at least article + content + date/meta
        if (
            has_article
            and has_entry_content
            and (
                has_post_meta
                or has_time
            )
        ):
            return True

    except Exception:
        pass

    # --------------------------------------------------------
    # Check common Elementor/WordPress single-post classes
    # --------------------------------------------------------

    single_post_selectors = [
        ".single-post",
        ".single-post-content",
        ".blog-single",
        ".blog-post-single",
        ".single-blog-post",
    ]

    for selector in single_post_selectors:

        try:

            if page.locator(
                selector
            ).count() > 0:

                # Need article/date evidence too
                has_date = (
                    page.locator(
                        "time, [datetime], "
                        ".entry-date, .post-date"
                    ).count() > 0
                )

                if has_date:
                    return True

        except Exception:
            pass

    return False


# ============================================================
# CRAWLER
# ============================================================

def crawl_website(
    start_url,
    max_pages=MAX_PAGES
):

    start_url = normalize_url(
        start_url
    )

    base_domain = urlparse(
        start_url
    ).netloc.lower()

    queue = deque()

    queue.append(
        start_url
    )

    visited = set()

    all_pages = []

    blog_pages = []

    failed_pages = []

    crawl_records = []

    print("=" * 70)
    print("WEBSITE CRAWLER")
    print("=" * 70)

    print(
        f"\nStarting URL:"
    )

    print(start_url)

    print(
        f"\nMaximum pages:"
    )

    print(max_pages)

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        page = context.new_page()

        while queue and len(all_pages) < max_pages:

            current_url = queue.popleft()

            current_url = normalize_url(
                current_url
            )

            if current_url in visited:
                continue

            visited.add(
                current_url
            )

            print(
                f"\n[{len(all_pages) + 1}] "
                f"{current_url}"
            )

            status = ""

            result = ""

            error_message = ""

            try:

                response = page.goto(
                    current_url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                # ------------------------------------------------
                # STATUS
                # ------------------------------------------------

                if response:

                    status = response.status

                    if 200 <= status < 300:
                        result = "PASS"

                    elif 300 <= status < 400:
                        result = "REDIRECT"

                    elif 400 <= status < 500:
                        result = "FAIL - 4xx"

                    elif 500 <= status < 600:
                        result = "FAIL - 5xx"

                    else:
                        result = "UNKNOWN"

                else:

                    result = "NO RESPONSE"

                # ------------------------------------------------
                # CONTENT TYPE
                # ------------------------------------------------

                content_type = ""

                if response:

                    content_type = (
                        response.headers.get(
                            "content-type",
                            ""
                        ).lower()
                    )

                is_html_page = (
                    result in {
                        "PASS",
                        "REDIRECT"
                    }
                    and (
                        not content_type
                        or "text/html" in content_type
                    )
                )

                # ------------------------------------------------
                # PROCESS HTML PAGE
                # ------------------------------------------------

                if is_html_page:

                    # Add to ALL pages
                    all_pages.append(
                        current_url
                    )

                    # --------------------------------------------
                    # BLOG DETECTION
                    # --------------------------------------------

                    if is_blog_detail_page(
                        page,
                        current_url
                    ):

                        blog_pages.append(
                            current_url
                        )

                        print(
                            "   BLOG ARTICLE DETECTED"
                        )

                    # --------------------------------------------
                    # COLLECT LINKS
                    # --------------------------------------------

                    try:

                        hrefs = page.locator(
                            "a[href]"
                        ).evaluate_all(
                            """
                            elements => elements.map(
                                element => element.href
                            )
                            """
                        )

                    except Exception:

                        hrefs = []

                    # --------------------------------------------
                    # ADD LINKS TO QUEUE
                    # --------------------------------------------

                    for href in hrefs:

                        try:

                            absolute_url = urljoin(
                                current_url,
                                href
                            )

                            absolute_url = normalize_url(
                                absolute_url
                            )

                            if not is_valid_page_url(
                                absolute_url,
                                base_domain
                            ):
                                continue

                            if absolute_url in visited:
                                continue

                            if absolute_url in queue:
                                continue

                            queue.append(
                                absolute_url
                            )

                        except Exception:

                            continue

                else:

                    failed_pages.append(
                        current_url
                    )

                # ------------------------------------------------
                # RECORD
                # ------------------------------------------------

                crawl_records.append({

                    "url": current_url,

                    "status": status,

                    "result": result,

                    "error": error_message

                })

                print(
                    f"   Status: {status} | "
                    f"{result}"
                )

            except PlaywrightTimeoutError:

                result = "TIMEOUT"

                error_message = (
                    "Page load timeout"
                )

                failed_pages.append(
                    current_url
                )

                crawl_records.append({

                    "url": current_url,

                    "status": "",

                    "result": result,

                    "error": error_message

                })

                print(
                    "   TIMEOUT"
                )

            except Exception as error:

                result = "ERROR"

                error_message = str(
                    error
                )

                failed_pages.append(
                    current_url
                )

                crawl_records.append({

                    "url": current_url,

                    "status": "",

                    "result": result,

                    "error": error_message

                })

                print(
                    f"   ERROR: "
                    f"{error_message[:150]}"
                )

        browser.close()

    # ============================================================
    # REMOVE DUPLICATES
    # ============================================================

    all_pages = list(
        dict.fromkeys(
            all_pages
        )
    )

    blog_pages = list(
        dict.fromkeys(
            blog_pages
        )
    )

    failed_pages = list(
        dict.fromkeys(
            failed_pages
        )
    )

    # ============================================================
    # QA PAGE LIST
    # ============================================================

    qa_pages = [

        url

        for url in all_pages

        if is_qa_page(url)

    ]

    qa_pages = list(
        dict.fromkeys(
            qa_pages
        )
    )

    # ============================================================
    # SAVE DIRECTORY
    # ============================================================

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    os.makedirs(
        os.path.dirname(CRAWL_REPORT_FILE),
        exist_ok=True
    )

    # ============================================================
    # SAVE ALL PAGES
    # ============================================================

    with open(
        ALL_PAGES_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        for url in all_pages:

            file.write(
                url + "\n"
            )

    # ============================================================
    # SAVE QA PAGES
    # ============================================================

    with open(
        QA_PAGES_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        for url in qa_pages:

            file.write(
                url + "\n"
            )

    # ============================================================
    # SAVE BLOG PAGES
    # ============================================================

    with open(
        BLOG_PAGES_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        for url in blog_pages:

            file.write(
                url + "\n"
            )

    # ============================================================
    # SAVE FAILED PAGES
    # ============================================================

    with open(
        FAILED_PAGES_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        for url in failed_pages:

            file.write(
                url + "\n"
            )

    # ============================================================
    # SAVE CSV
    # ============================================================

    with open(
        CRAWL_REPORT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        fieldnames = [
            "url",
            "status",
            "result",
            "error"
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(
            crawl_records
        )

    # ============================================================
    # SUMMARY
    # ============================================================

    print("\n" + "=" * 70)
    print("CRAWL COMPLETED")
    print("=" * 70)

    print(
        f"\nAll discovered pages : "
        f"{len(all_pages)}"
    )

    print(
        f"QA pages             : "
        f"{len(qa_pages)}"
    )

    print(
        f"Blog detail pages    : "
        f"{len(blog_pages)}"
    )

    print(
        f"Failed pages         : "
        f"{len(failed_pages)}"
    )

    print("\nFiles created:")

    print(
        f"  {ALL_PAGES_FILE}"
    )

    print(
        f"  {QA_PAGES_FILE}"
    )

    print(
        f"  {BLOG_PAGES_FILE}"
    )

    print(
        f"  {CRAWL_REPORT_FILE}"
    )

    print(
        f"  {FAILED_PAGES_FILE}"
    )

    return {

        "all_pages": all_pages,

        "qa_pages": qa_pages,

        "blog_pages": blog_pages,

        "failed_pages": failed_pages

    }


# ============================================================
# MAIN
# ============================================================

def main():

    crawl_website(
        START_URL,
        MAX_PAGES
    )


if __name__ == "__main__":

    main()