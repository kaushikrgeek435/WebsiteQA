from playwright.sync_api import sync_playwright
import csv
import os

from config import REPORTS_DIR, SITE_URL
from urllib.parse import urljoin, urlparse


TEST_URL = SITE_URL


def is_valid_navigation_link(href):
    """Ignore non-web links."""
    if not href:
        return False

    href = href.strip().lower()

    if href.startswith("#"):
        return False

    if href.startswith("mailto:"):
        return False

    if href.startswith("tel:"):
        return False

    if href.startswith("javascript:"):
        return False

    if href.startswith("data:"):
        return False

    return True


def check_navigation(url):
    results = []

    print("=" * 60)
    print("PHASE 5A - NAVIGATION CHECK")
    print("=" * 60)

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1440, "height": 900}
        )

        print(f"\nOpening: {url}")

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )
        except Exception as e:
            print(f"Page load warning: {e}")

        # Give JavaScript/navigation menus time to render
        page.wait_for_timeout(3000)

        # --------------------------------------------------
        # DESKTOP NAVIGATION
        # --------------------------------------------------

        print("\nFinding navigation links...")

        nav_links = page.locator(
            "header a, nav a, .menu a, .navbar a"
        )

        count = nav_links.count()

        print(f"Navigation elements found: {count}")

        seen_urls = set()

        for i in range(count):

            try:
                link = nav_links.nth(i)

                if not link.is_visible():
                    continue

                text = link.inner_text().strip()

                href = link.get_attribute("href")

                if not is_valid_navigation_link(href):
                    continue

                absolute_url = urljoin(url, href)

                parsed = urlparse(absolute_url)

                # Remove fragment
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

                # Avoid duplicate links
                if clean_url in seen_urls:
                    continue

                seen_urls.add(clean_url)

                # Check destination
                try:

                    response = page.request.get(
                        clean_url,
                        timeout=30000
                    )

                    status = response.status

                    if 200 <= status < 300:
                        result = "PASS"

                    elif 300 <= status < 400:
                        result = "REDIRECT"

                    elif 400 <= status < 500:
                        result = "FAIL - 4xx"

                    elif status >= 500:
                        result = "FAIL - 5xx"

                    else:
                        result = "UNKNOWN"

                except Exception as e:

                    status = ""
                    result = "ERROR"

                    print(
                        f"ERROR checking {clean_url}: {e}"
                    )

                print(
                    f"{result:<15} | "
                    f"{text[:30]:<30} | "
                    f"{clean_url}"
                )

                results.append(
                    {
                        "page": url,
                        "link_text": text,
                        "url": clean_url,
                        "status": status,
                        "result": result
                    }
                )

            except Exception as e:

                print(
                    f"Navigation element error: {e}"
                )

        # --------------------------------------------------
        # MOBILE MENU DETECTION
        # --------------------------------------------------

        print("\nChecking mobile menu...")

        mobile_page = browser.new_page(
            viewport={"width": 375, "height": 812}
        )

        try:
            mobile_page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )
        except Exception as e:
            print(f"Mobile page warning: {e}")

        mobile_page.wait_for_timeout(3000)

        # Common hamburger selectors
        menu_selectors = [
            "button[aria-label*='menu' i]",
            "button[class*='menu' i]",
            ".hamburger",
            ".menu-toggle",
            ".navbar-toggler",
            "[class*='hamburger' i]",
            "[class*='menu-toggle' i]"
        ]

        menu_found = False

        for selector in menu_selectors:

            try:

                menu = mobile_page.locator(selector).first

                if awaitable_is_visible(menu):
                    menu_found = True

                    print(
                        f"Mobile menu detected: {selector}"
                    )

                    try:
                        menu.click(timeout=5000)

                        mobile_page.wait_for_timeout(1000)

                        print(
                            "Mobile menu click: PASS"
                        )

                    except Exception as e:

                        print(
                            f"Mobile menu click: FAIL - {e}"
                        )

                    break

            except Exception:
                continue

        if not menu_found:

            print(
                "Mobile menu button not detected."
            )

        mobile_page.close()
        browser.close()

    return results


def awaitable_is_visible(locator):
    """Safe visibility check for Playwright locator."""
    try:
        return locator.is_visible()
    except Exception:
        return False


def save_navigation_report(results):

    os.makedirs(REPORTS_DIR, exist_ok=True)

    report_file = os.path.join(REPORTS_DIR, "navigation_report.csv")

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
                "result"
            ]
        )

        writer.writeheader()

        writer.writerows(results)

    print(
        f"\nNavigation report:"
        f"\n{report_file}"
    )


if __name__ == "__main__":

    results = check_navigation(TEST_URL)

    save_navigation_report(results)

    print("\n" + "=" * 60)
    print("PHASE 5A TEST SUMMARY")
    print("=" * 60)

    total = len(results)

    passed = sum(
        1 for r in results
        if r["result"] == "PASS"
    )

    redirects = sum(
        1 for r in results
        if r["result"] == "REDIRECT"
    )

    failures = sum(
        1 for r in results
        if "FAIL" in r["result"]
    )

    errors = sum(
        1 for r in results
        if r["result"] == "ERROR"
    )

    print(f"Navigation links checked: {total}")
    print(f"Passed: {passed}")
    print(f"Redirects: {redirects}")
    print(f"Failures: {failures}")
    print(f"Errors: {errors}")

    print("\nDone!")