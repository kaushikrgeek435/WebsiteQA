from playwright.sync_api import sync_playwright
import csv
import os

from config import REPORTS_DIR, SITE_URL
from urllib.parse import urljoin, urlparse


# ============================================================
# CONFIGURATION
# ============================================================

TEST_URL = SITE_URL


# ============================================================
# FILE / RESOURCE EXTENSIONS TO IGNORE
# ============================================================

IGNORED_EXTENSIONS = (
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
    ".eot",
)


# ============================================================
# CHECK WHETHER LINK IS VALID FOR TESTING
# ============================================================

def is_testable_link(href):

    if not href:
        return False

    href = href.strip()

    lower_href = href.lower()

    # Ignore special links
    if lower_href.startswith("#"):
        return False

    if lower_href.startswith("mailto:"):
        return False

    if lower_href.startswith("tel:"):
        return False

    if lower_href.startswith("javascript:"):
        return False

    if lower_href.startswith("data:"):
        return False

    # Ignore resource/file links
    parsed = urlparse(lower_href)

    path = parsed.path

    if path.endswith(IGNORED_EXTENSIONS):
        return False

    return True


# ============================================================
# CHECK WHETHER URL IS EXTERNAL
# ============================================================

def is_external_url(base_url, target_url):

    base_domain = urlparse(base_url).netloc.lower()

    target_domain = urlparse(target_url).netloc.lower()

    if not target_domain:
        return False

    return target_domain != base_domain


# ============================================================
# CHECK EXTERNAL LINKS
# ============================================================

def check_external_links(url):

    results = []

    print("=" * 60)
    print("PHASE 5E - EXTERNAL LINK CHECK")
    print("=" * 60)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        print(f"\nOpening: {url}")

        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

        except Exception as e:

            print(
                f"Page load warning: {e}"
            )

        page.wait_for_timeout(3000)

        # ----------------------------------------------------
        # FIND LINKS
        # ----------------------------------------------------

        links = page.locator("a[href]")

        total_links = links.count()

        print(
            f"\nTotal links found: {total_links}"
        )

        seen_urls = set()

        # ----------------------------------------------------
        # CHECK EACH LINK
        # ----------------------------------------------------

        for i in range(total_links):

            try:

                link = links.nth(i)

                href = link.get_attribute(
                    "href"
                )

                if not is_testable_link(href):
                    continue

                absolute_url = urljoin(
                    url,
                    href
                )

                # Only HTTP/HTTPS
                parsed = urlparse(
                    absolute_url
                )

                if parsed.scheme not in [
                    "http",
                    "https"
                ]:
                    continue

                # Only external URLs
                if not is_external_url(
                    url,
                    absolute_url
                ):
                    continue

                # Remove fragment
                clean_url = (
                    f"{parsed.scheme}://"
                    f"{parsed.netloc}"
                    f"{parsed.path}"
                )

                if parsed.query:
                    clean_url += f"?{parsed.query}"

                # Avoid duplicates
                if clean_url in seen_urls:
                    continue

                seen_urls.add(clean_url)

                # ------------------------------------------------
                # LINK TEXT
                # ------------------------------------------------

                try:

                    link_text = (
                        link.inner_text()
                        .strip()
                    )

                except Exception:

                    link_text = ""

                if not link_text:

                    link_text = (
                        link.get_attribute(
                            "aria-label"
                        )
                        or link.get_attribute(
                            "title"
                        )
                        or "(no text)"
                    )

                # ------------------------------------------------
                # TARGET ATTRIBUTE
                # ------------------------------------------------

                target = (
                    link.get_attribute(
                        "target"
                    )
                    or ""
                )

                target = target.strip()

                # ------------------------------------------------
                # REL ATTRIBUTE
                # ------------------------------------------------

                rel = (
                    link.get_attribute(
                        "rel"
                    )
                    or ""
                ).strip()

                # ------------------------------------------------
                # HTTP CHECK
                # ------------------------------------------------

                print(
                    f"\nChecking: {clean_url}"
                )

                try:

                    response = page.request.get(
                        clean_url,
                        timeout=30000
                    )

                    status = response.status

                    # ------------------------------------------------
                    # RESULT
                    # ------------------------------------------------

                    if 200 <= status < 300:

                        http_result = "PASS"

                    elif 300 <= status < 400:

                        http_result = "REDIRECT"

                    elif 400 <= status < 500:

                        http_result = "FAIL - 4xx"

                    elif status >= 500:

                        http_result = "FAIL - 5xx"

                    else:

                        http_result = "UNKNOWN"

                except Exception as e:

                    status = ""

                    http_result = "ERROR"

                    print(
                        f"Request error: {e}"
                    )

                # ------------------------------------------------
                # TARGET CHECK
                # ------------------------------------------------

                if target.lower() == "_blank":

                    target_result = "PASS"

                else:

                    target_result = (
                        "WARNING - Missing _blank"
                    )

                # ------------------------------------------------
                # OVERALL RESULT
                # ------------------------------------------------

                if http_result.startswith("FAIL"):

                    overall_result = http_result

                elif http_result == "ERROR":

                    overall_result = "ERROR"

                elif target_result.startswith(
                    "WARNING"
                ):

                    overall_result = (
                        "WARNING - Missing _blank"
                    )

                else:

                    overall_result = "PASS"

                # ------------------------------------------------
                # PRINT RESULT
                # ------------------------------------------------

                print(
                    f"Text: {link_text[:50]}"
                )

                print(
                    f"Status: {status}"
                )

                print(
                    f"Target: "
                    f"{target if target else '(none)'}"
                )

                print(
                    f"Result: {overall_result}"
                )

                # ------------------------------------------------
                # SAVE RESULT
                # ------------------------------------------------

                results.append(
                    {
                        "page": url,
                        "link_text": link_text,
                        "url": clean_url,
                        "status": status,
                        "target": target,
                        "rel": rel,
                        "http_result": http_result,
                        "target_result": target_result,
                        "result": overall_result,
                    }
                )

            except Exception as e:

                print(
                    f"Link processing error: {e}"
                )

                results.append(
                    {
                        "page": url,
                        "link_text": "",
                        "url": "",
                        "status": "",
                        "target": "",
                        "rel": "",
                        "http_result": "",
                        "target_result": "",
                        "result": "ERROR",
                    }
                )

        browser.close()

    return results


