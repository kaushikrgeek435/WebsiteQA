# AGENTS.md

## Project: WebsiteQA

This file is the working context for the WebsiteQA project. Read this file before making changes to the project.

---

## 1. Project Goal

WebsiteQA is a Python + Playwright website QA automation project.

The goal is to automate repetitive website QA checks that are currently performed manually, while keeping the checks practical and useful for real QA work.

Main goals:

- Crawl the website and discover pages.
- Separate approved QA pages from all discovered pages.
- Run SEO checks.
- Check images.
- Check dead links.
- Check browser console errors/warnings.
- Check network failures.
- Check navigation.
- Check buttons.
- Check forms for empty-field validation.
- Check external links.
- Check sliders/carousels.
- Check popups/modals.
- Later add responsive testing.
- Later compare Figma designs against the staging website.
- Later add a QA rule book and consolidated reporting.

Do not unnecessarily redesign the architecture. Prefer small, reliable improvements to the existing modules.

---

## 2. Environment

Operating system:
- Windows
- PowerShell
- VS Code

Project path:
- `C:\Users\Kaushik Geek\Desktop\WebsiteQA`

Python:
- Python 3.13.x

Virtual environment:
- `.venv`

The normal terminal should look similar to:

```text
(.venv) PS C:\Users\Kaushik Geek\Desktop\WebsiteQA>
```

Playwright is installed and Chromium has been installed.

---

## 3. Website Under Test

Staging website:

```text
https://dev.dotcomdesign.com/eclipse-roofing/
```

Base URL:

```python
BASE_URL = "https://dev.dotcomdesign.com"
```

---

## 4. Current Project Structure

```text
WebsiteQA/
├── .venv/
├── results/
├── tests/
├── config.py
├── crawler.py
├── seo_checker.py
├── image_checker.py
├── dead_link_checker.py
├── console_checker.py
├── network_checker.py
├── navigation_checker.py
├── button_checker.py
├── form_checker.py
├── contact_checker.py
├── external_link_checker.py
├── slider_checker.py
├── popup_checker.py
├── main.py
├── requirement.txt
├── test_phase4.py
└── AGENTS.md
```

---

### Per-website results folder

`SITE_URL` in `config.py` is the single place that sets the website under test; all checkers and
`main.py` read it. Everything is stored under `results/<site-name>/` (`pages/` page lists,
`reports/` CSVs, `screenshots/<checker>/`).
RULE: when the user gives a website URL to check, update `SITE_URL` in `config.py` first. Paths below written as `results/x` mean
`results/<site-name>/pages/x` (txt) or `results/<site-name>/reports/x` (csv).
Figma output (`results/figma_comparison/`) and `_run_alliance_responsive.py` are not migrated yet.

---

## 5. Important Scope Rule

There are two different page scopes.

### QA page scope

Normal QA checks use:

```text
results/qa_pages.txt
```

This contains only approved Figma/QA pages.

Current target:

```text
14 QA pages
```

### Whole-site scope

Dead-link/discovery checks use:

```text
results/discovered_pages.txt
```

This contains all discovered pages.

Current crawler result:

```text
111 discovered pages
```

Do NOT accidentally use `qa_pages.txt` for whole-site dead-link checking.

Do NOT automatically treat every discovered blog detail page as a normal QA page.

---

## 6. Current QA Pages

The approved QA page paths are:

```python
QA_PAGE_PATHS = {
    "/eclipse-roofing",
    "/eclipse-roofing/roof-installation",
    "/eclipse-roofing/services/metal-roofing",
    "/eclipse-roofing/services/asphalt-roofing-manheim-pa",
    "/eclipse-roofing/services/cedar-shingle-roofing-manheim-pa",
    "/eclipse-roofing/services/rubber-roofing",
    "/eclipse-roofing/about-us",
    "/eclipse-roofing/portfolio",
    "/eclipse-roofing/reviews",
    "/eclipse-roofing/blog",
    "/eclipse-roofing/contact-roofing-contractor",
    "/eclipse-roofing/get-a-quote",
    "/eclipse-roofing/service-area",
    "/eclipse-roofing/roof-installation-in-denver-pa-what-homeowners-should-know",
}
```

The approved blog detail page is:

