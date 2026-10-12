import os

from config import REPORTS_DIR, SITE_URL

from console_checker import (
    check_console,
    save_console_report
)

from network_checker import (
    check_network,
    save_network_report
)


# Use ONE page for testing
TEST_URL = SITE_URL


pages = [TEST_URL]


print("\n")
print("=" * 60)
print("       PHASE 4 TEST")
print("=" * 60)


# ==========================================
# PHASE 4A - CONSOLE
# ==========================================

print("\n")
print("=" * 60)
print("PHASE 4A - CONSOLE CHECK")
print("=" * 60)

console_results = check_console(pages)

console_report = save_console_report(
    console_results
)

print("\nConsole report:")
print(console_report)


# ==========================================
# PHASE 4B - NETWORK
# ==========================================

print("\n")
print("=" * 60)
print("PHASE 4B - NETWORK CHECK")
print("=" * 60)

network_results = check_network(pages)

network_report = save_network_report(
    network_results
)

print("\nNetwork report:")
print(network_report)


# ==========================================
# SUMMARY
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

    if result["result"].startswith("FAIL"):
        network_failures += 1

    elif result["result"] == "REDIRECT":
        network_redirects += 1


print("\n")
print("=" * 60)
print("             PHASE 4 TEST SUMMARY")
print("=" * 60)

print(
    f"Console errors:    {console_errors}"
)

print(
    f"Console warnings:  {console_warnings}"
)

print(
    f"Network requests:  {len(network_results)}"
)

print(
    f"Network failures:  {network_failures}"
)

print(
    f"Network redirects: {network_redirects}"
)

print("\nReports created:")

print(
    os.path.join(REPORTS_DIR, "console_report.csv")
)

print(
    os.path.join(REPORTS_DIR, "network_report.csv")
)

print("=" * 60)