from playwright.sync_api import sync_playwright
import csv
import os

from config import REPORTS_DIR


def check_console(pages):

    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        for index, url in enumerate(pages, start=1):

            print("\n" + "=" * 60)
            print(
                f"CONSOLE CHECK "
                f"[{index}/{len(pages)}]"
            )
            print(url)
            print("=" * 60)

            console_messages = []

            def handle_console(message):

                message_type = message.type

                # We mainly care about errors and warnings
                if message_type in (
                    "error",
                    "warning"
                ):

                    console_messages.append(
                        {
                            "type": message_type,
                            "text": message.text
                        }
                    )

            page.on(
                "console",
                handle_console
            )

            try:

                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=30000
                )

                # Give delayed JavaScript a chance
                page.wait_for_timeout(1000)

                if not console_messages:

                    print(
                        "Console: PASS - "
                        "No errors/warnings detected"
                    )

                    results.append(
                        {
                            "url": url,
                            "type": "",
                            "message": "",
                            "result": "PASS"
                        }
                    )

                else:

                    for message in console_messages:

                        print(
                            f"{message['type'].upper()}: "
                            f"{message['text']}"
                        )

                        results.append(
                            {
                                "url": url,
                                "type": message["type"],
                                "message": message["text"],
                                "result": (
                                    "FAIL"
                                    if message["type"]
                                    == "error"
                                    else "WARNING"
                                )
                            }
                        )

            except Exception as e:

                print(
                    f"PAGE ERROR: {e}"
                )

                results.append(
                    {
                        "url": url,
                        "type": "page_error",
                        "message": str(e),
                        "result": "ERROR"
                    }
                )

            # Remove listener before next page
            page.remove_listener(
                "console",
                handle_console
            )

        browser.close()

    return results


def save_console_report(results):

    os.makedirs(
        REPORTS_DIR,
        exist_ok=True
    )

    report_path = (
        os.path.join(REPORTS_DIR, "console_report.csv")
    )

    fieldnames = [
        "url",
        "type",
        "message",
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