```text
https://dev.dotcomdesign.com/eclipse-roofing/roof-installation-in-denver-pa-what-homeowners-should-know
```

Portfolio filter URLs such as:

```text
/portfolio?term=8
/portfolio?term=9
/portfolio?term=10
/portfolio?term=11
```

are NOT separate QA pages.

Query-string URLs should not become QA pages.

---

## 7. Crawler Rules

The crawler should:

1. Normalize URLs.
2. Remove trailing slash differences.
3. Exclude query-string pages from QA scope.
4. Discover all internal pages.
5. Save all discovered pages.
6. Save only approved QA pages separately.
7. Identify blog detail pages.
8. Save crawl failures.

Expected result:

```text
results/discovered_pages.txt
results/qa_pages.txt
results/blog_pages.txt
results/crawl_report.csv
results/failed_pages.txt
```

Target summary:

```text
All discovered pages : 111
QA pages             : 14
Blog detail pages    : 1
Failed pages         : 0
```

If the actual current run differs, trust the latest terminal output instead of assuming these numbers are still current.

---

## 8. Phase Status

### Phase 1 - Crawler

Status: DONE

Responsibilities:
- Discover internal pages.
- Normalize URLs.
- Separate QA pages from all discovered pages.
- Identify blog detail pages.

---

### Phase 2 - SEO

Status: DONE

SEO checks are part of the existing project.

Do not remove existing checks unless there is a clear reason.

---

### Phase 3A - Image Checker

Status: DONE

Image QA is already implemented.

---

### Phase 3B - Dead Link Checker

Status: FUNCTIONALLY DONE

Important rule:

Dead-link testing should use:

```text
results/discovered_pages.txt
```

because dead links need whole-site coverage.

Do not restrict dead-link testing to only the 14 QA pages.

---

### Phase 4A - Console Checker

Status: DONE

Checks browser console messages.

Output:

```text
results/console_report.csv
```

The checker should capture:
- console errors
- console warnings

---

### Phase 4B - Network Checker

Status: DONE

Checks:
- requests
- responses
- HTTP status
- duration
- network failures
- redirects

Output:

```text
results/network_report.csv
```

Important:

The website can contain Cloudflare or other resources that prevent `networkidle` from completing.

Prefer:

```python
wait_until="domcontentloaded"
```

instead of depending on `networkidle`.

---

### Phase 5A - Navigation Checker

Status: DONE

Previous successful result:

```text
Navigation links checked: 6
Passed: 6
Redirects: 0
Failures: 0
Errors: 0
Mobile menu click: PASS
```

---

### Phase 5B - Button Checker

Status: DONE

Previous successful result:

```text
Buttons checked: 1
Passed: 1
Warnings: 0
Failures: 0
Errors: 0
```

Example:

```text
Get a Free Estimate -> PASS
```

The checker should avoid risky/unwanted clicks such as:
- submit buttons
- reset buttons
- mailto
- tel
- javascript links
- dangerous/destructive actions
- form submission

---

### Phase 5C-1 - Form Empty Validation

Status: DONE

The checker found:
- 1 visible form
- 9 fields
- 3 required fields

Required fields included:
- full-name
- phone
- desiredService

Empty submission correctly detected validation messages.

Form filling/submission is intentionally NOT handled by this project.

The user has a separate Chrome extension for form testing.

Do not add automatic real form submission unless explicitly requested.

Do not use the user's personal name as dummy test data.

---

### Phase 5D - Phone/Email

Status: SKIPPED

Do not spend time on this unless explicitly requested.

---

### Phase 5E - External Links

Status: PARTIAL / CAN BE REVISITED

If this phase is improved, make the scope clear.

For whole-site external-link validation, use the appropriate all-discovered-page source when requested.

---

### Phase 5F - Slider / Carousel Checker

Status: CURRENT

This is the current development focus.

The website contains a testimonial slider on the homepage.

The relevant section is:

```text
See What Our Customers Are Saying
```

It displays multiple testimonial cards simultaneously and has:

- previous arrow
- next arrow
- pagination dots

The slider must be tested as an actual interactive component.

Do NOT only check whether a CSS class such as `.swiper` exists.

The important QA behavior is:

