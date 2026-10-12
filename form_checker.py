from playwright.sync_api import sync_playwright
import csv
import os

from config import REPORTS_DIR


TEST_URL = "https://dev.dotcomdesign.com/eclipse-roofing/get-a-quote/"


def get_field_name(field, index):
    """
    Try to get a useful name for a form field.
    """

    try:
        name = field.get_attribute("name")

        if name:
            return name

        field_id = field.get_attribute("id")

        if field_id:
            return field_id

        placeholder = field.get_attribute("placeholder")

        if placeholder:
            return placeholder

        aria_label = field.get_attribute("aria-label")

        if aria_label:
            return aria_label

    except Exception:
        pass

    return f"field_{index}"


def get_field_type(field):
    """
    Return the HTML field type.
    """

    try:
        tag = field.evaluate(
            "(el) => el.tagName.toLowerCase()"
        )

        if tag == "textarea":
            return "textarea"

        if tag == "select":
            return "select"

        if tag == "input":
            return (
                field.get_attribute("type")
                or "text"
            ).lower()

        return tag

    except Exception:
        return "unknown"


def is_required(field):
    """
    Detect whether a field is required.
    """

    try:

        required = field.get_attribute("required")

        if required is not None:
            return True

        aria_required = (
            field.get_attribute("aria-required")
        )

        if aria_required == "true":
            return True

        # Some websites use a class containing "required".
        class_name = (
            field.get_attribute("class")
            or ""
        ).lower()

        if "required" in class_name:
            return True

    except Exception:
        pass

    return False


def get_validation_message(field):
    """
    Get browser validation message if available.
    """

    try:

        return field.evaluate(
            """
            (el) => {
                if (typeof el.validationMessage === "string") {
                    return el.validationMessage;
                }
                return "";
            }
            """
        )

    except Exception:
        return ""


def find_visible_forms(page):

    forms = page.locator("form")

    visible_forms = []

    for i in range(forms.count()):

        try:

            form = forms.nth(i)

            if form.is_visible():
                visible_forms.append(form)

        except Exception:
            continue

    return visible_forms


