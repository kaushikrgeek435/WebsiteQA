"""
Popup form demo: open a popup/modal, fill required fields with dummy data,
submit, and record the whole process (video + step screenshots).

Usage:
    python popup_form_demo.py [URL] [--dry-run] [--headless]

--dry-run  fills the form but does NOT click submit.
"""

import csv
import os
import sys
from datetime import datetime

from playwright.sync_api import sync_playwright


DEFAULT_URL = "https://www.515concretefloorpolishing.com/"
OUTPUT_DIR = os.path.join("results", "popup_form_demo")
REPORT_FILE = os.path.join(OUTPUT_DIR, "popup_form_demo_report.csv")

POPUP_TRIGGERS = (
	"[data-toggle='modal'], [data-bs-toggle='modal'], "
	"[data-target^='#'], [data-bs-target^='#']"
)

DUMMY_MESSAGE = "Automated QA test submission - please ignore."

# Clearly fake data. Never use a real person's name.
DUMMY_BY_KEYWORD = [
	("first", "QA"),
	("last", "Test"),
	("full", "QA Test"),
	("name", "QA Test"),
	("email", "qa.test@example.com"),
	("phone", "5555550123"),
	("tel", "5555550123"),
	("address", "123 Test Street"),
	("zip", "10001"),
	("city", "Test City"),
	("message", DUMMY_MESSAGE),
	("comment", DUMMY_MESSAGE),
]

steps = []


def log(step, status, details, shot=""):
	print(f"   [{status}] {step}: {details}")
	steps.append({
		"time": datetime.now().strftime("%H:%M:%S"),
		"step": step,
		"status": status,
		"details": details,
		"screenshot": shot,
	})


def snap(page, name):
	path = os.path.join(OUTPUT_DIR, f"{len(steps) + 1:02d}_{name}.png")
	page.screenshot(path=path)
	return path


def dummy_value(field):
	field_type = (field.get_attribute("type") or "").lower()
	key = " ".join(
		(field.get_attribute(attr) or "")
		for attr in ("name", "id", "placeholder")
	).lower()

	if field_type == "email":
		return "qa.test@example.com"
	if field_type == "tel":
		return "5555550123"

	for keyword, value in DUMMY_BY_KEYWORD:
		if keyword in key:
			return value

	return "QA Test"


def is_required(field):
	return (
		field.get_attribute("required") is not None
		or field.get_attribute("aria-required") == "true"
	)


def highlight(locator):
	locator.evaluate(
		"e => { e.style.outline = '3px solid #ff3b30'; e.style.outlineOffset = '2px'; }"
	)


def open_popup(page):
	triggers = page.locator(POPUP_TRIGGERS)

	for index in range(triggers.count()):
		trigger = triggers.nth(index)

		if not trigger.is_visible():
			continue

		target = (
			trigger.get_attribute("data-target")
			or trigger.get_attribute("data-bs-target")
			or ""
		)

		if not target.startswith("#"):
			continue

		popup = page.locator(target)

		if popup.count() == 0 or popup.locator("form").count() == 0:
			continue

		label = trigger.inner_text().strip() or target
		trigger.scroll_into_view_if_needed()
		highlight(trigger)
		page.wait_for_timeout(800)
		log("Find trigger", "INFO", f"'{label}' -> {target}", snap(page, "trigger"))

		trigger.click()

		try:
			popup.wait_for(state="visible", timeout=5000)
		except Exception:
			log("Open popup", "ERROR", f"{target} did not become visible", snap(page, "popup_failed"))
			return None

		page.wait_for_timeout(1000)
		log("Open popup", "PASS", f"{target} is visible", snap(page, "popup_open"))
		return popup

	log("Find trigger", "INFO", "No popup trigger with a form found")
	return None


def fill_required(page, form):
	fields = form.locator("input, textarea, select")
	filled = 0

	for index in range(fields.count()):
		field = fields.nth(index)
		field_type = (field.get_attribute("type") or "").lower()

		if field_type in ("hidden", "submit", "button", "reset", "file"):
			continue
		if not field.is_visible() or not is_required(field):
			continue

		name = field.get_attribute("name") or field.get_attribute("id") or f"field {index}"

		if field_type in ("checkbox", "radio"):
			field.check()
			value = "checked"
		elif field.evaluate("e => e.tagName") == "SELECT":
			options = field.locator("option")
			field.select_option(index=1 if options.count() > 1 else 0)
			value = "first option"
		else:
			value = dummy_value(field)
			highlight(field)
			field.click()
			field.press_sequentially(value, delay=40)

		filled += 1
		log("Fill field", "INFO", f"{name} = {value}")

	page.wait_for_timeout(500)
	log("Fill required fields", "PASS" if filled else "WARNING",
		f"{filled} required field(s) filled", snap(page, "filled"))
	return filled


