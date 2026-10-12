import argparse
import csv
import os

from playwright.sync_api import (
	sync_playwright,
	TimeoutError as PlaywrightTimeoutError,
)

import config


DEFAULT_URL = config.SITE_URL
QA_PAGES_FILE = config.QA_PAGES_FILE
RESULTS_DIR = config.REPORTS_DIR
REPORT_FILE = os.path.join(RESULTS_DIR, "popup_report.csv")


POPUP_SELECTORS = [
	"[role='dialog']",
	"dialog",
	".modal",
	".popup",
	"[class*='modal' i]",
	"[class*='popup' i]",
]

TRIGGER_SELECTORS = [
	"[data-toggle='modal']",
	"[data-bs-toggle='modal']",
	"[aria-haspopup='dialog']",
	"[aria-controls]",
	"[data-target]",
	"[data-bs-target]",
	"button[class*='modal' i]",
	"button[class*='popup' i]",
	"[role='button'][class*='modal' i]",
	"[role='button'][class*='popup' i]",
]

CLOSE_SELECTORS = [
	"[data-dismiss='modal']",
	"[data-bs-dismiss='modal']",
	"[aria-label*='close' i]",
	"[title*='close' i]",
	"button.close",
	".close",
	"button[class*='close' i]",
]

def parse_args():
	parser = argparse.ArgumentParser(
		description="Check popup and modal behavior on a site or QA-page list."
	)
	parser.add_argument(
		"--url",
		default=None,
		help="Single page URL to test. If omitted, use the QA page list."
	)
	parser.add_argument(
		"--qa-file",
		default=QA_PAGES_FILE,
		help="QA page list file to use when --url is not provided."
	)
	return parser.parse_args()


def load_qa_pages(qa_file=QA_PAGES_FILE):
	if not os.path.exists(qa_file):
		print(f"ERROR: {qa_file} not found. Run crawler.py first.")
		return []

	with open(qa_file, "r", encoding="utf-8") as file:
		return list(dict.fromkeys(
			line.strip()
			for line in file
			if line.strip()
		))


def load_pages_for_target(target_url=None, qa_file=QA_PAGES_FILE):
	if target_url:
		return [target_url.rstrip("/") + "/"] if not target_url.endswith("/") else [target_url]
	return load_qa_pages(qa_file)


def selector_group(selectors):
	return ", ".join(selectors)


def visible_popups(page):
	locator = page.locator(selector_group(POPUP_SELECTORS))
	visible = []

	for index in range(locator.count()):
		popup = locator.nth(index)

		try:
			if popup.is_visible():
				visible.append(popup)
		except Exception:
			continue

	return visible


def popup_has_content(popup):
	try:
		text = " ".join(popup.inner_text().split())
		return len(text) >= 3
	except Exception:
		return False


def popup_state(page):
	popups = visible_popups(page)

	if not popups:
		return False, False

	return True, any(popup_has_content(popup) for popup in popups)


def field_name(field, index):
	return (
		field.get_attribute("name")
		or field.get_attribute("id")
		or field.get_attribute("placeholder")
		or field.get_attribute("aria-label")
		or f"field_{index}"
	)


def field_is_required(field):
	return (
		field.get_attribute("required") is not None
		or field.get_attribute("aria-required") == "true"
		or "required" in (field.get_attribute("class") or "").lower()
	)


def form_kind(form):
	text = " ".join(form.inner_text().split()).lower()
	attributes = " ".join(
		(
			form.get_attribute("id") or "",
			form.get_attribute("class") or "",
			form.get_attribute("aria-label") or "",
		)
	).lower()
	combined = f"{text} {attributes}"

	if any(word in combined for word in ["apply", "application", "career", "job"]):
		return "Application"

	if any(word in combined for word in ["contact", "quote", "estimate", "inquiry"]):
		return "Contact"

	return "Contact/Application"


def empty_submit_validation(form):
	all_fields = form.locator("input, textarea, select")
	required_fields = []

	for index in range(all_fields.count()):
		field = all_fields.nth(index)
		try:
			if field.is_visible() and field_is_required(field):
				required_fields.append(field)
		except Exception:
			continue

	if not required_fields:
		return "INFO", "No required fields detected", ""

	invalid_count = 0
	validation_messages = []
	failed_fields = []

	for field in required_fields:
		try:
			result = field.evaluate("""
				(el) => {
					if (el.reportValidity) {
						el.reportValidity();
					}
					return {
						valid: el.validity ? el.validity.valid : true,
						message: el.validationMessage || '',
						name: (el.name || el.id || el.getAttribute('placeholder') || 'field')
					};
				}
			""")
			if result and result.get("valid") is False:
				invalid_count += 1
				failed_fields.append(result.get("name") or "field")
				if result.get("message"):
					validation_messages.append(result.get("message"))
		except Exception:
			continue

	message_text = " ".join(validation_messages).strip()
	if invalid_count > 0 or message_text:
		field_summary = "; ".join(failed_fields[:5]) if failed_fields else "required fields"
		return "PASS", (message_text or "Required-field validation triggered"), field_summary

	return "WARNING", "Required fields exist, but no validation message was triggered", "; ".join(failed_fields[:5]) if failed_fields else "required fields"