```text
Click Next
    ↓
Visible slider content should change

Click Previous
    ↓
Visible slider content should change

Click pagination
    ↓
Visible slider content should change
```

Because multiple testimonial cards can be visible at once, compare visible content/state rather than relying only on an `active-slide` class.

Current output:

```text
results/slider_report.csv
```

The slider checker should use:

```text
results/qa_pages.txt
```

because normal component QA is performed on approved QA pages.

Potential slider technologies/classes may include:
- Elementor carousel
- Swiper
- Slick
- Splide
- Owl
- custom testimonial carousel
- custom slider markup

Do not assume the exact library without inspecting the DOM.

Avoid clicking unrelated arrows elsewhere on the page.

A candidate slider should ideally have:
- repeated slide/card content
- navigation controls and/or pagination
- meaningful visible content

---

### Phase 5G - Popup / Modal

Status: NEXT

After Phase 5F is stable, implement popup/modal testing.

Possible checks:
- popup opens
- popup closes
- close button works
- overlay behavior
- Escape key if supported
- no broken/empty popup
- no accidental navigation

---

### Phase 6 - Responsive Testing

Status: IN PROGRESS (overflow/cut-off check + menu-per-breakpoint check stable)

Module: `responsive_checker.py` -> `results/responsive_report.csv` (uses `qa_pages.txt`).
Quick run: `python responsive_checker.py --viewports 320,768,1440`

Current check (per page x viewport):
- ERROR: page scrolls horizontally.
- WARNING: visible text/media/controls cut off at the viewport edge (screenshot with red outline saved).
- Ignored by design: content clipped inside an on-screen overflow container (sliders), fully off-screen
  elements (closed off-canvas mobile menu), wrapper boxes with negative margins, media bleeding <= 8px.
- Note: the site sets `overflow-x: hidden` on html/body, so documentWidth never exceeds the viewport;
  real overflow appears only as cut-off content.

Menu per breakpoint (columns `menu_mode`, `menu_button_visible`, `nav_links_visible`, `mobile_menu_opens`):
- <= 767px expects the mobile menu button; >= 1280px expects desktop nav links; 768-1279 either is OK.
- When the menu button is shown, it is clicked and nav links must become visible (else ERROR).
- ERROR: no navigation visible at all. WARNING: wrong style for the width, or button + desktop links both shown.
- The console prints a per-page "MENU BREAKPOINTS" summary.
- Eclipse Roofing: mobile menu 320-900, desktop menu 1024-2560 on all 13 pages; the button opens the menu (6 links).

Full-page screenshots (for Phase 7): `python responsive_checker.py --full-screenshots`
-> `results/responsive_screenshots/full_page/<page>/<width>.png` (~630 MB for all 14 pages x 24 widths).

Page loading scrolls screen by screen so scroll-reveal (wow.js) sections become visible;
the old 4-jump scroll left whole homepage sections blank and unmeasured.

QA scope is now 14 pages (approved blog detail page added to crawler `QA_PAGE_PATHS`).

Last full run before the scroll fix (14 pages x 24 viewports = 336 checks): 336 PASS.
PENDING (2026-10-09): verification run after the scroll fix was started. On Monday, review
`results/responsive_report.csv` and spot-check full-page screenshots; if clean, mark Phase 6 DONE.

Later test important viewport sizes.

The project should support checking multiple widths, including approximately:

```text
320
375
390
414
768
1024
1280
1366
1440
1536
1728
1920
2560
```

The exact list may later be driven by the Figma designs.

---

### Phase 7 - Figma vs Staging

Status: DONE (desktop + mobile/tablet frames whenever the Figma file has them; verified on alliance and sonrise)

Runs standalone - intentionally NOT wired into `main.py`. Connect it only in Phase 9
(final report), after all phases are completed, as an optional step for projects with a Figma setup.

