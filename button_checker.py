from playwright.sync_api import sync_playwright
import csv
import os

from config import REPORTS_DIR, SITE_URL
from urllib.parse import urljoin, urlparse


TEST_URL = SITE_URL


def is_external_url(base_url, target_url):
    base_domain = urlparse(base_url).netloc
    target_domain = urlparse(target_url).netloc

    return target_domain and target_domain != base_domain


def should_skip_button(element):
    """
    Skip buttons that could submit forms or perform risky actions.
    """

    try:
        tag_name = element.evaluate(
            "(el) => el.tagName.toLowerCase()"
        )

        button_type = (
            element.get_attribute("type") or ""
        ).lower()

        href = (
            element.get_attribute("href") or ""
        ).lower()

        text = element.inner_text().strip().lower()

        # Never test form submit buttons here.
        if tag_name == "button" and button_type in [
            "submit",
            "reset"
        ]:
            return True

        # Skip links that are not normal web navigation.
        if href.startswith("mailto:"):
            return True

        if href.startswith("tel:"):
            return True

        if href.startswith("javascript:"):
            return True

        # Skip potentially destructive/purchasing actions.
        risky_words = [
            "delete",
            "remove",
            "logout",
            "log out",
            "purchase",
            "buy now",
            "pay now",
            "checkout",
            "add to cart"
        ]

        for word in risky_words:
            if word in text:
                return True

        # Skip anything inside a form.
        inside_form = element.evaluate(
            "(el) => !!el.closest('form')"
        )

        if inside_form:
            return True

    except Exception:
        return True

    return False


def find_buttons(page):

    selectors = [
        "button",
        "[role='button']",
        "a.btn",
        "a.button",
        "a.cta",
        "a[class*='btn']",
        "a[class*='button']",
        "a[class*='cta']"
    ]

    elements = []

    for selector in selectors:

        try:
            locator = page.locator(selector)

            count = locator.count()

            for i in range(count):

                element = locator.nth(i)

                if not element.is_visible():
                    continue

                if not element.is_enabled():
                    continue

                if should_skip_button(element):
                    continue

                elements.append(element)

        except Exception:
            continue

    return elements


def check_buttons(url):

    results = []

    print("=" * 60)
    print("PHASE 5B - BUTTON CHECK")
    print("=" * 60)

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

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
            print(f"Page load warning: {e}")

        page.wait_for_timeout(3000)

        buttons = find_buttons(page)

        print(
            f"\nTestable buttons found: {len(buttons)}"
        )

        # --------------------------------------------------
        # TEST EACH BUTTON
        # --------------------------------------------------

        for index, button in enumerate(buttons, start=1):

            try:

                text = button.inner_text().strip()

                if not text:
                    text = (
                        button.get_attribute("aria-label")
                        or button.get_attribute("title")
                        or f"Button {index}"
                    )

                href = button.get_attribute("href") or ""

                before_url = page.url

                before_scroll = page.evaluate(
                    "() => window.scrollY"
                )

                before_pages = len(
                    page.context.pages
                )

                print(
                    f"\n[{index}] Testing: {text[:50]}"
                )

                # --------------------------------------------------
                # CLICK
                # --------------------------------------------------

                try:

                    button.click(
                        timeout=10000,
                        no_wait_after=True
                    )

                    page.wait_for_timeout(1500)

                except Exception as click_error:

                    print(
                        f"CLICK FAIL: {click_error}"
                    )

                    results.append(
                        {
                            "page": url,
                            "button_text": text,
                            "href": href,
                            "result": "FAIL - Click Error",
                            "details": str(click_error)
                        }
                    )

                    continue

                # --------------------------------------------------
                # DETECT WHAT HAPPENED
                # --------------------------------------------------

                after_url = page.url

                after_scroll = page.evaluate(
                    "() => window.scrollY"
                )

                after_pages = len(
                    page.context.pages
                )

                # URL changed
                if after_url != before_url:

                    result = "PASS - Navigation"
                    details = (
                        f"URL changed to: {after_url}"
                    )

                # New tab/page opened
                elif after_pages > before_pages:

                    result = "PASS - New Tab/Window"
                    details = "New browser page opened"

                # Page scrolled
                elif abs(after_scroll - before_scroll) > 20:

                    result = "PASS - Scroll/Anchor"
                    details = (
                        f"Scroll changed from "
                        f"{before_scroll} to {after_scroll}"
                    )

                else:

                    # Check whether a dialog/modal became visible.
                    modal_count = page.locator(
                        "[role='dialog'], "
                        ".modal, "
                        ".popup, "
                        "[class*='modal' i], "
                        "[class*='popup' i]"
                    ).count()

                    visible_modal = False

                    for m in range(modal_count):

                        try:

                            modal = page.locator(
                                "[role='dialog'], "
                                ".modal, "
                                ".popup, "
                                "[class*='modal' i], "
                                "[class*='popup' i]"
                            ).nth(m)

                            if modal.is_visible():

                                visible_modal = True
                                break

                        except Exception:
                            continue

                    if visible_modal:

                        result = "PASS - Popup/Modal"
                        details = (
                            "Popup or modal became visible"
                        )

                    else:

                        result = "WARNING - No Detectable Action"
                        details = (
                            "Button was clicked but no "
                            "navigation, popup, or scroll "
                            "was detected"
                        )

                print(
                    f"Result: {result}"
                )

                print(
                    f"Details: {details}"
                )

                results.append(
                    {
                        "page": url,
                        "button_text": text,
                        "href": href,
                        "result": result,
                        "details": details
                    }
                )

                # --------------------------------------------------
                # CLOSE NEW TABS
                # --------------------------------------------------

                if len(page.context.pages) > 1:

                    for extra_page in page.context.pages:

                        if extra_page != page:

                            try:
                                extra_page.close()
                            except Exception:
                                pass

                # --------------------------------------------------
                # RETURN TO ORIGINAL PAGE
                # --------------------------------------------------

                if page.url != before_url:

                    try:

                        page.goto(
                            before_url,
                            wait_until="domcontentloaded",
                            timeout=30000
                        )

                        page.wait_for_timeout(1000)

                    except Exception:
                        pass

            except Exception as e:

                print(
                    f"Button processing error: {e}"
                )

                results.append(
                    {
                        "page": url,
                        "button_text": "",
                        "href": "",
                        "result": "ERROR",
                        "details": str(e)
                    }
                )

        browser.close()

    return results


def save_button_report(results):

    os.makedirs(REPORTS_DIR, exist_ok=True)

    report_file = os.path.join(REPORTS_DIR, "button_report.csv")

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
                "button_text",
                "href",
                "result",
                "details"
            ]
        )

        writer.writeheader()
        writer.writerows(results)

    print(
        f"\nButton report:"
        f"\n{report_file}"
    )


if __name__ == "__main__":

    results = check_buttons(TEST_URL)

    save_button_report(results)

    print("\n" + "=" * 60)
    print("PHASE 5B TEST SUMMARY")
    print("=" * 60)

    total = len(results)

    passed = sum(
        1
        for r in results
        if r["result"].startswith("PASS")
    )

    warnings = sum(
        1
        for r in results
        if r["result"].startswith("WARNING")
    )

    failures = sum(
        1
        for r in results
        if r["result"].startswith("FAIL")
    )

    errors = sum(
        1
        for r in results
        if r["result"] == "ERROR"
    )

    print(f"Buttons checked: {total}")
    print(f"Passed: {passed}")
    print(f"Warnings: {warnings}")
    print(f"Failures: {failures}")
    print(f"Errors: {errors}")

    print("\nDone!")