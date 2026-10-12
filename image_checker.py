from playwright.sync_api import sync_playwright
import csv
import os

from config import REPORTS_DIR
from urllib.parse import urlparse


IGNORED_IMAGE_FORMATS = (
    ".svg",
    ".ico",
)


def get_image_extension(url):
    path = urlparse(url).path.lower()

    if "." in path:
        return path.rsplit(".", 1)[-1]

    return ""


def check_images(pages):

    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context()

        request = context.request

        page = context.new_page()

        for index, url in enumerate(pages, start=1):

            print("\n" + "=" * 60)
            print(f"IMAGE CHECK [{index}/{len(pages)}]")
            print(url)
            print("=" * 60)

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                # Give lazy-loaded images a chance to load
                page.evaluate(
                    """
                    window.scrollTo(
                        0,
                        document.body.scrollHeight
                    );
                    """
                )

                page.wait_for_timeout(1000)

                images = page.locator("img")

                image_count = images.count()

                print(
                    f"Images found: {image_count}"
                )

                for image_index in range(image_count):

                    image = images.nth(
                        image_index
                    )

                    src = (
                        image.get_attribute(
                            "src"
                        )
                    )

                    current_src = (
                        image.get_attribute(
                            "currentSrc"
                        )
                    )

                    image_url = (
                        current_src
                        or src
                        or ""
                    )

                    alt = (
                        image.get_attribute(
                            "alt"
                        )
                        or ""
                    )

                    # Ignore images without URL
                    if not image_url:
                        results.append(
                            {
                                "page_url": url,
                                "image_url": "",
                                "alt": alt,
                                "status": "",
                                "file_size_kb": "",
                                "format": "",
                                "alt_result":
                                    "FAIL - Missing src",
                                "status_result":
                                    "FAIL - Missing src",
                                "size_result":
                                    "",
                                "format_result":
                                    "",
                                "overall_result":
                                    "FAIL"
                            }
                        )

                        continue

                    # --------------------------------
                    # ALT CHECK
                    # --------------------------------

                    if alt.strip():

                        alt_result = "PASS"

                    else:

                        alt_result = (
                            "FAIL - Missing alt"
                        )

                    # --------------------------------
                    # IMAGE REQUEST
                    # --------------------------------

                    status = None
                    file_size_kb = ""
                    content_type = ""

                    try:

                        response = request.get(
                            image_url,
                            timeout=30000,
                            fail_on_status_code=False
                        )

                        status = response.status

                        headers = response.headers

                        content_type = (
                            headers.get(
                                "content-type",
                                ""
                            )
                        )

                        content_length = (
                            headers.get(
                                "content-length"
                            )
                        )

                        if content_length:

                            file_size_kb = round(
                                int(content_length)
                                / 1024,
                                2
                            )

                    except Exception as e:

                        print(
                            f"Image request error: {e}"
                        )

                    # --------------------------------
                    # STATUS CHECK
                    # --------------------------------

                    if status == 200:

                        status_result = "PASS"

                    elif status is None:

                        status_result = (
                            "FAIL - Request failed"
                        )

                    else:

                        status_result = (
                            f"FAIL - HTTP {status}"
                        )

                    # --------------------------------
                    # SIZE CHECK
                    # --------------------------------

                    if file_size_kb == "":

                        size_result = (
                            "WARNING - Size unavailable"
                        )

                    elif file_size_kb <= 200:

                        size_result = "PASS"

                    else:

                        size_result = (
                            f"FAIL - {file_size_kb} KB"
                        )

                    # --------------------------------
                    # FORMAT CHECK
                    # --------------------------------

                    extension = get_image_extension(
                        image_url
                    )

                    if (
                        "image/webp"
                        in content_type.lower()
                    ):

                        image_format = "webp"

                    elif extension:

                        image_format = extension

                    else:

                        image_format = (
                            content_type
                        )

                    if image_format == "webp":

                        format_result = "PASS"

                    elif image_format in (
                        "svg",
                        "ico",
                    ):

                        format_result = (
                            "PASS - Vector/Icon"
                        )

                    else:

                        format_result = (
                            "WARNING - Not WebP"
                        )

                    # --------------------------------
                    # OVERALL RESULT
                    # --------------------------------

                    failures = [
                        alt_result,
                        status_result,
                        size_result
                    ]

                    has_failure = any(
                        result.startswith("FAIL")
                        for result in failures
                    )

                    if has_failure:

                        overall_result = "FAIL"

                    else:

                        overall_result = "PASS"

                    print(
                        f"\nImage {image_index + 1}"
                    )

                    print(
                        f"URL: {image_url}"
                    )

                    print(
                        f"Status: {status}"
                    )

                    print(
                        f"Size: {file_size_kb} KB"
                    )

                    print(
                        f"Format: {image_format}"
                    )

                    print(
                        f"Alt: {alt_result}"
                    )

                    print(
                        f"Overall: {overall_result}"
                    )

                    results.append(
                        {
                            "page_url": url,
                            "image_url": image_url,
                            "alt": alt,
                            "status": status,
                            "file_size_kb":
                                file_size_kb,
                            "format":
                                image_format,
                            "alt_result":
                                alt_result,
                            "status_result":
                                status_result,
                            "size_result":
                                size_result,
                            "format_result":
                                format_result,
                            "overall_result":
                                overall_result
                        }
                    )

            except Exception as e:

                print(
                    f"PAGE ERROR: {e}"
                )

        context.close()
        browser.close()

    return results


def save_image_report(results):

    os.makedirs(
        REPORTS_DIR,
        exist_ok=True
    )

    report_path = (
        os.path.join(REPORTS_DIR, "image_report.csv")
    )

    fieldnames = [
        "page_url",
        "image_url",
        "alt",
        "status",
        "file_size_kb",
        "format",
        "alt_result",
        "status_result",
        "size_result",
        "format_result",
        "overall_result"
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