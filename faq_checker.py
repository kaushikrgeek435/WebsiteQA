"""
FAQ content checker.

Compares the expected FAQs in faq_expected.json (page URL -> [question, answer])
against the live page text. Hidden accordion answers are included (textContent).

PASS    : exact text found (ignoring case, punctuation, spacing, quote style)
WARNING : close match found (wording differs slightly) - review `site_text`
ERROR   : not found on the page / page failed to load

Output: results/<site>/reports/faq_report.csv
Run:    python faq_checker.py
"""

import csv
import json
import re
import sys
from difflib import SequenceMatcher

from playwright.sync_api import sync_playwright

from config import report_path

EXPECTED_FILE = "faq_expected.json"
CLOSE_MATCH = 0.85

COLLECT_JS = """
() => {
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (el.closest('script,style,noscript,template,svg')) continue;
    const t = (el.textContent || '').replace(/\\s+/g, ' ').trim();
    if (t.length >= 8 && t.length <= 4000) out.push(t);
  }
  // Exclude <script> text so FAQ schema JSON-LD cannot count as page content.
  const body = document.body.cloneNode(true);
  body.querySelectorAll('script,style,noscript,template').forEach(e => e.remove());
  return {all: body.textContent.replace(/\\s+/g, ' '), blocks: [...new Set(out)]};
}
"""


def loose(text):
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"[‐-―]", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def compact(text):
    return re.sub(r"[^a-z0-9$%+]", "", loose(text))


def best_match(expected, blocks):
    target = loose(expected)
    best_ratio, best_text = 0.0, ""
    for block in blocks:
        cand = loose(block)
        if len(cand) > len(target) * 1.6 or len(cand) < len(target) * 0.5:
            continue
        sm = SequenceMatcher(None, target, cand, autojunk=False)
        if sm.quick_ratio() <= best_ratio:
            continue
        ratio = sm.ratio()
        if ratio > best_ratio:
            best_ratio, best_text = ratio, block
    return best_ratio, best_text


def check(kind, expected, page_compact, blocks):
    if compact(expected) in page_compact:
        return "PASS", 1.0, ""
    ratio, text = best_match(expected, blocks)
    if ratio >= CLOSE_MATCH:
        return "WARNING", ratio, text
    return "ERROR", ratio, text if ratio >= 0.5 else ""


def main():
    with open(EXPECTED_FILE, encoding="utf-8") as f:
        expected = json.load(f)

    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        for url, faqs in expected.items():
            print(f"\n{url}")
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1500)
                status = resp.status if resp else ""
                data = page.evaluate(COLLECT_JS)
            except Exception as exc:
                print(f"  ERROR loading page: {exc}")
                for i, (q, a) in enumerate(faqs, 1):
                    for kind, text in (("question", q), ("answer", a)):
                        rows.append([url, "", i, kind, text, "ERROR", 0, "", f"Page load failed: {exc}"])
                continue

            page_compact = compact(data["all"])
            for i, (q, a) in enumerate(faqs, 1):
                for kind, text in (("question", q), ("answer", a)):
                    result, ratio, found = check(kind, text, page_compact, data["blocks"])
                    note = {"PASS": "Exact match",
                            "WARNING": "Text differs slightly from the doc",
                            "ERROR": "Not found on page"}[result]
                    rows.append([url, status, i, kind, text, result, f"{ratio:.2f}", found, note])
                    if result != "PASS":
                        print(f"  {result:7} Q{i} {kind}: {text[:70]}")
            passed = sum(1 for r in rows if r[0] == url and r[5] == "PASS")
            print(f"  HTTP {status} - {passed}/{len(faqs) * 2} items exact")

        browser.close()

    out = report_path("faq_report.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["page", "http_status", "faq_number", "item", "expected_text",
                    "result", "similarity", "site_text", "details"])
        w.writerows(rows)

    counts = {k: sum(1 for r in rows if r[5] == k) for k in ("PASS", "WARNING", "ERROR")}
    print(f"\nPages: {len(expected)}  Items: {len(rows)}  {counts}")
    print(f"Report: {out}")


if __name__ == "__main__":
    sys.exit(main())
