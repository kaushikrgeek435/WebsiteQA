from playwright.sync_api import sync_playwright
import csv
import os

from config import REPORTS_DIR


def check_seo(pages):

    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        for index, url in enumerate(pages, start=1):

            print("\n" + "=" * 60)
            print(f"SEO CHECK [{index}/{len(pages)}]")
            print(url)
            print("=" * 60)

            try:

                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                status = response.status if response else None

                # ---------------------------------
                # H1 CHECK
                # ---------------------------------

                h1_elements = page.locator("h1")

                h1_count = h1_elements.count()

                if h1_count == 1:
                    h1_result = "PASS"
                elif h1_count == 0:
                    h1_result = "FAIL - Missing H1"
                else:
                    h1_result = (
                        f"FAIL - {h1_count} H1 tags"
                    )

                # ---------------------------------
                # TITLE CHECK
                # ---------------------------------

                title = page.title().strip()

                if title:
                    title_result = "PASS"
                else:
                    title_result = "FAIL - Missing title"

                # ---------------------------------
                # META DESCRIPTION
                # ---------------------------------

                meta_description = page.locator(
                    'meta[name="description"]'
                ).get_attribute("content")

                if meta_description:
                    meta_description = (
                        meta_description.strip()
                    )

                if meta_description:
                    description_result = "PASS"
                else:
                    description_result = (
                        "FAIL - Missing meta description"
                    )

                # ---------------------------------
                # CANONICAL
                # ---------------------------------

                canonical = page.locator(
                    'link[rel="canonical"]'
                ).get_attribute("href")

                if canonical:
                    canonical_result = "PASS"
                else:
                    canonical_result = (
                        "FAIL - Missing canonical"
                    )

                # ---------------------------------
                # HEADING STRUCTURE
                # ---------------------------------

                headings = page.locator(
                    "h1, h2, h3, h4, h5, h6"
                ).evaluate_all(
                    """
                    elements => elements.map(
                        element => ({
                            tag: element.tagName,
                            text: element.innerText.trim()
                        })
                    )
                    """
                )

                heading_result = check_heading_structure(
                    headings
                )

                # ---------------------------------
                # PAGE RESULT
                # ---------------------------------

                checks = [
                    h1_result,
                    title_result,
                    description_result,
                    canonical_result,
                    heading_result
                ]

                failed_checks = [
                    check
                    for check in checks
                    if check.startswith("FAIL")
                ]

                if failed_checks:
                    overall_result = "FAIL"
                else:
                    overall_result = "PASS"

                print(
                    f"H1:              {h1_result}"
                )

                print(
                    f"Title:            {title_result}"
                )

                print(
                    f"Meta Description: {description_result}"
                )

                print(
                    f"Canonical:        {canonical_result}"
                )

                print(
                    f"Headings:         {heading_result}"
                )

                print(
                    f"Overall:          {overall_result}"
                )

                results.append(
                    {
                        "url": url,
                        "status": status,
                        "h1_count": h1_count,
                        "h1_result": h1_result,
                        "title": title,
                        "title_result": title_result,
                        "meta_description": (
                            meta_description or ""
                        ),
                        "description_result": (
                            description_result
                        ),
                        "canonical": canonical or "",
                        "canonical_result": (
                            canonical_result
                        ),
                        "heading_result": (
                            heading_result
                        ),
                        "overall_result": (
                            overall_result
                        )
                    }
                )

            except Exception as e:

                print(
                    f"ERROR: {e}"
                )

                results.append(
                    {
                        "url": url,
                        "status": "",
                        "h1_count": "",
                        "h1_result": "ERROR",
                        "title": "",
                        "title_result": "ERROR",
                        "meta_description": "",
                        "description_result": "ERROR",
                        "canonical": "",
                        "canonical_result": "ERROR",
                        "heading_result": "ERROR",
                        "overall_result": "ERROR"
                    }
                )

        browser.close()

    return results


def check_heading_structure(headings):

    if not headings:
        return "FAIL - No headings found"

    # First heading should ideally be H1
    first_heading = headings[0]["tag"]

    if first_heading != "H1":
        return (
            f"WARNING - First heading is "
            f"{first_heading}"
        )

    # Check heading level jumps
    previous_level = None

    for heading in headings:

        current_level = int(
            heading["tag"][1]
        )

        if previous_level is not None:

            if current_level > previous_level + 1:

                return (
                    f"WARNING - Heading jump "
                    f"H{previous_level} → "
                    f"H{current_level}"
                )

        previous_level = current_level

    return "PASS"


def save_seo_report(results):

    os.makedirs(
        REPORTS_DIR,
        exist_ok=True
    )

    report_path = (
        os.path.join(REPORTS_DIR, "seo_report.csv")
    )

    with open(
        report_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "url",
                "status",
                "h1_count",
                "h1_result",
                "title",
                "title_result",
                "meta_description",
                "description_result",
                "canonical",
                "canonical_result",
                "heading_result",
                "overall_result"
            ]
        )

        writer.writeheader()

        writer.writerows(results)

    return report_path