def has_captcha(form):
	return form.locator(
		"iframe[src*='recaptcha'], iframe[src*='hcaptcha'], "
		".g-recaptcha, .h-captcha, .cf-turnstile, iframe[src*='turnstile']"
	).count() > 0


def wait_for_human_captcha(page, form, timeout_seconds=120):
	"""Wait for a person to solve the CAPTCHA in the visible browser."""
	token = form.locator(
		"input[name='cf-turnstile-response'], textarea[name='g-recaptcha-response'], "
		"textarea[name='h-captcha-response']"
	)
	print(f"\n   >>> Please tick the CAPTCHA in the browser window ({timeout_seconds}s)...\n")

	for _ in range(timeout_seconds * 2):
		page.wait_for_timeout(500)
		for index in range(token.count()):
			if token.nth(index).input_value():
				log("CAPTCHA", "PASS", "Solved by tester", snap(page, "captcha_solved"))
				return True

	log("CAPTCHA", "WARNING", "Not solved in time - not submitting", snap(page, "captcha_timeout"))
	return False


def submit(page, form):
	button = form.locator(
		"input[type='submit'], button[type='submit'], button:not([type])"
	).first

	start_url = page.url
	highlight(button)
	page.wait_for_timeout(800)
	button.click()
	log("Click submit", "INFO", "Submit clicked")

	# Contact Form 7 shows its result in .wpcf7-response-output and sets a
	# status class on the form. Other forms may redirect to a thank-you page.
	response = form.locator(".wpcf7-response-output, [role='alert'], .success, .error")

	for _ in range(30):
		page.wait_for_timeout(500)

		if page.url != start_url:
			log("Submission result", "PASS", f"Redirected to {page.url}", snap(page, "result"))
			return

		form_class = form.get_attribute("class") or ""
		message = ""

		for index in range(response.count()):
			item = response.nth(index)
			if item.is_visible() and item.inner_text().strip():
				message = item.inner_text().strip()
				break

		if "sent" in form_class:
			log("Submission result", "PASS", message or "Form status: sent", snap(page, "result"))
			return
		if any(s in form_class for s in ("invalid", "failed", "spam", "aborted")):
			log("Submission result", "ERROR", message or form_class, snap(page, "result"))
			return
		if message and "submitting" not in form_class:
			log("Submission result", "WARNING", message, snap(page, "result"))
			return

	log("Submission result", "WARNING", "No confirmation within 15s", snap(page, "result"))


def save_report():
	with open(REPORT_FILE, "w", newline="", encoding="utf-8") as file:
		writer = csv.DictWriter(file, fieldnames=["time", "step", "status", "details", "screenshot"])
		writer.writeheader()
		writer.writerows(steps)


def main():
	args = [a for a in sys.argv[1:] if not a.startswith("--")]
	url = args[0] if args else DEFAULT_URL
	dry_run = "--dry-run" in sys.argv
	headless = "--headless" in sys.argv

	os.makedirs(OUTPUT_DIR, exist_ok=True)

	print("=" * 70)
	print("POPUP FORM DEMO")
	print("=" * 70)
	print(f"URL     : {url}")
	print(f"Submit  : {'NO (dry run)' if dry_run else 'YES'}\n")

	with sync_playwright() as p:
		browser = p.chromium.launch(headless=headless, slow_mo=250)
		context = browser.new_context(
			viewport={"width": 1440, "height": 900},
			record_video_dir=OUTPUT_DIR,
			record_video_size={"width": 1440, "height": 900},
		)
		page = context.new_page()

		try:
			page.goto(url, wait_until="domcontentloaded", timeout=60000)
			page.wait_for_timeout(3000)
			log("Open page", "PASS", url, snap(page, "page"))

			popup = open_popup(page)

			if popup:
				form = popup.locator("form").first

				if fill_required(page, form):
					captcha = has_captcha(form)

					if captcha:
						log("CAPTCHA", "INFO", "CAPTCHA detected", snap(page, "captcha"))

					if dry_run:
						log("Submit", "INFO", "Dry run - submit skipped")
					elif captcha and headless:
						log("Submit", "WARNING", "CAPTCHA needs a person - run without --headless")
					elif not captcha or wait_for_human_captcha(page, form):
						submit(page, form)

			page.wait_for_timeout(2000)
		except Exception as error:
			log("Execution", "ERROR", str(error))
		finally:
			video_path = page.video.path() if page.video else ""
			context.close()
			browser.close()

	save_report()

	print(f"\nReport : {REPORT_FILE}")
	if video_path:
		print(f"Video  : {video_path}")


if __name__ == "__main__":
	main()
