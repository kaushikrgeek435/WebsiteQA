"""
FAQ hyperlink checker.

For every link the FAQ doc shows inside an answer (faq_links.json), checks on the live page:
  - the answer contains a link with that text
  - the link points to the expected service page (when a target is known)
  - the target loads (HTTP < 400)
Links on the page inside an FAQ answer that the doc does not show are reported as WARNING.

Output: results/<site>/reports/faq_link_report.csv
Run:    python faq_link_checker.py
"""

import csv
import json
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

from config import report_path
from faq_checker import compact

# Finds the smallest element whose text contains the answer, and returns its links.
ANSWER_LINKS_JS = """
(answerKey) => {
  const key = s => s.toLowerCase().replace(/[\\u2018\\u2019]/g, "'").replace(/[^a-z0-9$%+]/g, '');
  let best = null;
  for (const el of document.body.querySelectorAll('*')) {
    if (el.closest('script,style,noscript,template')) continue;
    if (!key(el.textContent || '').includes(answerKey)) continue;
    if (!best || (el.textContent.length < best.textContent.length)) best = el;
  }
  if (!best) return null;
  return [...best.querySelectorAll('a[href]')].map(a => ({
    text: a.textContent.replace(/\\s+/g, ' ').trim(), href: a.getAttribute('href')}));
}
"""


def slug(url):
    return urlparse(url).path.rstrip("/").split("/")[-1]


def main():
    with open("faq_expected.json", encoding="utf-8") as f:
        faqs = json.load(f)
    with open("faq_links.json", encoding="utf-8") as f:
        link_spec = json.load(f)
    targets = link_spec.pop("_targets")

    rows, status_cache = [], {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def status_of(url):
            if url not in status_cache:
                try:
                    status_cache[url] = page.request.get(url, timeout=30000).status
                except Exception as exc:
                    status_cache[url] = f"error: {exc}"
            return status_cache[url]

        for url, per_faq in link_spec.items():
            print(f"\n{url}")
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1000)

            for i, (question, answer) in enumerate(faqs[url], 1):
                expected = per_faq.get(str(i), [])
                links = page.evaluate(ANSWER_LINKS_JS, compact(answer))
                if links is None:
                    for text in expected:
                        rows.append([url, i, question, text, "", "", "", "ERROR", "Answer not found on page"])
                    continue

                used = set()
                for text in expected:
                    match = next((k for k, l in enumerate(links)
                                  if k not in used and compact(l["text"]) == compact(text)), None)
                    want = targets.get(text, "")
                    if match is None:
                        rows.append([url, i, question, text, want, "", "", "ERROR", "Link missing in answer (plain text or different link text)"])
                        print(f"  ERROR   Q{i} '{text}': link missing")
                        continue
                    used.add(match)
                    href = urljoin(url, links[match]["href"])
                    status = status_of(href)
                    problems = []
                    if not isinstance(status, int) or status >= 400:
                        problems.append(f"target returns {status}")
                    if want and slug(href) != want:
                        problems.append(f"expected /services/{want}/")
                    result = "ERROR" if problems else ("PASS" if want else "WARNING")
                    note = "; ".join(problems) or ("OK" if want else "Target not defined by doc - confirm destination")
                    rows.append([url, i, question, text, want, href, status, result, note])
                    if result != "PASS":
                        print(f"  {result:7} Q{i} '{text}' -> {href} ({note})")

                for k, l in enumerate(links):
                    if k not in used:
                        href = urljoin(url, l["href"])
                        rows.append([url, i, question, l["text"], "", href, status_of(href), "WARNING",
                                     "Extra link in answer - not shown in the FAQ doc"])
                        print(f"  WARNING Q{i} extra link '{l['text']}' -> {href}")

        browser.close()

    out = report_path("faq_link_report.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["page", "faq_number", "question", "link_text", "expected_target",
                    "actual_href", "http_status", "result", "details"])
        w.writerows(rows)

    counts = {k: sum(1 for r in rows if r[7] == k) for k in ("PASS", "WARNING", "ERROR")}
    print(f"\nLinks checked: {len(rows)}  {counts}\nReport: {out}")


if __name__ == "__main__":
    main()