def check_form(url):

    results = []

    print("=" * 60)
    print("PHASE 5C - SAFE FORM CHECK")
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

        # --------------------------------------------------
        # FIND FORMS
        # --------------------------------------------------

        forms = find_visible_forms(page)

        print(
            f"\nVisible forms found: {len(forms)}"
        )

        if not forms:

            print(
                "\nWARNING: No visible form found."
            )

            browser.close()

            return results

        # --------------------------------------------------
        # CHECK EACH FORM
        # --------------------------------------------------

        for form_number, form in enumerate(
            forms,
            start=1
        ):

            print(
                f"\n{'-' * 50}"
            )

            print(
                f"FORM {form_number}"
            )

            print(
                f"{'-' * 50}"
            )

            fields = form.locator(
                "input, textarea, select"
            )

            field_count = fields.count()

            print(
                f"Total fields: {field_count}"
            )

            required_count = 0

            # --------------------------------------------------
            # FIELD ANALYSIS
            # --------------------------------------------------

            for i in range(field_count):

                try:

                    field = fields.nth(i)

                    if not field.is_visible():
                        continue

                    field_name = get_field_name(
                        field,
                        i + 1
                    )

                    field_type = get_field_type(
                        field
                    )

                    required = is_required(
                        field
                    )

                    if required:
                        required_count += 1

                    print(
                        f"\nField: {field_name}"
                    )

                    print(
                        f"Type: {field_type}"
                    )

                    print(
                        f"Required: "
                        f"{'YES' if required else 'NO'}"
                    )

                    results.append(
                        {
                            "page": url,
                            "form_number": form_number,
                            "field_name": field_name,
                            "field_type": field_type,
                            "required": (
                                "YES"
                                if required
                                else "NO"
                            ),
                            "validation": "",
                            "result": (
                                "PASS"
                                if required
                                else "INFO"
                            )
                        }
                    )

                except Exception as e:

                    print(
                        f"Field error: {e}"
                    )

            print(
                f"\nRequired fields found: "
                f"{required_count}"
            )

            # --------------------------------------------------
            # FIND SUBMIT BUTTON
            # --------------------------------------------------

            submit_buttons = form.locator(
                "button[type='submit'], "
                "input[type='submit'], "
                "button:not([type])"
            )

            submit_button = None

            for i in range(
                submit_buttons.count()
            ):

                try:

                    candidate = (
                        submit_buttons.nth(i)
                    )

                    if candidate.is_visible():
                        submit_button = candidate
                        break

                except Exception:
                    continue

            if submit_button is None:

                print(
                    "\nWARNING: Submit button "
                    "not found."
                )

                continue

            submit_text = ""

            try:

                submit_text = (
                    submit_button.inner_text()
                    .strip()
                )

            except Exception:

                submit_text = (
                    submit_button.get_attribute(
                        "value"
                    )
                    or "Submit"
                )

            print(
                f"\nSubmit button: "
                f"{submit_text}"
            )

            # --------------------------------------------------
            # SAFE VALIDATION TEST
            # --------------------------------------------------

            print(
                "\nTesting empty form validation..."
            )

            before_url = page.url

            try:

                # IMPORTANT:
                # We do NOT fill anything.
                # We only click Submit once.

                submit_button.click(
                    timeout=10000,
                    no_wait_after=True
                )

                page.wait_for_timeout(1500)

                print(
                    "Submit click: PASS"
                )

            except Exception as e:

                print(
                    f"Submit click error: {e}"
                )

                results.append(
                    {
                        "page": url,
                        "form_number": form_number,
                        "field_name": "",
                        "field_type": "",
                        "required": "",
                        "validation": "",
                        "result": (
                            "FAIL - Submit Click"
                        )
                    }
                )

                continue

            after_url = page.url

            # --------------------------------------------------
            # CHECK VALIDATION
            # --------------------------------------------------

            validation_found = False

            for i in range(field_count):

                try:

                    field = fields.nth(i)

                    if not field.is_visible():
                        continue

                    message = (
                        get_validation_message(
                            field
                        )
                    )

                    if message:

                        validation_found = True

                        print(
                            f"\nValidation: "
                            f"{get_field_name(field, i + 1)}"
                        )

                        print(
                            f"Message: {message}"
                        )

                        results.append(
                            {
                                "page": url,
                                "form_number": form_number,
                                "field_name": (
                                    get_field_name(
                                        field,
                                        i + 1
                                    )
                                ),
                                "field_type": (
                                    get_field_type(
                                        field
                                    )
                                ),
                                "required": (
                                    "YES"
                                    if is_required(field)
                                    else "NO"
                                ),
                                "validation": message,
                                "result": (
                                    "PASS - Validation"
                                )
                            }
                        )

                except Exception:
                    continue

            # --------------------------------------------------
            # CHECK COMMON CUSTOM VALIDATION
            # --------------------------------------------------

            custom_errors = page.locator(
                ".error, "
                ".errors, "
                ".invalid-feedback, "
                ".validation-message, "
                "[role='alert']"
            )

            custom_error_count = 0

            for i in range(
                custom_errors.count()
            ):

                try:

                    error = custom_errors.nth(i)

                    if error.is_visible():

                        text = (
                            error.inner_text()
                            .strip()
                        )

                        if text:

                            custom_error_count += 1

                            print(
                                f"\nCustom validation:"
                            )

                            print(text)

                            results.append(
                                {
                                    "page": url,
                                    "form_number": form_number,
                                    "field_name": "",
                                    "field_type": "",
                                    "required": "",
                                    "validation": text,
                                    "result": (
                                        "PASS - Custom Validation"
                                    )
                                }
                            )

                except Exception:
                    continue

            # --------------------------------------------------
            # FINAL EMPTY FORM RESULT
            # --------------------------------------------------

            if validation_found or custom_error_count > 0:

                print(
                    "\nEmpty form validation: PASS"
                )

            elif after_url != before_url:

                print(
                    "\nWARNING: Form navigated "
                    "without detectable validation."
                )

                results.append(
                    {
                        "page": url,
                        "form_number": form_number,
                        "field_name": "",
                        "field_type": "",
                        "required": "",
                        "validation": "",
                        "result": (
                            "WARNING - Navigated"
                        )
                    }
                )

            else:

                print(
                    "\nWARNING: No validation "
                    "message detected."
                )

                results.append(
                    {
                        "page": url,
                        "form_number": form_number,
                        "field_name": "",
                        "field_type": "",
                        "required": "",
                        "validation": "",
                        "result": (
                            "WARNING - No Validation"
                        )
                    }
                )

        browser.close()

    return results


def save_form_report(results):

    os.makedirs(
        REPORTS_DIR,
        exist_ok=True
    )

    report_file = (
        os.path.join(REPORTS_DIR, "form_report.csv")
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
                "form_number",
                "field_name",
                "field_type",
                "required",
                "validation",
                "result"
            ]
        )

        writer.writeheader()

        writer.writerows(results)

    print(
        f"\nForm report:"
        f"\n{report_file}"
    )


if __name__ == "__main__":

    results = check_form(TEST_URL)

    save_form_report(results)

    print("\n" + "=" * 60)
    print("PHASE 5C TEST SUMMARY")
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

    print(
        f"Records checked: {total}"
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

    print("\nDone!")