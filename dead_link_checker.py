from playwright.sync_api import sync_playwright
import csv
import os

from config import REPORTS_DIR
from urllib.parse import urlparse


def check_dead_links(pages):

    results = []

    discovered_links = set()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context()

        request = context.request

        page = context.new_page()

        # ----------------------------------------
        # COLLECT LINKS FROM ALL DISCOVERED PAGES
        # ----------------------------------------

        for index, page_url in enumerate(
            pages,
            start=1
        ):

            print("\n" + "=" * 60)
            print(
                f"COLLECTING LINKS "
                f"[{index}/{len(pages)}]"
            )
            print(page_url)
            print("=" * 60)

            try:

                page.goto(
                    page_url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                links = page.locator(
                    "a[href]"
                ).evaluate_all(
                    """
                    elements =>
                    elements.map(
                        a => ({
                            href: a.href,
                            text:
                                a.innerText.trim()
                        })
                    )
                    """
                )

                for link in links:

                    href = link["href"]

                    if not href:
                        continue

                    href = href.split("#")[0]

                    # Ignore special links
                    if href.startswith(
                        (
                            "mailto:",
                            "tel:",
                            "javascript:",
                            "data:"
                        )
                    ):
                        continue

                    if href.startswith("http"):

                        discovered_links.add(
                            (
                                page_url,
                                href
                            )
                        )

            except Exception as e:

                print(
                    f"Page error: {e}"
                )

        # ----------------------------------------
        # CHECK EVERY LINK
        # ----------------------------------------

        print("\n")
        print("=" * 60)
        print("CHECKING LINKS")
        print("=" * 60)

        for index, item in enumerate(
            discovered_links,
            start=1
        ):

            source_page = item[0]
            link_url = item[1]

            print(
                f"\n[{index}/"
                f"{len(discovered_links)}]"
            )

            print(
                f"Checking: {link_url}"
            )

            status = None
            error = ""

            try:

                response = request.get(
                    link_url,
                    timeout=30000,
                    fail_on_status_code=False
                )

                status = response.status

                # --------------------------------
                # RESULT
                # --------------------------------

                if 200 <= status < 300:

                    result = "PASS"

                elif 300 <= status < 400:

                    result = (
                        "REDIRECT"
                    )

                elif 400 <= status < 500:

                    result = "FAIL - 4xx"

                elif status >= 500:

                    result = "FAIL - 5xx"

                else:

                    result = "UNKNOWN"

            except Exception as e:

                result = "ERROR"

                error = str(e)

            print(
                f"Status: {status}"
            )

            print(
                f"Result: {result}"
            )

            results.append(
                {
                    "source_page":
                        source_page,
                    "link_url":
                        link_url,
                    "status":
                        status,
                    "result":
                        result,
                    "error":
                        error
                }
            )

        context.close()
        browser.close()

    return results


def save_dead_link_report(results):

    os.makedirs(
        REPORTS_DIR,
        exist_ok=True
    )

    report_path = (
        os.path.join(REPORTS_DIR, "dead_link_report.csv")
    )

    fieldnames = [
        "source_page",
        "link_url",
        "status",
        "result",
        "error"
    ]

    with open(
        report_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(results)

    return report_path