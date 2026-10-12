from playwright.sync_api import sync_playwright
import csv
import os

from config import REPORTS_DIR
import time


def check_network(pages):

    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        for index, url in enumerate(pages, start=1):

            print("\n" + "=" * 60)
            print(
                f"NETWORK CHECK "
                f"[{index}/{len(pages)}]"
            )
            print(url)
            print("=" * 60)

            requests = {}

            def handle_request(request):

                requests[request] = {
                    "start_time": time.time()
                }

            def handle_response(response):

                request = response.request

                start_time = requests.get(
                    request,
                    {}
                ).get(
                    "start_time"
                )

                duration = ""

                if start_time:
                    duration = round(
                        (
                            time.time()
                            - start_time
                        ) * 1000,
                        2
                    )

                status = response.status

                resource_type = (
                    request.resource_type
                )

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

                print(
                    f"{status} | "
                    f"{resource_type} | "
                    f"{duration} ms | "
                    f"{request.url}"
                )

                results.append(
                    {
                        "page_url": url,
                        "request_url": request.url,
                        "method": request.method,
                        "resource_type":
                            resource_type,
                        "status": status,
                        "duration_ms":
                            duration,
                        "result": result
                    }
                )

            page.on(
                "request",
                handle_request
            )

            page.on(
                "response",
                handle_response
            )

            try:

                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=30000
                )

                page.wait_for_timeout(1000)

            except Exception as e:

                print(
                    f"PAGE ERROR: {e}"
                )

                results.append(
                    {
                        "page_url": url,
                        "request_url": "",
                        "method": "",
                        "resource_type": "",
                        "status": "",
                        "duration_ms": "",
                        "result":
                            f"ERROR - {e}"
                    }
                )

            page.remove_listener(
                "request",
                handle_request
            )

            page.remove_listener(
                "response",
                handle_response
            )

        browser.close()

    return results


def save_network_report(results):

    os.makedirs(
        REPORTS_DIR,
        exist_ok=True
    )

    report_path = (
        os.path.join(REPORTS_DIR, "network_report.csv")
    )

    fieldnames = [
        "page_url",
        "request_url",
        "method",
        "resource_type",
        "status",
        "duration_ms",
        "result"
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