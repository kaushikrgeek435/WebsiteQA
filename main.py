import os

# The website to check is set in config.py (SITE_URL).
from config import REPORTS_DIR, SITE_RESULTS_DIR, SITE_URL

from crawler import (
    crawl_website,
    save_reports
)

from seo_checker import (
    check_seo,
    save_seo_report
)

from image_checker import (
    check_images,
    save_image_report
)

from dead_link_checker import (
    check_dead_links,
    save_dead_link_report
)

from console_checker import (
    check_console,
    save_console_report
)

from network_checker import (
    check_network,
    save_network_report
)

from responsive_checker import (
    check_responsive,
    save_report as save_responsive_report,
    load_pages as load_responsive_pages
)

# ==========================================
# WEBSITE
# ==========================================

START_URL = SITE_URL


# ==========================================
# PHASE 1
# CRAWLER
# ==========================================

print("\n")
print("=" * 60)
print(f"Website : {SITE_URL}")
print(f"Results : {SITE_RESULTS_DIR}")
print("PHASE 1 - WEBSITE CRAWLER")
print("=" * 60)

pages = crawl_website(
    START_URL,
    max_pages=500
)

save_reports(pages)

page_urls = [
    page["url"]
    for page in pages
]

print(
    f"\nPages discovered: "
    f"{len(page_urls)}"
)


# ==========================================
# PHASE 2
# SEO
# ==========================================

print("\n")
print("=" * 60)
print("PHASE 2 - SEO CHECK")
print("=" * 60)

seo_results = check_seo(
    page_urls
)

seo_report = save_seo_report(
    seo_results
)

print(
    f"\nSEO report: {seo_report}"
)


# ==========================================
# PHASE 3A
# IMAGE CHECK
# ==========================================

print("\n")
print("=" * 60)
print("PHASE 3A - IMAGE CHECK")
print("=" * 60)

image_results = check_images(
    page_urls
)

image_report = save_image_report(
    image_results
)

print(
    f"\nImage report: {image_report}"
)


# ==========================================
# PHASE 3B
# DEAD LINK CHECK
# ==========================================

print("\n")
print("=" * 60)
print("PHASE 3B - DEAD LINK CHECK")
print("=" * 60)

dead_link_results = check_dead_links(
    page_urls
)

dead_link_report = (
    save_dead_link_report(
        dead_link_results
    )
)

print(
    f"\nDead link report: "
    f"{dead_link_report}"
)


# ==========================================
# PHASE 3 SUMMARY
# ==========================================

image_pass = 0
image_fail = 0

for result in image_results:

    if result["overall_result"] == "PASS":
        image_pass += 1

    elif result["overall_result"] == "FAIL":
        image_fail += 1


link_pass = 0
link_redirect = 0
link_fail = 0
link_error = 0

for result in dead_link_results:

    if result["result"] == "PASS":

        link_pass += 1

    elif result["result"] == "REDIRECT":

        link_redirect += 1

    elif result["result"].startswith(
        "FAIL"
    ):

        link_fail += 1

    elif result["result"] == "ERROR":

        link_error += 1


print("\n")
print("=" * 60)
print("PHASE 3 SUMMARY")
print("=" * 60)

print("\nIMAGES")

print(
    f"Total images: {len(image_results)}"
)

print(
    f"PASS: {image_pass}"
)

print(
    f"FAIL: {image_fail}"
)


print("\nLINKS")

print(
    f"Total links: {len(dead_link_results)}"
)

print(
    f"PASS: {link_pass}"
)

print(
    f"Redirects: {link_redirect}"
)

print(
    f"Failed: {link_fail}"
)

print(
    f"Errors: {link_error}"
)


print("\nReports:")

print(
    os.path.join(REPORTS_DIR, "image_report.csv")
)

print(
    os.path.join(REPORTS_DIR, "dead_link_report.csv")
)

print("=" * 60)
# ==========================================
# PHASE 6 - RESPONSIVE TESTING
# ==========================================

print("\n")
print("=" * 60)
print("PHASE 6 - RESPONSIVE TESTING")
print("=" * 60)

responsive_pages = load_responsive_pages()
responsive_results = check_responsive(responsive_pages)
responsive_report = save_responsive_report(responsive_results)

print(
    f"\nResponsive report: {responsive_report}"
)

responsive_pass = sum(item["result"] == "PASS" for item in responsive_results)
responsive_warning = sum(item["result"] == "WARNING" for item in responsive_results)
responsive_error = sum(item["result"] == "ERROR" for item in responsive_results)

print("\nRESPONSIVE SUMMARY")
print("=" * 60)
print(f"Total checks: {len(responsive_results)}")
print(f"PASS: {responsive_pass}")
print(f"WARNING: {responsive_warning}")
print(f"ERROR: {responsive_error}")
print("=" * 60)
# ==========================================
# PHASE 4A
# CONSOLE CHECK
# ==========================================

print("\n")
print("=" * 60)
print("PHASE 4A - CONSOLE CHECK")
print("=" * 60)

console_results = check_console(
    page_urls
)

console_report = save_console_report(
    console_results
)

print(
    f"\nConsole report: "
    f"{console_report}"
)

# ==========================================
# PHASE 4B
# NETWORK CHECK
# ==========================================

print("\n")
print("=" * 60)
print("PHASE 4B - NETWORK CHECK")
print("=" * 60)

network_results = check_network(
    page_urls
)

network_report = save_network_report(
    network_results
)

print(
    f"\nNetwork report: "
    f"{network_report}"
)

# ==========================================
# PHASE 4 SUMMARY
# ==========================================

console_errors = 0
console_warnings = 0

for result in console_results:

    if result["result"] == "FAIL":
        console_errors += 1

    elif result["result"] == "WARNING":
        console_warnings += 1


network_failures = 0
network_redirects = 0

for result in network_results:

    result_type = result["result"]

    if result_type.startswith("FAIL"):
        network_failures += 1

    elif result_type == "REDIRECT":
        network_redirects += 1


print("\n")
print("=" * 60)
print("PHASE 4 SUMMARY")
print("=" * 60)

print("\nCONSOLE")

print(
    f"Errors:   {console_errors}"
)

print(
    f"Warnings: {console_warnings}"
)

print("\nNETWORK")

print(
    f"Requests: {len(network_results)}"
)

print(
    f"Failures: {network_failures}"
)

print(
    f"Redirects: {network_redirects}"
)

print("\nReports:")

print(
    os.path.join(REPORTS_DIR, "console_report.csv")
)

print(
    os.path.join(REPORTS_DIR, "network_report.csv")
)

print("=" * 60)