# ============================================================
# SAVE REPORT
# ============================================================

def save_external_link_report(results):

    os.makedirs(
        REPORTS_DIR,
        exist_ok=True
    )

    report_file = (
        os.path.join(REPORTS_DIR, "external_link_report.csv")
    )

    with open(
        report_file,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "page",
                "link_text",
                "url",
                "status",
                "target",
                "rel",
                "http_result",
                "target_result",
                "result",
            ]
        )

        writer.writeheader()

        writer.writerows(results)

    print(
        f"\nExternal link report:"
        f"\n{report_file}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    results = check_external_links(
        TEST_URL
    )

    save_external_link_report(
        results
    )

    print("\n" + "=" * 60)
    print("PHASE 5E TEST SUMMARY")
    print("=" * 60)

    total = len(results)

    passed = sum(
        1
        for r in results
        if r["result"] == "PASS"
    )

    warnings = sum(
        1
        for r in results
        if r["result"].startswith(
            "WARNING"
        )
    )

    failures = sum(
        1
        for r in results
        if r["result"].startswith(
            "FAIL"
        )
    )

    errors = sum(
        1
        for r in results
        if r["result"] == "ERROR"
    )

    redirects = sum(
        1
        for r in results
        if r["http_result"] == "REDIRECT"
    )

    print(
        f"External links checked: {total}"
    )

    print(
        f"Passed: {passed}"
    )

    print(
        f"Warnings: {warnings}"
    )

    print(
        f"Failures: {failures}"
    )

    print(
        f"Errors: {errors}"
    )

    print(
        f"Redirects: {redirects}"
    )

    print("\nDone!")