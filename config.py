import os
import re
from urllib.parse import urlparse


# ============================================================
# WEBSITE UNDER TEST
# ============================================================
#
# Change SITE_URL below to check a different website. Every checker and
# main.py read the website from here - this is the only place to set it.
#
# Every result for that website is stored in its own folder:
#
#   results/<site-name>/
#   ├── pages/        discovered_pages.txt, qa_pages.txt, blog_pages.txt, failed_pages.txt
#   ├── reports/      every *_report.csv
#   └── screenshots/  issue screenshots, grouped by checker
#
# ============================================================

SITE_URL = "https://dev.dotcomdesign.com/eclipse-roofing/"

# Staging hosts serve several sites under one domain, so the first path
# segment names the site there (dev.dotcomdesign.com/eclipse-roofing).
STAGING_HOSTS = {"dev.dotcomdesign.com"}


def site_name(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]

    name = host
    first_segment = parsed.path.strip("/").split("/")[0]
    if host in STAGING_HOSTS and first_segment:
        name = first_segment

    return re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-") or "site"


SITE_NAME = site_name(SITE_URL)

SITE_RESULTS_DIR = os.path.join("results", SITE_NAME)
PAGES_DIR = os.path.join(SITE_RESULTS_DIR, "pages")
REPORTS_DIR = os.path.join(SITE_RESULTS_DIR, "reports")
SCREENSHOTS_DIR = os.path.join(SITE_RESULTS_DIR, "screenshots")

QA_PAGES_FILE = os.path.join(PAGES_DIR, "qa_pages.txt")
DISCOVERED_PAGES_FILE = os.path.join(PAGES_DIR, "discovered_pages.txt")


def report_path(file_name):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return os.path.join(REPORTS_DIR, file_name)