Module: `figma_checker.py` (Figma REST API + Playwright). Needs `$env:FIGMA_TOKEN`.
Figma frame JSON/PNG are cached in `results/figma_comparison/`; use `--refresh` to re-download.
Output: `results/figma_comparison/<project>/element_comparison.csv` (+ screenshots, diff images, Figma cache)
- one folder per project in `figma_pages.json`. Projects: `alliance`, `sonrise` (SonRise Coffee - only
Home is built on staging; checked against desktop 1728 + mobile 360 frames).
Pages compared: `figma_pages.json` (per project: Figma file URL, staging base URL, frame node -> path).
Currently configured: `alliance` - Home `/`, Contact Us `/contact`, Assisted Living `/assisted-living`,
Senior Care Program `/senior-care-program` (desktop 1920 frames only; no mobile frames in the file).
`python figma_checker.py` runs the default project; `--project <name>` picks another;
`--figma-url` + `--staging-url` checks a single frame.
Mobile/tablet designs: a page may list `"frames": {"desktop": "<node>", "tablet": "<node>", "mobile": "<node>"}`
instead of `"node"`. Each frame is compared at its own Figma width (e.g. a 390px frame -> 390px browser).
Every run also scans the Figma file and automatically checks unlisted page-sized frames
(300-1199px wide, >=1000px tall) whose name contains a configured page name (e.g. "Home - Mobile").
RULE: if Figma has a mobile/tablet version of a page, it must be checked too.
Page-level checks: `section_order` (sections in design order) and `unexpected_content`
(visible staging text with no counterpart in the design; INFO where the design uses lorem ipsum).
Checks: text presence/wording, typography, text colour, x position, box styles of the painted
container around each text (`box-background/border/radius/shadow/width/height/padding`), and
`spacing-below` between adjacent stacked texts. Known non-issues handled: next/font renamed families,
current-page nav highlight, Figma lorem ipsum, invisible same-colour borders, photo banners.
Visual diff (`figma_visual_diff.py`, needs Pillow): per Figma section, aligned to staging via matched
text + best-offset search; `visual-diff` rows (WARNING when >=5% of pixels changed) and a
Figma | Staging | Diff image per page at `results/figma_comparison/visual_diff_<page>.png`.
Small changes (icons, arrows, badges) are reported as "localized changes" (32px tiles, must survive
+/-8px shifts so moved text is not counted) and boxed in orange on the diff image.
Staging is measured after an instant scroll-to-top (site uses smooth scroll + sticky header).

Future goal:

Compare Figma design with the staging website.

Potential integration:
- Figma MCP
- browser/DevTools tooling
- Playwright screenshots
- viewport-specific comparison

Checks may include:
- layout
- spacing
- typography
- colors
- images
- buttons
- section order
- responsive behavior
- missing sections
- unexpected sections

Do not build this phase until the lower-level website QA checks are stable.

---

### Phase 8 - QA Rule Book

Status: TODO

Create a rule system for repeatable QA standards.

Rules may include:
- exactly one H1
- required metadata
- broken links
- image failures
- console errors
- network failures
- missing buttons
- slider behavior
- popup behavior
- responsive issues
- Figma mismatches

The rule book should produce clear issue descriptions.

---

### Phase 9 - Reporting

Status: TODO

When building this phase (after all other phases are completed), connect Phase 7
`figma_checker.py` to `main.py` / the final report as an optional step: run it only when the
project has an entry in `figma_pages.json` and `FIGMA_TOKEN` is set, and include
`results/figma_comparison/element_comparison.csv` in the consolidated report.

Eventually create a consolidated report.

Possible outputs:

```text
results/
├── crawl_report.csv
├── seo_report.csv
├── image_report.csv
├── dead_link_report.csv
├── console_report.csv
├── network_report.csv
├── navigation_report.csv
├── button_report.csv
├── form_report.csv
├── external_link_report.csv
├── slider_report.csv
└── final_qa_report.csv
```

Future reporting may also include:
- screenshots
- failed URLs
- severity
- issue description
- expected result
- actual result
- QA status

---

## 9. Coding Rules

Use Python + Playwright.

Prefer synchronous Playwright unless the existing module requires async.

Use:

```python
from playwright.sync_api import sync_playwright
```

Prefer:

```python
page.goto(url, wait_until="domcontentloaded")
```

over:

```python
page.goto(url, wait_until="networkidle")
```

because the staging website may contain Cloudflare or continuously loading resources.

Use reasonable timeouts.

Do not make tests unnecessarily slow.

Use explicit waits only where needed.