def test_popup_forms(page, page_url, popup_number):
	forms = []
	for popup in visible_popups(page):
		popup_forms = popup.locator("form")
		for index in range(popup_forms.count()):
			form = popup_forms.nth(index)
			try:
				if form.is_visible():
					forms.append(form)
			except Exception:
				continue

	if not forms:
		return {
			"form_type": "None",
			"required_fields": "",
			"empty_validation": "N/A",
			"form_submission": "N/A",
			"thank_you": "N/A",
			"form_details": "No contact or application form in popup",
		}

	form = forms[0]
	fields = []
	all_fields = form.locator("input, textarea, select")
	for index in range(all_fields.count()):
		field = all_fields.nth(index)
		try:
			if field.is_visible() and field_is_required(field):
				fields.append(field)
		except Exception:
			continue

	form_type = form_kind(form)
	required_names = [
		field_name(field, index)
		for index, field in enumerate(fields, start=1)
	]
	validation_status, validation_detail, failed_field_summary = empty_submit_validation(form)

	return {
		"form_type": form_type,
		"required_fields": "; ".join(required_names),
		"empty_validation": validation_status,
		"form_submission": "N/A",
		"thank_you": "N/A",
		"form_details": f"Form detected; validation check: {validation_detail}; failed field(s): {failed_field_summary}",
	}


def find_triggers(page):
	triggers = []
	seen = set()

	for selector in TRIGGER_SELECTORS:
		locator = page.locator(selector)

		for index in range(locator.count()):
			trigger = locator.nth(index)

			try:
				if not trigger.is_visible() or not trigger.is_enabled():
					continue

				identity = trigger.evaluate(
					"el => ({tag: el.tagName, id: el.id, className: el.className, "
					"text: (el.innerText || '').trim(), href: el.getAttribute('href')})"
				)
				identity = str(identity)

				if identity not in seen:
					seen.add(identity)
					triggers.append(trigger)
			except Exception:
				continue

	return triggers


def trigger_name(trigger, index):
	try:
		return (
			" ".join(trigger.inner_text().split())
			or trigger.get_attribute("aria-label")
			or trigger.get_attribute("title")
			or f"Trigger {index}"
		)[:100]
	except Exception:
		return f"Trigger {index}"


def find_close_control(popup):
	locator = popup.locator(selector_group(CLOSE_SELECTORS))

	for index in range(locator.count()):
		control = locator.nth(index)

		try:
			if control.is_visible() and control.is_enabled():
				return control
		except Exception:
			continue

	return None


def press_escape(page):
	try:
		page.keyboard.press("Escape")
		page.wait_for_timeout(500)

		if not visible_popups(page):
			return "PASS"
	except Exception:
		pass

	return "INFO"


def click_close_control(page):
	for popup in visible_popups(page):
		close_control = find_close_control(popup)

		if close_control:
			try:
				close_control.click(timeout=5000)
				page.wait_for_timeout(500)

				if not visible_popups(page):
					return "PASS"
			except Exception:
				pass

	return "WARNING"


def check_trigger(page, page_url, trigger, trigger_index):
	name = trigger_name(trigger, trigger_index)
	before_url = page.url

	try:
		trigger.click(timeout=5000, no_wait_after=True)
		page.wait_for_timeout(700)
	except Exception as error:
		return {
			"page": page_url,
			"popup_number": trigger_index,
			"trigger": name,
			"open": "ERROR",
			"close": "N/A",
			"escape": "N/A",
			"result": "ERROR",
			"details": f"Trigger click failed: {error}",
		}

	opened, has_content = popup_state(page)

	if page.url != before_url and not opened:
		return {
			"page": page_url,
			"popup_number": trigger_index,
			"trigger": name,
			"open": "INFO",
			"close": "N/A",
			"escape": "N/A",
			"result": "INFO",
			"details": "Trigger navigated without opening a popup",
		}

	if not opened:
		return {
			"page": page_url,
			"popup_number": trigger_index,
			"trigger": name,
			"open": "ERROR",
			"close": "N/A",
			"escape": "N/A",
			"result": "ERROR",
			"details": "Trigger clicked, but no visible popup was detected",
		}

	if not has_content:
		return {
			"page": page_url,
			"popup_number": trigger_index,
			"trigger": name,
			"open": "ERROR",
			"close": "N/A",
			"escape": "N/A",
			"result": "ERROR",
			"details": "Popup opened without meaningful visible content",
		}

	has_form = any(
		popup.locator("form").count() > 0
		for popup in visible_popups(page)
	)
	escape_result = press_escape(page)

	if escape_result == "PASS":
		try:
			trigger.click(timeout=5000, no_wait_after=True)
			page.wait_for_timeout(500)
		except Exception:
			pass

	close_result = click_close_control(page)
	close_details = []

	if close_result == "PASS":
		close_details.append("Close control hid the popup")
	else:
		close_details.append("No working close control was found")

	if escape_result == "PASS":
		close_details.append("Escape key hid the popup")
	else:
		close_details.append("Escape behavior was not detected")

	overall = (
		"PASS"
		if close_result == "PASS" and escape_result in ["PASS", "INFO"]
		else "WARNING"
	)

	form_result = {
		"form_type": "None",
		"required_fields": "",
		"empty_validation": "N/A",
		"form_submission": "N/A",
		"thank_you": "N/A",
		"form_details": "No contact or application form in popup",
	}

	if has_form:
		try:
			if not visible_popups(page):
				trigger.click(timeout=5000, no_wait_after=True)
				page.wait_for_timeout(700)

			form_result = test_popup_forms(
				page,
				page_url,
				trigger_index,
			)
			overall = (
				"PASS"
				if overall == "PASS"
				and form_result["empty_validation"] in ["PASS", "N/A"]
				and form_result["form_submission"] in ["PASS", "N/A"]
				else "WARNING"
			)
		except Exception as error:
			form_result["form_submission"] = "ERROR"
			form_result["form_details"] = f"Popup form check failed: {error}"
			overall = "ERROR"

	return {
		"page": page_url,
		"popup_number": trigger_index,
		"trigger": name,
		"open": "PASS",
		"close": close_result,
		"escape": escape_result,
		"result": overall,
		"form_type": form_result["form_type"],
		"required_fields": form_result["required_fields"],
		"empty_validation": form_result["empty_validation"],
		"form_submission": form_result["form_submission"],
		"thank_you": form_result["thank_you"],
		"details": (
			"; ".join(close_details)
			+ "; "
			+ form_result["form_details"]
		),
	}


