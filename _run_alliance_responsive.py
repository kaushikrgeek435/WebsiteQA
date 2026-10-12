import csv
import os
from urllib.parse import urlparse

import crawler
import responsive_checker as checker
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.allianceseniorhome.com/"
OUTPUT_DIR = "results/alliance_site_responsive"
CRAWL_DIR = os.path.join(OUTPUT_DIR, "crawl")
REPORT_FILE = os.path.join(OUTPUT_DIR, "all_pages_responsive_report.csv")

os.makedirs(CRAWL_DIR, exist_ok=True)
crawler.RESULTS_DIR = CRAWL_DIR
crawler.ALL_PAGES_FILE = os.path.join(CRAWL_DIR, "discovered_pages.txt")
crawler.QA_PAGES_FILE = os.path.join(CRAWL_DIR, "qa_pages.txt")
crawler.BLOG_PAGES_FILE = os.path.join(CRAWL_DIR, "blog_pages.txt")
crawler.CRAWL_REPORT_FILE = os.path.join(CRAWL_DIR, "crawl_report.csv")
crawler.FAILED_PAGES_FILE = os.path.join(CRAWL_DIR, "failed_pages.txt")

print(f"Discovering pages on {BASE_URL}", flush=True)
crawl_result = crawler.crawl_website(BASE_URL, max_pages=100)
pages = list(dict.fromkeys(
    url for url in crawl_result["all_pages"]
    if not urlparse(url).query
))
print(f"\nAlliance pages to test: {len(pages)}", flush=True)
for url in pages:
    print(f"  {url}", flush=True)

checker.SCREENSHOT_DIR = os.path.join(OUTPUT_DIR, "issue_screenshots")


def detect_document_overflow(page):
    return page.evaluate(
        """() => {
            const root = document.documentElement;
            return {
                viewportWidth: root.clientWidth,
                documentWidth: root.scrollWidth,
                bodyWidth: document.body ? document.body.scrollWidth : 0,
                hasH1: !!document.querySelector('h1'),
                overflowElements: []
            };
        }"""
    )


def wait_for_content(page):
    page.wait_for_load_state("domcontentloaded")
    page.evaluate(
        """async () => {
            if (document.fonts) await document.fonts.ready;
            const step = Math.max(220, Math.floor(innerHeight * 0.5));
            const maxScroll = Math.max(0, document.documentElement.scrollHeight - innerHeight);
            for (let top = 0; top < maxScroll; top += step) {
                window.scrollTo({ top, behavior: 'smooth' });
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
            window.scrollTo({ top: maxScroll, behavior: 'smooth' });
            await new Promise(resolve => setTimeout(resolve, 1200));
            window.scrollTo({ top: 0, behavior: 'smooth' });
            await new Promise(resolve => setTimeout(resolve, 800));
        }"""
    )


def inspect_rendered_page(page):
    return page.evaluate(
        """() => {
            const root = document.documentElement;
            const textElements = [...document.querySelectorAll('h1,h2,h3,p,button,input,textarea,select')];
            const clippedText = textElements.filter(element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0
                    && style.display !== 'none'
                    && style.overflowX !== 'hidden'
                    && style.overflowX !== 'clip'
                    && element.scrollWidth > element.clientWidth + 3;
            }).map(element => ({
                tag: element.tagName,
                text: (element.innerText || element.getAttribute('placeholder') || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
                clientWidth: element.clientWidth,
                scrollWidth: element.scrollWidth
            }));
            const sections = [...document.querySelectorAll('main section, section')]
                .map(section => section.getBoundingClientRect())
                .filter(rect => rect.height > 0)
                .sort((a, b) => a.top - b.top);
            let largestSectionGap = 0;
            for (let i = 1; i < sections.length; i += 1) {
                largestSectionGap = Math.max(largestSectionGap, sections[i].top - sections[i - 1].bottom);
            }
            const images = [...document.images];
            const failedImages = images.filter(image => image.complete && image.naturalWidth === 0).map(image => image.alt || image.src);
            return {
                viewportWidth: root.clientWidth,
                documentWidth: root.scrollWidth,
                horizontalOverflow: root.scrollWidth > root.clientWidth + 2,
                sectionCount: sections.length,
                headingCount: document.querySelectorAll('h1,h2,h3').length,
                imageCount: images.length,
                failedImages,
                clippedText,
                largestSectionGap: Math.max(0, Math.round(largestSectionGap))
            };
        }"""
    )


checker.detect_overflow = detect_document_overflow
checker.wait_for_page_content = wait_for_content
results = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=False)
    page = browser.new_page()
    for page_url in pages:
        print(f"\nChecking page: {page_url}", flush=True)
        for viewport in checker.VIEWPORTS:
            label = f"{viewport['width']}x{viewport['height']}"
            try:
                result = checker.check_viewport(page, page_url, viewport)
            except Exception as exc:
                result = {
                    "page": page_url,
                    "viewport": label,
                    "status": "ERROR",
                    "result": "ERROR",
                    "details": f"{type(exc).__name__}: {exc}",
                    "screenshot": "",
                }
            if result["result"] != "ERROR":
                audit = inspect_rendered_page(page)
                result.update(audit)
                issues = []
                if audit["horizontalOverflow"]:
                    issues.append("document horizontal overflow")
                if audit["failedImages"]:
                    issues.append(f"{len(audit['failedImages'])} failed images")
                if audit["clippedText"]:
                    issues.append(f"{len(audit['clippedText'])} clipped text/control elements")
                if not audit["headingCount"]:
                    issues.append("no headings detected")
                if issues:
                    result["status"] = result["result"] = "WARNING"
                    result["details"] = "; ".join(issues)
                    result["screenshot"] = checker.take_screenshot(page, page_url, viewport["width"], viewport["height"])
                else:
                    result["details"] = (
                        f"Scrolled full page; sections={audit['sectionCount']}, "
                        f"headings={audit['headingCount']}, images={audit['imageCount']}, "
                        f"largest section gap={audit['largestSectionGap']}px"
                    )
            results.append(result)
            print(f"  {label}: {result['result']} - {result['details']}", flush=True)
    browser.close()

with open(REPORT_FILE, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "page", "viewport", "status", "result", "details", "screenshot",
            "viewportWidth", "documentWidth", "horizontalOverflow", "sectionCount",
            "headingCount", "imageCount", "failedImages", "clippedText", "largestSectionGap",
        ],
    )
    writer.writeheader()
    writer.writerows(results)

print(f"\nReport: {REPORT_FILE}", flush=True)
for status in ("PASS", "WARNING", "ERROR"):
    print(f"{status}: {sum(row['result'] == status for row in results)}", flush=True)