Prefer stable selectors:
1. IDs
2. data attributes
3. accessible roles/labels
4. stable classes
5. carefully designed CSS
6. XPath only when necessary

Avoid brittle selectors based on deeply nested DOM paths.

---

## 10. Reporting Rules

Each checker should produce a CSV inside:

```text
results/
```

Use clear statuses:

```text
PASS
WARNING
ERROR
INFO
```

Definitions:

### PASS

The expected behavior was verified.

### WARNING

The checker found something that needs review, but it could not confidently classify it as a hard failure.

### ERROR

The expected behavior failed or the test itself encountered a serious execution problem.

### INFO

No applicable component/check was found, or the record is informational.

Do not mark a page as ERROR merely because a particular component does not exist when that component is optional.

---

## 11. QA Philosophy

This project is intended to automate useful QA work, not generate noisy false positives.

Prefer:

```text
high confidence + useful evidence
```

over:

```text
lots of warnings + uncertain results
```

When detection is uncertain:
- investigate the DOM
- improve the selector
- compare actual behavior
- use WARNING when appropriate

Do not silently assume that a detected element is the component being tested.

---

## 12. Existing Chrome Form Checker

There is a separate Chrome extension project/workflow for automated form testing.

Its responsibilities include:
- detecting forms
- identifying required fields
- clicking submit
- filling dummy data
- handling terms/acceptance checkboxes
- detecting success messages
- handling thank-you redirects
- detecting CAPTCHA/Cloudflare states

This is separate from the WebsiteQA Playwright form checker.

Do not duplicate the full Chrome extension workflow inside WebsiteQA unless explicitly requested.

---

## 13. Future Integration

The long-term system may combine:

```text
Crawler
   ↓
QA Page Scope
   ↓
Website QA Checkers
   ├── SEO
   ├── Images
   ├── Dead Links
   ├── Console
   ├── Network
   ├── Navigation
   ├── Buttons
   ├── Forms
   ├── External Links
   ├── Sliders
   └── Popups
   ↓
Responsive Testing
   ↓
Figma vs Staging
   ↓
QA Rule Book
   ↓
Final Report
```

Possible future tooling:

```text
Python
Playwright
Figma MCP
Chrome DevTools / browser tooling
Google Sheets
```

---

## 14. Important Working Agreement

Before changing a file:

1. Read the relevant existing file.
2. Check how it currently works.
3. Preserve working behavior.
4. Make the smallest reasonable change.
5. Run the relevant checker.
6. Review the generated CSV/report.
7. Fix false positives before adding more checks.

When a test fails, distinguish between:

```text
Website failure
vs
Automation failure
```

Do not automatically report an automation problem as a website bug.

---

## 15. Current Next Step

Current phase:

```text
Phase 5F - Slider / Carousel Checker
```

The immediate target is the homepage testimonial slider:

```text
See What Our Customers Are Saying
```

The checker must verify actual interaction with:
- Next
- Previous
- pagination dots

Then continue to:

```text
Phase 5G - Popup / Modal Checker
```

Do not jump to Figma comparison until the basic website QA phases are stable.

---

## 16. Useful Commands

Activate virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

Run crawler:

```powershell
python crawler.py
```

Run slider checker:

```powershell
python slider_checker.py
```

Inspect non-INFO slider results:

```powershell
Import-Csv results\slider_report.csv | Where-Object {$_.result -ne "INFO"} | Format-Table page,slider_number,slides,next,previous,pagination,result -AutoSize
```

Inspect detailed slider results:

```powershell
Import-Csv results\slider_report.csv | Where-Object {$_.result -ne "INFO"} | Select-Object page,slider_number,slides,next,previous,pagination,result,details | Format-List
```

---

## 17. Instructions for Codex / VS Code Agent

When continuing this project:

- Read `AGENTS.md` first.
- Inspect existing files before editing them.
- Do not overwrite unrelated working modules.
- Do not remove existing functionality without a reason.
- Keep QA scope rules intact.
- Remember that `qa_pages.txt` and `discovered_pages.txt` have different purposes.
- Ask for clarification only when an important requirement is genuinely ambiguous.
- Prefer implementing and testing a small change rather than rewriting the entire project.
- Report what files were changed and how the result was verified.