def check_page(browser, page_url):
	print(f"\nChecking page: {page_url}")
	page = browser.new_page(viewport={"width": 1440, "height": 900})

	try:
		try:
			page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
		except PlaywrightTimeoutError:
			print("   Page load timeout - continuing")

		page.wait_for_timeout(1200)
		initial_popups = visible_popups(page)

		if initial_popups:
			result = {
				"page": page_url,
				"popup_number": 0,
				"trigger": "Initial page state",
				"open": "PASS",
				"close": "N/A",
				"escape": "N/A",
				"result": "WARNING",
				"details": "Popup is visible on page load; no trigger was required",
			}
			return [result]

		triggers = find_triggers(page)

		if not triggers:
			print("   No popup/modal detected")
			return [{
				"page": page_url,
				"popup_number": 0,
				"trigger": "None",
				"open": "N/A",
				"close": "N/A",
				"escape": "N/A",
				"result": "INFO",
				"details": "No explicit popup/modal trigger detected",
			}]

		results = []

		for index, trigger in enumerate(triggers, start=1):
			result = check_trigger(page, page_url, trigger, index)
			results.append(result)

			if page.url != page_url:
				page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
				page.wait_for_timeout(700)

		return results
	finally:
		page.close()


def check_popups(pages):
	results = []

	print("=" * 70)
	print("PHASE 5G - POPUP / MODAL CHECKER")
	print("=" * 70)
	print(f"Pages to check: {len(pages)}")

	with sync_playwright() as playwright:
		browser = playwright.chromium.launch(headless=True)

		try:
			for page_url in pages:
				results.extend(check_page(browser, page_url))
		finally:
			browser.close()

	return results


def save_popup_report(results):
	os.makedirs(RESULTS_DIR, exist_ok=True)

	fieldnames = [
		"page",
		"popup_number",
		"trigger",
		"open",
		"close",
		"escape",
		"form_type",
		"required_fields",
		"empty_validation",
		"form_submission",
		"thank_you",
		"result",
		"details",
	]

	with open(REPORT_FILE, "w", newline="", encoding="utf-8") as file:
		writer = csv.DictWriter(file, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(results)

	print(f"\nPopup report saved: {REPORT_FILE}")
	return REPORT_FILE


def main():
	args = parse_args()
	selected_url = args.url or DEFAULT_URL

	print("\n" + "=" * 70)
	print("PHASE 5G - POPUP / MODAL CHECKER")
	print("=" * 70)

	if args.url:
		print(f"Target URL: {selected_url}")
		pages = load_pages_for_target(selected_url)
	else:
		print(f"Using QA file: {args.qa_file}")
		pages = load_pages_for_target(qa_file=args.qa_file)

	if not pages:
		return

	results = check_popups(pages)
	save_popup_report(results)

	counts = {
		status: sum(item["result"] == status for item in results)
		for status in ["PASS", "WARNING", "ERROR", "INFO"]
	}

	print("\nPOPUP CHECK SUMMARY")
	print("=" * 70)
	print(f"Total records : {len(results)}")
	print(f"PASS          : {counts['PASS']}")
	print(f"WARNING       : {counts['WARNING']}")
	print(f"ERROR         : {counts['ERROR']}")
	print(f"INFO          : {counts['INFO']}")


if __name__ == "__main__":
	main()
