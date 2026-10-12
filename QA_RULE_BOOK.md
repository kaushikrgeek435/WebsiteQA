# QA Rule Book

Phase 8. Each rule comes from a real issue found during manual QA.
Status per rule: whether an automated checker covers it yet.

---

## Responsive rules

### RESP-01 - Slider/carousel arrows must stay vertically centered on their track

- **Applies to:** any slider, carousel or thumbnail strip with prev/next arrows, at every viewport.
- **Expected:** the arrow's vertical center lines up with the vertical center of the slide/thumbnail
  row it controls (tolerance: 4px). Arrows must not overlap the slides they control.
- **Fail (WARNING):** an arrow drops below (or rises above) the center of its row by more than 4px,
  or overlaps a visible slide.
- **How to verify:** measure `getBoundingClientRect()` of the arrow and of the slider track
  (e.g. the `.swiper` container); compare centers; check horizontal overlap with each visible slide.
- **Example:** handhole.com product page (`/handhole-product/polymer-concrete-17-30-24/`),
  760px - product thumbnail arrows reported sitting lower than the thumbnail row's center.
  Re-check on 2026-10-12 (load at 375/760/1024/1440 and resize 1440 -> 760): arrows centered
  within 3px - could not reproduce; likely already fixed or state-dependent.
- **Automated:** not yet (planned for `responsive_checker.py`).

### RESP-02 - Button text must stay on one line at every viewport

- **Applies to:** every visible button and button-styled link (`button`, `input[type=submit|button]`,
  `.button`, `.btn`, `[role=button]`, WooCommerce `.wc-forward`, Elementor `.elementor-button`), at every viewport.
- **Expected:** the label renders on a single line; the button grows/shrinks or moves to its own row instead.
- **Fail (WARNING):** the label wraps to 2+ lines.
- **How to verify:** count text line boxes of the label (`Range.getClientRects()` distinct `top` values),
  or button content height > 1.5 x computed `line-height`. Skip icon-only buttons and hidden ones.
- **Example:** clubfootsolutions.org `/cart/`, ~1230px - "View cart" button in the WooCommerce
  "added to your cart" notice wraps to "View / cart". (Seen in screenshot; needs an item in the cart to reproduce.)
- **Automated:** not yet (planned for `responsive_checker.py`).

### RESP-04 - Desktop menus (header and footer) must stay on one line

- **Applies to:** header nav and footer nav at every desktop width (>= 1024px, and any width where the
  desktop-style menu is shown instead of the hamburger).
- **Expected:** all top-level menu links sit on one row; no item drops to a second line.
- **Fail (WARNING):** top-level links occupy 2+ rows (distinct `top` positions), or a single link's label wraps.
- **How to verify:** collect visible top-level `nav > ul > li > a` (exclude sub-menus/dropdowns) in header and
  footer; group by rounded `top`; more than one group = wrapped. Test with a real scrollbar too - DevTools
  "1022px" leaves ~1007px of content width, so test around breakpoints minus ~15px.
- **Example:** jbroofingkalona.com footer, 1022px (DevTools, scrollbar visible) - "CONTACT" dropped to a
  second row. Re-check on 2026-10-12 at 1000-1920px: footer menu on one row - could not reproduce;
  likely fixed or font-load dependent.
- **Automated:** not yet (`responsive_checker.py` checks which menu is shown, not whether it wraps).

### RESP-05 - No unexpected empty space on smaller screens

- **Applies to:** every page at tablet/mobile widths (<= 1023px).
- **Expected:** vertical spacing between blocks follows the design (similar rhythm to desktop, scaled down).
  No blank white bands left by hidden/empty elements, fixed heights, or desktop-only spacers.
- **Fail (WARNING):** a blank band (no text, image, video, button, background image) taller than ~60px
  inside a single section (same background), or noticeably taller than the same gap at desktop.
- **Not a failure:** normal section padding where the background changes between sections
  (e.g. white section -> grey section), or a design gap that also exists at desktop.
- **How to verify:** list visible content boxes (text line rects, media, buttons, background images) sorted by
  `top`; report blank bands; ignore bands that span a section/background change; compare with desktop.
  Load lazy images first (scroll the page) so not-yet-loaded images are not counted as empty space.
- **Example:** udccorporation.com `/about/`, 326px - large blank gaps under the header, between the photo
  and "ESTABLISHED 1984", and between "Who We Are" and "Our History". Re-check on 2026-10-12 at 326px:
  gaps now ~51px (under header, same as desktop where the logo overhangs) and ~41px - not reproduced at the
  reported size; possibly fixed, or screenshot taken before lazy-loaded images appeared.
- **Automated:** not yet - needs section/background awareness first to avoid flagging normal section padding.

### RESP-06 - Floating/positioned elements must not overlap buttons or text

- **Applies to:** absolutely/fixed positioned elements - "SCROLL" indicators, scroll-down arrows, badges,
  decorative lines, sticky bars - at every viewport, especially short/medium heights where hero content
  grows taller than the hero.
- **Expected:** positioned elements sit in free space; they move or hide when content needs the room.
- **Fail (WARNING):** a positioned element's text/box intersects a visible button or text line (> 2px).
- **How to verify:** for each visible `position: absolute|fixed` element with text or a visible box, compare its
  rect (and its text line rects) with every visible button and text line rect in the same section.
  Ignore the element's own children/parents, the site header, and intentional overlays (slider arrows over
  images, badges on images).
- **Example:** wildwondersphotography.net home hero, 900x858 - the "SCROLL" indicator text and its line
  sit on top of the "DO NOT SCREENSHOT PHOTOS!!!" button.
  Also 3dfloorscapes.com `/careers/`, 594px - sticky "CONTACT US" bar covers the "Last Name" input
  (acceptable only if the page leaves bottom space so the field can be scrolled clear of it).
- **Automated:** not yet (RESP-03 only checks text next to a button inside the same block).

### RESP-07 - Form validation messages must not overlap fields, labels or each other

- **Applies to:** every form with required fields, at every viewport, after an empty submit
  (same empty-submit step `form_checker.py` already does - no real data is submitted).
- **Expected:** each message sits fully below (or beside) its own field, on its own line(s); fields,
  placeholders, labels and other messages stay readable; the layout grows to make room.
- **Fail (WARNING):** a message's text rect intersects its input/select, another field's label, or another
  message (> 2px); or the message wraps inside a field too narrow to hold it.
- **How to verify:** empty-submit the form, wait for messages (`.wpcf7-not-valid-tip`, `.error`,
  `[class*=invalid]`, `[role=alert]`, `[aria-live]`), then compare each message's text line rects with every
  visible input/select/textarea and label rect and with other messages.
- **Example:** dandrpestcontrol.com `/careers/`, 1156px - City / State / Zip are squeezed into narrow columns;
  "The field is required." wraps to 2 lines and the first line sits inside the input over the placeholder,
  and the second line runs into the "Telephone Number*" label below.
- **Automated:** not yet (needs the form empty-submit step; responsive checker does not submit forms).

### RESP-08 - Font sizes must scale properly - not too big, not too small

- **Applies to:** headings (H1-H3, hero/banner titles) and body text, at tablet and mobile widths.
- **Expected:** text gets smaller as the screen gets smaller; it never stays at (or grows above) its desktop
  size; a hero title fits comfortably in its banner.
- **Fail (WARNING):** any of:
  - a heading's font-size at <= 1023px is >= its font-size at desktop (1440px);
  - font-size too big for the width - guide limits: H1 > 56px at 768-1023px, H1 > 40px at <= 767px,
    H2 > 44px / 32px, body text > 20px at <= 767px (limits can later come from Figma mobile frames);
  - a short heading (<= 4 words) breaks into one word per line, or the title fills > 80% of its banner height;
  - text too small to read: readable text (paragraphs, card/testimonial text, labels, links, buttons)
    < 14px at <= 767px (< 12px anywhere); fine print/captions may go to 12px. Text inside real images/
    screenshots is not checked (it is an image, not HTML text).
- **How to verify:** read `getComputedStyle(el).fontSize` for visible H1-H3/hero titles at each width and
  compare with the same element at 1440px; count heading lines via `Range.getClientRects()`; compare
  heading height with its banner/section height; flag visible text nodes with computed font-size under the
  minimum.
- **Example (too small):** staging.digitalboostia.com `/educredservices/`, 320x568 - hero chat-bubble cards
  ("A measurable mission drives institutional planning...", "Your Strategic Plan provides a strong...") use
  ~9-10px text - unreadable on a phone.
- **Example (too big):** openroaddrivingschool.com `/new-tesla-time/`, 796px - hero title "New Tesla Time" is about
  90px tall, breaks to two lines and fills almost the whole banner image.
- **Automated:** not yet.

### RESP-09 - No excessive side padding on smaller screens

- **Applies to:** main content blocks (text, forms, cards) at tablet and mobile widths.
- **Expected:** content uses the available width; side gutters shrink with the screen
  (guide: ~16-24px at <= 767px, ~24-48px at 768-1023px).
- **Fail (WARNING):** any of:
  - a text/form block at <= 767px is narrower than ~70% of the viewport while nothing sits beside it;
  - left or right gap from the viewport edge to the content > 48px at <= 767px (> 80px at 768-1023px);
  - content is narrower at a wider screen than at a smaller one (desktop padding kicking in too early);
  - uneven sides: left gap and right gap differ by > 2x for centered content, or a block is indented far
    from its own section heading (e.g. text starts ~180px right of the heading above it).
- **How to verify:** for visible paragraphs, headings, form fields and cards, take
  `getBoundingClientRect()` left/right gaps to the viewport; check that the empty side area has no other
  content (not a 2-column layout); compare content width across widths (e.g. 375 / 594 / 768).
- **Example:** 3dfloorscapes.com `/careers/`, 594px - text and form squeezed into a ~310px column with
  ~140px of empty space on each side; words wrap almost every line and form fields are too narrow.
  Also nofoottoosmall.org `/families/moms-groups/`, 970px - "Meeting Options" content sits in a ~330px column
  with ~240px empty on the left and ~320px on the right, starting ~180px right of its "Meeting Options" heading.
- **Automated:** not yet.

### RESP-10 - Content must not touch the edge of its box/card

- **Applies to:** buttons, text and images inside cards, banners, colored boxes and bordered containers,
  at every viewport.
- **Expected:** keep inner spacing (padding) on every side - guide: at least ~16px between a child and the
  edge of a box that has a visible background, border or shadow; the bottom gap should match the top/side gaps.
- **Fail (WARNING):** a visible child (button, text, image) touches or sticks to an edge of its painted box -
  gap < 8px - or the box's bottom is cut right at the child (button sitting flush on the bottom edge).
- **How to verify:** for each element with a visible background/border/shadow, compare its rect with the rects
  of its visible children (buttons, text lines, images); report the smallest gap per side; skip full-bleed
  images/backgrounds that are meant to touch the edge.
- **Example:** dandrpestcontrol.com `/careers/`, 969px - in the green "APPLICATION FOR EMPLOYMENT" card the
  "APPLICATION FORM" button sits right on the bottom edge of the card (no bottom padding), while the card has
  ~30px padding on the other sides.
- **Automated:** not yet.

### RESP-11 - Icon and its text must share the same alignment

- **Applies to:** feature/service lists, icon boxes, info cards - any icon/image paired with a title or text,
  at every viewport (especially when columns stack on tablet/mobile).
- **Expected:** icon and label use the same alignment - both centered (icon centered above centered text) or
  both left-aligned; icons in a stacked list line up with each other.
- **Fail (WARNING):** any of:
  - icon center and text center differ by > 8px while the text is centered (or icon left edge and text left
    edge differ by > 8px while the text is left-aligned);
  - icons in the same list/group have different left positions or different centers;
  - icons of the same group differ noticeably in size (> 25%).
- **How to verify:** for each icon (`img`, `svg`, `i[class*=icon]`, `.elementor-icon`, small images <= 150px)
  find its title/text sibling; compare horizontal centers and left edges using `getBoundingClientRect()` and
  the text's `text-align`; compare icon rects within the same parent list.
- **Example:** zenlordpro.com `/features/collect-rent/`, 728px - the 4 feature icons (house, cards, umbrella,
  shield) are left-aligned while their labels ("Easy, Automated ACH", "NSF Protection", ...) are centered,
  so every icon sits off to the left of its text.
- **Automated:** not yet.

### RESP-12 - Embeds and media must render - no empty boxes

- **Applies to:** iframes (Google Maps, YouTube/Vimeo, forms, calendars, social feeds), images, background
  images and sliders, at every viewport.
- **Expected:** every reserved media/embed area shows its content at every width and scales to the column
  (no fixed desktop width/height that breaks on smaller screens).
- **Fail (WARNING):** a visible area >= 100px tall that is empty - e.g. an iframe with no/blank content,
  a bordered box with nothing inside, an image that failed to load or has 0 natural size, a lazy-loaded
  element that never loaded after scrolling. ERROR when the embed URL itself fails (4xx/5xx, blocked).
- **How to verify:** after scrolling the whole page (lazy load), check each iframe's `src` is set and loads,
  each `img` has `complete && naturalWidth > 0`, and that bordered/background boxes >= 100px tall contain
  visible children; compare with the same page at desktop (if the content shows there but not here, the
  responsive styles hide or break it). Screenshot the empty area.
- **Example:** navyleagueoc.org `/about/`, 710px - below the "Write to:" address there is a ~360px empty
  dark area and below it an empty white-bordered box (likely map / embed not rendering at this width).
  Re-check on 2026-10-12: not possible - the site now redirects to the host's "Account Suspended" page and
  its SSL certificate has expired.
- **Automated:** partly - `image_checker.py` covers broken images; empty embed/box detection not yet.

### RESP-13 - Line height must be enough so wrapped lines never touch

- **Applies to:** all multi-line text - headings, buttons, paragraphs - at every viewport (headings wrap more
  on smaller screens, so a tight line-height that looked fine on one line breaks here).
- **Expected:** line-height >= ~1.1 x font-size for headings and >= ~1.4 x for body text; letters of one line
  never touch or overlap the line above/below; uneven line spacing inside one heading should not happen.
- **Fail (WARNING):** any of:
  - computed `line-height` < 1.0 x `font-size` on text that wraps to 2+ lines;
  - two consecutive line boxes overlap or are spaced closer than the font-size (letters touching);
  - line spacing inside one heading is uneven (gap between lines differs by > 30%, e.g. a `<br>` line vs a
    wrapped line).
- **How to verify:** for visible text elements that wrap, read `getComputedStyle` `fontSize` / `lineHeight`;
  get line rects via `Range.getClientRects()` and compare consecutive line tops/bottoms.
- **Example:** prullcustomdesigns.com home, 944px - heading "Are you ready to have your dream home designed by
  Prull Custom Designs?" wraps; "designed by" sits directly under the first line with the letters touching /
  overlapping ("Are" over "des..."), while the gap to "Prull Custom Designs?" is much larger - line-height too
  tight and uneven.
- **Automated:** not yet.

### RESP-14 - Hero/banner height must fit its content on smaller screens

- **Applies to:** hero sections and inner-page title banners (page title + breadcrumb), mainly at
  tablet/mobile widths.
- **Expected:** the banner height follows its content - padding above and below the content roughly equal and
  modest (guide: <= ~60px each side on mobile, <= ~100px on tablet). A banner with only a title/breadcrumb
  should be short; desktop `min-height`/fixed `height` (e.g. 400px, 100vh) should not carry over to mobile.
- **Fail (WARNING):** any of:
  - empty space above or below the hero content > ~60px on <= 767px (> ~100px on 768-1023px);
  - content takes < 40% of the hero height on mobile (hero mostly empty);
  - top and bottom empty space differ by > 2x when content is meant to be centered.
- **How to verify:** find the first large section after the header (or `[class*=hero]`, `[class*=banner]`,
  `.page-header`, `.elementor-section` with background); measure its rect vs the union of its visible
  text/button rects; read `min-height`/`height` from computed style to report the cause.
- **Example:** staging.digitalboostia.com `/iowaheartsafe/about/`, 320x568 - inner-page banner "About Us" +
  breadcrumb "HOME >> ABOUT US" sits in a ~320px tall banner with ~120px empty above and ~120px empty below;
  the banner should shrink to fit the title.
- **Automated:** not yet.

### RESP-15 - Spacing between stacked cards must be suitable and consistent

- **Applies to:** cards/boxes/columns that stack vertically on tablet and mobile (services, features, team,
  testimonials, blog cards), checked especially at the smallest width (320x568).
- **Expected:** the gap between two stacked cards is comfortable and the same for every pair - guide:
  ~16-32px on mobile, ~24-40px on tablet - measured from the card's **visual** edge, including any decorative
  offset shadow/bar under the card, so the shadow of one card never crowds or touches the next card.
- **Fail (WARNING):** any of:
  - gap between consecutive cards < 12px (cards crowd/touch) or > 48px on <= 767px (cards look unrelated);
  - gaps in the same group differ by > 8px;
  - a card's decorative shadow/bar sits closer to the next card than to its own card (looks attached to the
    wrong card).
- **How to verify:** find repeated sibling cards (same class, stacked: same left, increasing top); measure the
  gap between each card's bottom (including `box-shadow` offset / `::after` decorative bars) and the next
  card's top; compare all gaps in the group.
- **Example:** staging.digitalboostia.com `/educredservices/`, 320x568 - between the "Licensing Agency Support"
  card (with its dark offset bar underneath) and the "Accrediting Agencies" card the gap is not suitable:
  ~40px of empty space after the dark bar, so spacing looks off compared with the card's own design.
- **Automated:** not yet.

### RESP-03 - Text must not run under/behind a button or other element

- **Applies to:** notices, cards, headers - any row with text next to a button/icon, at every viewport.
- **Expected:** text wraps before reaching neighbouring elements; nothing overlaps it.
- **Fail (WARNING):** a text line's box intersects a visible button/element painted over it.
- **How to verify:** compare text line rects (`Range.getClientRects()`) with sibling button rects; any
  intersection > 2px = overlap.
- **Example:** same clubfootsolutions.org cart notice - "has been added to" runs under the "View cart"
  button ("to" is cut off).
- **Automated:** not yet (planned for `responsive_checker.py`).

### RESP-16 - Header/nav must be sticky with a solid background on scroll

- **Applies to:** the main site header (logo + nav links), at every viewport.
- **Expected:** the header stays visible at the top of the viewport when the user scrolls down.
  When sticky/fixed, the header must have a solid (opaque) background so page content cannot
  show through. Content below the header must not overlap the header area.
- **Fail (WARNING):** any of:
  - after scrolling 200px, the header is no longer visible at the top of the viewport
    (header scrolled away without becoming sticky);
  - the sticky/fixed header has a transparent or semi-transparent background (alpha < 0.9) so
    page content bleeds through it;
  - page content (text, images, sections) overlaps the header's bounding box at scroll 0
    (header covers hero content with no padding/offset applied to the page body).
- **How to verify:**
  1. `window.scrollTo(0, 200)`, then check the header element's `getBoundingClientRect().top`
     — if it is ≥ 0 and roughly 0, it is sticky; if it has scrolled to a large negative value,
     the header is not sticky.
  2. Read `getComputedStyle(header).backgroundColor` — parse alpha; if < 0.9, the background
     is not solid enough.
  3. At scroll 0, check whether the first content section's top overlaps the header's bottom.
- **Example:** staging.digitalboostia.com `/educredservices/`, 320×568 — after the first scroll
  the header disappears or sits with a transparent background, causing the hero H1 text
  ("Higher ed accreditation and compliance made easy(ier).") to overlap the logo and nav area;
  the logo has no visual separation from the hero content behind it.
- **Automated:** not yet.

### RESP-17 - Decorative icons/badges must stay within their designed container at every viewport

- **Applies to:** decorative icons, circular badges, stamp-style images, and overlaid graphics that are
  `position: absolute` or `position: relative` and designed to sit on/over a specific parent container
  (e.g. a section image or card). Checked at every viewport.
- **Expected:** the icon/badge stays fully within the bounds of its designed parent container at every
  viewport. Its visual position must match the Figma design intent (e.g. bottom-left of image) rather
  than drifting into neighbouring text, columns, or outside the section entirely.
- **Fail (WARNING):** any of:
  - the icon's bounding rect overlaps a sibling text block or button (`intersection > 4px`);
  - the icon is fully outside its intended parent container rect (drifted into an adjacent column);
  - the icon is clipped or hidden at a viewport where it was visible in the Figma design.
- **How to verify:** find elements with `position: absolute` that contain an `<img>` or icon font
  inside a section; check `getBoundingClientRect()` of the icon vs its nearest positioned ancestor
  (parent container) and vs nearby text elements; flag any intersection or out-of-bounds condition.
- **Example:** staging.digitalboostia.com `/brandtheating/`, 956px — the "Comfort Club Maintenance"
  circular badge is designed (in Figma) to sit on the bottom-left of the section photo. At the
  two-column tablet layout the badge drifts right into the text column and overlaps the paragraph
  "Routine maintenance helps keep your system productive…", hiding the start of the text. At the
  single-column mobile layout the badge correctly sits on the photo, matching the Figma design.
- **Related:** RESP-06 (any positioned element overlapping text/buttons). RESP-17 specifically
  covers icons/badges that have a designed container anchor and must remain within it.
- **Automated:** not yet.

### RESP-18 - Stacked footer/section columns must expand to fill available width on mobile

- **Applies to:** footer widget columns, feature/info columns, and any multi-column layout that stacks
  vertically on tablet/mobile. Checked at widths ≤ 1024px.
- **Expected:** when columns stack vertically, each stacked column expands to at least ~80% of the
  container width. No large blank horizontal space should sit beside a content block — wasted space
  indicates a column that kept its desktop fractional width (e.g. 50%) instead of becoming full-width.
- **Fail (WARNING):** any of:
  - a stacked column block's width is < 70% of the container width while the remaining horizontal
    space is empty (no sibling content visible beside it);
  - consecutive stacked blocks have different widths (one 100%, the next 50%) creating a visually
    inconsistent layout;
  - a footer widget (nav list, contact info, address) occupies less than 65% of the footer container
    width on a single-column mobile layout.
- **How to verify:** find footer column elements (`footer [class*=col]`, `footer [class*=widget]`,
  `footer [class*=column]`) and section grid items; read their `getBoundingClientRect().width` vs
  the parent container's width; flag any block where `blockWidth / containerWidth < 0.70` and no
  sibling element occupies the adjacent space.
- **Example:** staging.digitalboostia.com `/brandtheating/`, 956px mobile view — the footer
  "Explore" nav list, "Contact Us" block, and "Fireplace Showroom" block each occupy roughly the
  left 50% of the footer, leaving the right 50% completely empty. The columns did not switch to
  full-width when stacking, so the footer looks half-filled with wasted space beside each block.
- **Automated:** not yet.

### RESP-19 - Button width must not stretch to full container width unless the Figma design requires it

- **Applies to:** all visible buttons and button-styled links (`button`, `input[type=submit|button]`,
  `.btn`, `.button`, `[role=button]`, Elementor `.elementor-button`) at tablet and mobile viewports.
- **Expected:** a button that is compact (content-fit) on desktop must stay compact on mobile and
  tablet. Its width should reflect its label length, not forcibly expand to fill the container.
  If the Figma design shows a full-width button at that breakpoint, full-width is correct and
  should not be flagged.
- **Fail (WARNING):** a button whose label is short (≤ 35 characters including spaces) spans
  ≥ 90% of its parent container width on a mobile/tablet viewport (≤ 1024px), suggesting an
  unintended `width: 100%` is applied. Both buttons in a stacked group stretching to the same
  full width is also flagged.
- **How to verify:** for each visible button, measure `getBoundingClientRect().width` vs its
  parent container width; read the button's label text length; read `getComputedStyle().width`
  and check if it is set to `100%`. Flag when label ≤ 35 chars AND button fills ≥ 90% container.
- **Note:** some designs intentionally use full-width mobile buttons (e.g. a CTA below a hero
  text block). Always cross-check against the Figma design before marking as a real bug.
- **Example:** staging.digitalboostia.com `/brandtheating/about/`, 956px mobile — "Contact Us Today"
  and "Call (319) 338-3637" buttons both stretch to 100% of the content column width. On desktop
  these buttons have a natural compact/inline width. The forced full-width on mobile does not match
  the Figma design.
- **Automated:** not yet.

### RESP-20 - A section column must not be completely empty while a sibling column holds all the content

- **Applies to:** any two-column (or multi-column) section layout where both columns are structurally
  present in the DOM — icon lists, feature grids, value/principle lists, service pairs — at every viewport.
- **Expected:** when a section has two or more content columns, each column should hold visible content.
  If items cannot distribute evenly, the layout should collapse to a single full-width column so all
  items are visible and the empty column disappears.
- **Fail (WARNING):** any of:
  - one column of a two-column section contains all the visible items while the sibling column is
    completely empty (no text, no image, no icon);
  - a column element is rendered with significant height (≥ 120px) but contains no visible child
    content (the column exists in the DOM but nothing rendered inside it);
  - a multi-item list whose items should distribute 50/50 across two columns places all items in
    one column, leaving the other with zero items.
- **How to verify:** find two-column section containers (`display: grid` with 2 columns, or two
  sibling flex children each ~50% width); for each column read `childElementCount` and the union
  of inner element rects; if one column height ≥ 120px and its content rect height < 10px, flag it.
- **Note:** distinguish between an intentionally empty decorative column (e.g. a background-image
  column with no text) and a broken layout column. Check whether the empty column has a background
  image or visual content via `getComputedStyle().backgroundImage` before flagging.
- **Example:** staging.digitalboostia.com `/brandtheating/about/`, 956px — a "Our Principles" section
  shows a two-column grid. The left column has 5 items with icons (Put customers first, Deliver honest
  recommendations, Maintain high standards, Provide dependable workmanship, Build long-term trust).
  The right column has the same alternating divider rows but is otherwise completely empty — no icons,
  no text, no image. The correct layout would either distribute items half-and-half across both columns
  or collapse to a single full-width column.
- **Automated:** not yet.

### RESP-21 - Slider/carousel navigation controls must not touch the content section below them

- **Applies to:** slider prev/next arrow buttons and pagination dots that appear below a carousel
  or slider component, at every viewport.
- **Expected:** there is a clear visual gap between the bottom edge of the slider navigation
  controls and the top of the next section or content block below them.
  Guide: at least 24px gap between the controls' bottom and the next section's top on mobile,
  at least 32px on desktop.
- **Fail (WARNING):** any of:
  - the gap between the slider nav controls' bottom edge and the next section element's top edge
    is < 16px (controls appear to touch or crowd the next section);
  - the slider nav controls overlap the next section's content (gap < 0px);
  - the nav controls visually sit inside the next section's padding area, causing visual confusion
    about which section they belong to.
- **How to verify:** find slider navigation containers (elements containing prev/next buttons,
  often `[class*=nav]`, `[class*=arrow]`, `[class*=control]`, `[class*=swiper-button]`);
  measure the bottom of the nav controls vs the top of the next sibling section;
  flag when gap < 16px.
- **Example:** staging.digitalboostia.com `/brandtheating/about/`, 956px — the team member slider
  has prev (←) and next (→) circular arrow buttons below the team cards. At this viewport, the
  nav buttons sit with almost no spacing before the "PROUD TO BE PART OF THE IOWA CITY COMMUNITY"
  heading of the following section. The nav controls look like they float on top of the next
  section rather than belonging to the team slider above.
- **Related:** RESP-01 (slider arrow vertical centering on track). RESP-21 is specifically about
  the bottom gap between carousel controls and the next page section.
- **Automated:** not yet.

### RESP-22 - Section vertical padding must not be excessive on mobile/tablet

- **Applies to:** all page sections and content blocks, especially sections that transition from a
  multi-column desktop layout to a stacked single-column mobile layout. Checked at ≤ 1024px.
- **Expected:** vertical padding (top + bottom) within a section, and vertical gap between
  consecutive sections, should be proportionate to the content. When columns stack on mobile,
  the section container should reduce its vertical padding to match. Large desktop padding values
  (e.g. 120px top/bottom) should be overridden at mobile (guide: ≤ 60px each side on mobile,
  ≤ 80px on tablet).
- **Fail (WARNING):** any of:
  - a section's top or bottom padding exceeds 80px on mobile (≤ 767px) or 100px on tablet
    (768–1023px) when its visible content does not need that much breathing room;
  - the gap between the last visible element in a section and the next section's first element
    exceeds 100px on mobile or 120px on tablet (suggesting the section kept desktop spacing);
  - an image-only or single-item section has a surrounding empty space (top + bottom) ≥ 2× the
    content height, making the section look mostly empty.
- **How to verify:** for each section element, read `getComputedStyle().paddingTop` and
  `paddingBottom`; measure the gap between the section's last visible child bottom and the
  next section's first visible child top; flag excessive values at mobile/tablet viewports.
- **Example:** staging.digitalboostia.com `/brandtheating/about/`, 956px — a section that shows
  a large team meeting photo has stacked from a two-column (text + image) desktop layout into a
  single-column mobile layout. The section retains large desktop top/bottom padding, creating
  noticeable empty space beneath the photo and before the "THE VALUES WE STILL WORK BY TODAY"
  heading section that follows.
- **Related:** RESP-14 (hero/banner height fitting content). RESP-22 covers general page sections,
  not just hero/banner areas.
- **Automated:** not yet.

### RESP-23 - Slider active slide must be horizontally centered with equal left/right side spacing

- **Applies to:** any slider or carousel that shows the active slide centered with adjacent slides
  partially peeking in from both sides (a "peek" or "offset" slider), at every viewport.
- **Expected:** the active slide is visually centered in the slider track. If adjacent slides peek
  in from both sides, the left peek and right peek widths must be equal (tolerance: ≤ 8px
  difference). The active slide must not sit noticeably closer to one edge than the other.
- **Fail (WARNING):** any of:
  - the left gap between the slider track edge and the active slide's left edge differs from
    the right gap by more than 8px (slide is off-center in the track);
  - one side shows a visible portion of an adjacent slide while the other side shows none
    (asymmetric peek);
  - the active slide is flush against one edge of the slider track while the opposite edge
    has a gap (slide is pinned to one side).
- **How to verify:** find the slider track container and the active/current slide element;
  measure `getBoundingClientRect()` of both; compute
  `leftGap = slide.left - track.left` and `rightGap = track.right - slide.right`;
  flag when `Math.abs(leftGap - rightGap) > 8`.
- **Example:** staging.digitalboostia.com `/brandtheating/about/`, 956px — the team member
  slider shows "Bill Brandt | President" as the active slide. The dark edge of the previous
  slide peeks in from the left while the next slide peeks in from the right, but the peek
  widths are unequal — the active card is not centered in the track, making the layout look
  asymmetric and visually unbalanced.
- **Automated:** not yet.

### RESP-24 - Full-width sections must span the full container width at all viewports (no right-side gap)

- **Applies to:** page sections designed in Figma as full-width (background/banner stretches edge to
  edge) — typically CTA banners, hero sections, colored strips, testimonial backgrounds. Checked
  especially at large desktop viewports (≥ 1440px, ≥ 1920px, ≥ 2560px).
- **Expected:** a section whose Figma design shows a full-width background (color, image, gradient)
  stretching to the viewport edge must maintain that full-width at all viewports. The section
  element's width should be 100% of the viewport or its parent container, with no large empty gap
  on either side.
- **Fail (WARNING):** any of:
  - a section's rendered width is < 90% of the viewport width at ≥ 1440px, leaving a visible
    empty gap beside it (right or left side);
  - the section container has a `max-width` that cuts the section short while the Figma design
    shows it spanning the full viewport width;
  - the section background color/image stops before the viewport edge at large desktop widths
    (content max-width correctly centered, but background does not extend to viewport edges).
- **How to verify:** at each viewport, compare the section element's `getBoundingClientRect().width`
  and `left/right` against `window.innerWidth`; read `getComputedStyle().maxWidth` to identify
  a constraining rule; flag sections where `sectionWidth / viewportWidth < 0.90`.
- **Note:** only flag as a design mismatch when the Figma design confirms full-width intent. A
  section intentionally narrower than the viewport (e.g. a centered card) should not be flagged.
- **Example:** staging.digitalboostia.com `/brandtheating/about/`, 2560px — the red CTA section
  "NEED A TEAM YOU CAN TRUST? / Schedule A Service / Contact Us Today / Call Us 319-338-3637"
  ends at a fixed max-width of ~1050px, leaving a large empty white gap to the right that is
  highlighted in red. In the Figma desktop design, this CTA section stretches full-width with the
  red background reaching both viewport edges. The staging site has not removed or overridden the
  max-width constraint at large screen sizes.
- **Automated:** not yet.

### RESP-25 - Line-height must not be so large that wrapped lines look like separate paragraphs

- **Applies to:** list items (`<li>`), paragraphs (`<p>`), and any text block that wraps to
  2+ lines at mobile/tablet viewports (≤ 1024px). Checked especially at 320px–768px widths.
- **Expected:** when text wraps to a second line, the visual gap between line 1 and line 2
  of the same text block looks like normal line-height — not like a paragraph break.
  Guide: computed `line-height` should be ≤ 1.8× the `font-size` for body/list text.
- **Fail (WARNING):** any of:
  - for a text block that wraps to 2+ lines, the gap between consecutive line rects
    (measured via `Range.getClientRects()`) exceeds 1.8× the element's `font-size`;
  - the internal line gap of a list item or paragraph looks as large as the gap between
    two separate list items, making it impossible to tell where one item ends and the next begins;
  - `getComputedStyle().lineHeight` parsed as px > 2.0 × `fontSize` on mobile (≤ 767px) for
    body-text or list-item elements.
- **How to verify:** for each visible list item or `<p>` that wraps at this viewport, read
  `getComputedStyle().lineHeight` and `fontSize`; compute the ratio; flag when ratio > 1.8.
  Also use `Range.getClientRects()` on the text content to measure actual pixel gap between lines.
- **Example:** staging.digitalboostia.com `/brandtheating/about/`, 320×568 — a bullet-point
  list of service features (Brandt diamond icons) contains multi-word items that wrap at this
  width: "Decades of proven / experience", "Licensed and trained / technicians",
  "Practical solutions tailored / to your needs", "Financing options / available".
  The line-height is so large that each wrapped pair of lines has a gap equivalent to an
  entire list item's height, making each item look like two separate items. The desktop
  line-height (likely set in ems, e.g. 2.5em) was not reduced for mobile.
- **Related:** RESP-13 (line-height too small → lines touch/overlap). RESP-25 is the
  opposite extreme: line-height too large → wrapped lines look like paragraph breaks.
- **Automated:** not yet.

### RESP-26 - An empty content container with a defined height must not create a large visual gap

- **Applies to:** any `<div>`, `<section>`, or block-level element that has a computed height ≥ 80px
  but contains no visible child elements (no text, no image, no icon, no background image). Checked
  at all viewports.
- **Expected:** if a container has no visible content, it should collapse to zero or near-zero height.
  A visible blank box is a sign that a `min-height`, `height`, or `padding` value is keeping the
  container open despite being empty — creating wasted space in the layout.
- **Fail (WARNING):** any of:
  - a block container's `getBoundingClientRect().height` ≥ 80px AND it has no visible child rects
    (all children have `height < 4px` or are hidden/display:none);
  - the same empty container grows proportionally larger at wider viewports (e.g. 150px at 768px,
    220px at 1280px), amplifying the gap at bigger screens;
  - the empty container sits between a slider's navigation controls and the next page section,
    creating a large visual gap that makes the slider look broken.
- **How to verify:** iterate block elements with `getBoundingClientRect().height >= 80`; for each,
  sum the heights of all visible child rects; if the sum is < 10px while the container height
  ≥ 80px, flag it; read `getComputedStyle().minHeight` and `height` to report the cause.
- **Note:** exclude containers that have a `background-image` or are known decorative spacers
  (`[class*=spacer]`, `[class*=divider]`). Also exclude containers with `overflow: hidden` that
  intentionally clip content (e.g. off-canvas menus).
- **Example:** staging.digitalboostia.com `/brandtheating/about/`, 1280×720 — the team member
  slider has a content area below the name/title cards that is completely empty (no bio, no text,
  no image). At 1280px this empty container is roughly 180px tall and 320px wide, appearing as a
  large blank white box outlined in the screenshot. It sits between the slider ← → nav buttons and
  the "PROUD TO BE PART OF THE IOWA CITY COMMUNITY" heading, making the section look broken and
  wasting significant vertical space.
- **Related:** RESP-20 (empty adjacent column in a two-column layout). RESP-26 covers any empty
  container regardless of layout context.
- **Automated:** not yet.

### RESP-27 - Labels in the same icon/feature group must wrap consistently at each viewport

- **Applies to:** groups of same-level items sharing the same visual template — icon + label lists,
  feature strips, stats blocks, benefit grids — where every item has an icon and a short text label.
  Checked at every viewport.
- **Expected:** within a group, all labels wrap to the same number of lines at a given viewport.
  If most labels wrap to 2 lines (because the viewport is narrow), no label should remain on 1 line
  unless it is intentionally shorter by design. Inconsistent wrapping (some items 1 line, others 2)
  makes the group look visually broken and unbalanced.
- **Fail (WARNING):** within a group of ≥ 3 same-type items (same parent, similar structure),
  at least one item wraps to a different number of lines than the majority — specifically when:
  - the majority (≥ 60%) of items wrap to 2+ lines, but one or more items stay on 1 line;
  - OR one item's label has a noticeably different font-size from its siblings (difference > 2px),
    causing it to behave differently when the viewport narrows.
- **How to verify:** find repeated sibling elements that each contain an icon + text label (e.g.
  `[class*=icon-box]`, `[class*=feature]`, list items with icons); for each, use
  `Range.getClientRects()` on the label text to count line rows; compare line counts across the
  group; flag when one item's line count differs from the group's mode by ≥ 1.
- **Example:** staging.digitalboostia.com `/brandtheating/services/ac-repair/`, 956px — a red
  feature strip has 5 icon+label items stacked vertically: "Family-Owned Since 1953" (2 lines),
  "Fast Response Times" (2 lines), "Honest Service" (2 lines), "Licensed & Trained Technicians"
  (1 line), "Financing Available" (2 lines). Four of the five items wrap to 2 lines but
  "Licensed & Trained Technicians" — a longer phrase — stays on a single line, likely because its
  font-size was manually reduced or it has a different CSS rule. This inconsistency makes the
  layout look unbalanced.
- **Automated:** not yet.

### RESP-28 - Custom list bullet icons must align with the first line of their text, not float mid-item

- **Applies to:** any list item that pairs a custom bullet icon (image, SVG, icon font, `::before`
  pseudo-element, or inline `<img>`) with a text label that can wrap to multiple lines at mobile/
  tablet viewports. Checked at widths ≤ 768px where wrapping is most likely.
- **Expected:** the custom bullet icon is vertically aligned with the **first line** of the item's
  text (top-aligned or `align-items: flex-start`). Single-line and multi-line items in the same
  list must look visually consistent — the icon should always appear parallel to (at the same
  vertical position as) the start of the text.
- **Fail (WARNING):** any of:
  - the bullet icon's vertical center is more than half the icon's own height below the text's
    first-line top (icon has drifted down toward the middle of multi-line text);
  - the icon's top edge is more than 8px below the text element's top edge (icon is not
    top-aligned with the text);
  - within the same list, single-line items look aligned but multi-line items look misaligned
    because the icon is `align-items: center` on the flex row rather than `flex-start`.
- **How to verify:** find list items or icon-text rows (`display: flex` or `display: grid` rows
  containing an icon + text sibling); for each, get `getBoundingClientRect()` of the icon and
  the first text node's first line rect (via `Range.getClientRects()[0]`); compare icon center
  vs text first-line center; flag when `Math.abs(iconCenter - textFirstLineCenter) > iconHeight/2`.
- **Example:** staging.digitalboostia.com `/brandtheating/financing/`, 320×568 — a bullet list
  "Financing may help you:" uses Brandt diamond icons (▼). Single-line items like "Spread project
  costs over time" look fine. Multi-line items like "Replace failing equipment / sooner" and
  "Protect your comfort and / budget" have the ▼ icon vertically centered between both text lines
  rather than sitting beside the first line, making the icon appear to float mid-item and look
  unparallel to the text start.
- **Related:** RESP-11 (icon and text must share the same alignment axis in feature sections).
  RESP-28 specifically covers list item bullets misaligning when text wraps.
- **Automated:** not yet.

### RESP-29 - Icon-beside-text info blocks must not collapse to a vertical stack at intermediate viewports

- **Applies to:** contact info blocks, feature highlights, and any component designed as an
  icon-on-the-left + text-on-the-right horizontal row (e.g. phone icon → "Call or Text / number",
  clock icon → "Hours / times", location pin → "Address"). Checked at all viewports.
- **Expected:** the icon and its associated text remain in the same horizontal row at viewports
  where the Figma design shows them side-by-side. The icon sits beside (to the left of) its text,
  not stacked above it. A vertical (stacked) layout is only acceptable at viewports small enough
  that the Figma design explicitly shows a stacked arrangement.
- **Fail (WARNING):** any of:
  - the icon's bottom edge is above the text element's top edge by more than 8px (icon is above
    the text, not beside it) at a viewport where the design shows them side-by-side;
  - the icon and text share the same horizontal center (both centered in the column) rather than
    the icon being left of the text — indicating a center-stacked collapse;
  - `getComputedStyle(container).flexDirection === "column"` (or similar block stacking) on a
    container at ≥ 768px that the Figma design shows as `row`.
- **How to verify:** find icon+text row containers; measure `getBoundingClientRect()` of the icon
  element and the first text element; if `icon.bottom < text.top - 8` at the current viewport,
  the layout has stacked vertically; compare against Figma design intent for that viewport.
- **Example:** staging.digitalboostia.com `/brandtheating/contact-us/`, 1024×768 — the
  "PREFER TO TALK WITH SOMEONE?" card has two info rows: a phone icon + "Call or Text /
  319-338-3637", and a clock icon + business hours. At 1024px, each icon sits on its own line
  above its text instead of beside it. The Figma design shows the icon to the left of the text
  in the same row. The collapse to a vertical stack at 1024px means icon and content are not
  parallel, making the contact info harder to scan.
- **Related:** RESP-28 (bullet icon floating mid-item when text wraps). RESP-29 is specifically
  about the entire layout direction collapsing from horizontal to vertical prematurely.
- **Automated:** not yet.

### RESP-30 - Decorative background designs must not overflow their container and bleed into adjacent sections

- **Applies to:** decorative background elements — `::before`/`::after` pseudo-element shapes,
  absolutely-positioned background graphics, background-image overlays, gradient overlays, and
  section card backgrounds — that are designed to stay within one section or column. Checked at
  every viewport, especially at intermediate widths where layouts transition between breakpoints.
- **Expected:** every decorative background element stays within the bounds of its own container.
  It must not extend into, overlap, or visually obscure content in a neighbouring section, column,
  or card. If the element is larger than its container by design, the container must clip it
  (`overflow: hidden`) so it cannot be seen outside its intended area.
- **Fail (WARNING):** any of:
  - a decorative element's `getBoundingClientRect()` extends more than 4px into a sibling
    column's bounding rect AND that sibling column contains visible text or interactive elements
    (inputs, buttons, links);
  - a section card's background color or image visually bleeds into the adjacent column's
    content area, partially obscuring form fields, text, or interactive elements;
  - a `::before`/`::after` pseudo-element (detectable via computed `content` and `position:
    absolute`) on one container overlaps a sibling container's interactive content.
- **How to verify:** find adjacent column pairs within a section; measure each column's rect;
  identify absolutely-positioned children or pseudo-elements that have rects extending past the
  column boundary; check for overlap with the sibling column's content rects. Any overlap >4px
  where content exists should be flagged.
- **Note:** always cross-check against the Figma design to confirm the decorative element was
  not intentionally designed to span both columns. If Figma shows it contained within one column,
  any bleeding at the actual site is a bug.
- **Example:** staging.digitalboostia.com `/brandtheating/contact-us/`, 1280×720 — a two-column
  layout shows "PREFER TO TALK WITH SOMEONE?" (gray card, left) beside "SEND US A MESSAGE"
  (contact form, right). A decorative background element from the left card bleeds approximately
  90px into the right form column, partially obscuring the left edges of the Full Name, Email
  Address, and Phone Number input fields. The background design should be clipped to the gray
  card's container boundary.
- **Related:** RESP-06 (floating/positioned elements overlapping text/buttons), RESP-17 (badge
  drifting outside its container). RESP-30 specifically covers background-layer design elements
  bleeding across section/column boundaries.
- **Automated:** not yet.

### RESP-31 - Content+button rows must keep the button on its designed side; a large empty gap beside them is an error

- **Applies to:** rows designed as a horizontal pair — title/label on one side (usually left) and
  an action button on the other side (usually right) — such as download rows, resource lists,
  FAQ rows, or feature rows with a CTA. Checked at desktop viewports (≥ 1024px) where the
  Figma design shows a horizontal layout.
- **Expected:** the action button stays on its designed side (right) in the same row as the title,
  separated by available space. There should be no large empty horizontal gap on the side where
  the button was supposed to sit. Only at mobile widths (≤ 767px) is it acceptable for the button
  to stack below the title.
- **Fail (WARNING):** at ≥ 1024px, any of:
  - the button is vertically below the title text (button top > title bottom) AND the right half
    of the row container is empty (no content in the right 40% of the container width);
  - the button and title share the same horizontal left edge when the Figma design shows the
    button right-aligned or right-side placed;
  - the row container has `justify-content: space-between` or `flex-direction: row` in the
    Figma design, but the staged page renders the items in column order leaving a right-side gap.
- **How to verify:** find repeating row containers (e.g. list items or `<tr>` rows containing
  both a text element and a button); measure `getBoundingClientRect()` of the title and button;
  if `button.top > title.bottom + 4` at ≥ 1024px, check whether the right portion of the row
  is empty; if `(container.right - button.right) > container.width * 0.40`, flag it as
  button-dropped-from-right.
- **Example:** staging.digitalboostia.com `/brandtheating/support/`, 1440×900 — a "Thermostat
  Manuals & Resources" list has rows of: title ("Honeywell TH5110 Thermostat Owners Manual")
  + "Download" button. In the Figma design the button is right-aligned in the row beside the
  title. On the staging site both the title and button are left-aligned (button stacked below
  the title), leaving the right half of each row completely empty. This is a layout bug at a
  large desktop viewport where the horizontal layout should be intact.
- **Related:** RESP-18 (footer columns not expanding), RESP-20 (empty column beside content).
  RESP-31 is specifically about action-item rows where a button dropped from the right.
- **Automated:** not yet.

### RESP-32 - All text content must stay fully readable within its container at every viewport; no edge clipping

- **Applies to:** all text blocks — addresses, paragraphs, headings, list items, footer content —
  at every viewport, especially at the smallest widths (320px, 375px).
- **Expected:** every line of text has at least 8px of clearance from its container's left and right
  edges. No text character is cut off by `overflow: hidden` or `overflow: clip` on a parent element.
  Multi-block content groups (e.g. location sections with address + phone in a footer) must all fit
  within the container and be readable together at the smallest supported viewport.
- **Fail (WARNING):** any of:
  - a text line's right edge (`Range.getClientRects()` line right) is within 4px of the container's
    right inner edge (`paddingBox.right`) — text is flush to the edge with no padding;
  - a text character is visually clipped by an ancestor's `overflow: hidden`/`clip` — the last
    visible character on a line is at the container boundary and the word continues on the next line
    at a position that suggests a mid-word clip;
  - a footer or content column that groups multiple info blocks (address, phone, links) has any
    block whose text overflows or clips at 320px–375px widths.
- **How to verify:** iterate all visible text nodes; for each, get line rects via
  `Range.getClientRects()`; find the nearest `overflow: hidden`/`clip` ancestor; compare the line's
  right edge to the ancestor's `getBoundingClientRect().right - parsedPaddingRight`; flag when
  gap < 4px.
- **Example:** staging.digitalboostia.com `/handhole/`, 320×862 — the footer has three location
  blocks (Iowa, Missouri, Texas) each with a street address and phone number. At 320px, the Iowa
  address "409 Seventh Avenue SE, Cedar Rapids, Iowa 52401" and the Texas address "3201 East Loop
  820 South, Fort Worth, Texas 76119" both run to the right edge of the footer container with
  essentially zero padding — the last characters of each address line touch or are cut off at the
  container boundary, making the text difficult to read and visually incomplete.
- **Related:** RESP-10 (content must not touch edge of its box/card — ≥8px gap guideline).
  RESP-32 specifically focuses on text character clipping and edge-flush text at small viewports.
- **Automated:** not yet.

### RESP-33 - No single content block should be orphaned alone on a new row while leaving most of that row empty

- **Applies to:** footer column groups, feature grid rows, navigation link rows, and any multi-item
  horizontal layout that wraps to a new row when the viewport is too narrow. Checked at intermediate
  tablet/desktop widths (768px–1280px) where partial row-wrapping is most likely.
- **Expected:** when items in a row cannot all fit at a given viewport width, the wrap should either:
  (a) keep all items together in one row by shrinking them to fit, or
  (b) distribute items evenly across rows so no single item is isolated alone on a row while the
  rest of that row is empty. A lone item taking < 30% of a row while > 50% of the row is empty
  is a layout problem.
- **Fail (WARNING):** any of:
  - a flex/grid row contains exactly one item while its sibling row(s) have ≥ 3 items — a lone
    item has been orphaned due to wrapping;
  - the orphaned item's width is < 30% of the row container width while the remaining space
    beside it is empty (no sibling content visible);
  - a footer section with N location/info columns wraps such that one column sits alone on a second
    row while the first row is fully populated, and the orphaned column's right edge leaves > 50%
    of the footer width empty.
- **How to verify:** find multi-column flex/grid containers; group children by their `offsetTop`
  into virtual rows; if any row has exactly 1 child while the overall group has > 2 total children,
  and the lone child's width < container.width × 0.3, flag it as orphaned.
- **Example:** staging.digitalboostia.com `/handhole/`, ~1280px — the footer has 5 items: logo,
  "Our Links" nav, "Iowa" location, "Missouri" location, "Texas" location. At this viewport, 4
  items fit on the first row (logo + Our Links + Iowa + Missouri) and "Texas" wraps to a second
  row alone, occupying only the left ~20% of the footer width. The right ~80% of the second row
  is completely empty. The Texas location block looks isolated and disconnected from the other
  footer content, and the footer as a whole looks unfinished.
- **Related:** RESP-18 (footer columns not expanding to full width), RESP-20 (empty column beside
  content in a section). RESP-33 is specifically about a single item orphaned to a new row in a
  flex/grid wrapping layout.
- **Automated:** not yet.

### RESP-34 - In equal-height card rows, action buttons must be pinned to the card bottom, not floated mid-card

- **Applies to:** card grids where sibling cards in the same flex/grid row stretch to equal height
  (profile cards, team cards, service cards, product cards). Checked at all viewports where cards
  appear in a multi-column row.
- **Expected:** when cards in the same row have different content lengths, the shorter cards
  stretch to match the tallest card's height. The action button (CTA, "Meet X", "Learn More",
  "Download") must be pinned to the bottom of the card (using `margin-top: auto` or a spacer)
  so it aligns with the buttons in sibling cards. There must be no large empty space inside
  the card between the button and the card's bottom edge.
- **Fail (WARNING):** any of:
  - within a same-row group of ≥ 2 cards, the action button in one card has more than 24px of
    empty space between its bottom edge and the card's bottom edge, while a sibling card's button
    sits at or near the card bottom (buttons in the row are not bottom-aligned);
  - the buttons in the same card row are at different Y-positions — they should all be at the
    same Y when the cards are equal height;
  - a card's action button is more than 20px above the card's bottom edge while the card has
    more than 30px of empty space between the button and the card bottom.
- **How to verify:** group card elements by their `offsetTop` into same-row groups; for each row
  find elements matching `[class*=button], [class*=btn], a.button, button` inside each card;
  collect the `getBoundingClientRect().bottom` of each button in the row; if the range
  (max - min) > 20px, buttons are not bottom-aligned; also check the gap between each button
  bottom and its card's bottom.
- **Example:** staging.digitalboostia.com `/debut-dance/about/`, 1478×862 — a 4-column instructor
  card row shows Avery Wilson, Stella Skelley, Joscelyn Siloro, Emmy Schroeder. Cards 3 and 4
  (longer content) set the row height. Cards 1 and 2 have shorter content, so their "Meet Avery"
  and "Meet Stella" buttons float mid-card with a large empty white area below them inside the
  card. The buttons should be pinned to the card bottom so all four "Meet" buttons align at the
  same Y position across the row.
- **Automated:** not yet.

### RESP-35 - Form input placeholder text must not be clipped or cut off at any viewport

- **Applies to:** all visible form inputs (`<input>`, `<select>`, `<textarea>`) that have a
  `placeholder` attribute, at every viewport width.
- **Expected:** the full placeholder text is readable within the input field. If the placeholder
  is too long to fit in the field's inner width, it should be truncated with an ellipsis (`…`)
  via CSS `text-overflow: ellipsis` on the `::placeholder`, so the user can at least see the
  start of the hint. Hard clipping (characters cut mid-word with no ellipsis) is not acceptable.
- **Fail (WARNING):** any of:
  - an input field's inner width (field width minus left+right padding) is less than the
    natural rendered width of its placeholder text at the current font-size, and the placeholder
    has no `text-overflow: ellipsis` — resulting in a hard cut mid-word;
  - the placeholder text is so clipped that the remaining visible portion is ambiguous — the
    user cannot determine the field's purpose from the partial text shown;
  - two adjacent input fields sharing a row are so narrow at mobile/tablet that both of their
    placeholders are partially clipped (side-by-side layout should stack at narrow widths).
- **How to verify:** for each `input[placeholder]`, read the `placeholder` attribute string;
  create a test span with the same `font-size`, `font-family`, `letter-spacing` to measure the
  text's natural width; compare against `input.getBoundingClientRect().width - (paddingLeft + paddingRight)`;
  flag when `textWidth > inputInnerWidth` and `getComputedStyle(input, '::placeholder').textOverflow !== 'ellipsis'`.
- **Example:** staging.digitalboostia.com `/spinemoving/`, ~996px — the "Get Free Moving Quote"
  hero form has a two-column field row: "Moving from Zip Code" (left) and "Moving to Zip Code"
  (right). At this viewport the right field is too narrow for its placeholder "Moving to Zip
  Code" — the last characters are hard-clipped by the input's edge without an ellipsis. The
  field appears as "Moving to Zip Co" or similar, making it ambiguous whether it is asking for
  a zip code, a country, or something else.
- **Automated:** not yet.

### RESP-36 - Hover popup/tooltip cards must stay fully within the viewport at all viewport sizes

- **Applies to:** hover-triggered popups, tooltip cards, and info overlays (hotspot dots, image map
  overlays, interactive diagram labels, nav mega-menus triggered by hover). Checked at every viewport.
- **Expected:** when a hover popup appears, its entire bounding box (including padding and borders)
  must remain within the visible viewport area. If the popup's default position would cause it to
  overflow any viewport edge (left, right, top, or bottom), it must reposition itself — flip to the
  opposite side, shift inward, or clamp to the viewport edge — before rendering. No popup content
  should be clipped or hidden by the viewport boundary.
- **Fail (WARNING):** any of:
  - a hover popup's `getBoundingClientRect().left < 0` (popup extends past the left viewport edge);
  - a hover popup's `getBoundingClientRect().right > window.innerWidth` (extends past the right edge);
  - a hover popup's `getBoundingClientRect().top < 0` (extends past the top edge);
  - a hover popup's `getBoundingClientRect().bottom > window.innerHeight` (extends past the bottom);
  - the popup's text, image, or button content is visually clipped at the viewport boundary, making
    it unreadable (e.g. only partial letters visible at the edge).
- **How to verify:** for each triggerable hotspot or hover element, simulate a hover (`page.hover()`),
  wait for the popup to appear, then read its `getBoundingClientRect()` and compare against
  `{ top: 0, left: 0, right: window.innerWidth, bottom: window.innerHeight }`.
  Flag any popup that extends outside these bounds.
- **Example:** dev.dotcomdesign.com `/tomlinson-cannon/`, 1024×768 — an interactive house diagram
  has clickable/hover hotspot dots at various positions. Hovering over the bottom-left hotspot
  (crawl space area) triggers a popup card showing a crawl space encapsulation photo, the title
  "Crawl Space Encapsulation", and a "LEARN MORE" button. The popup positions itself to the left
  of the hotspot but does not check viewport bounds — its left edge extends past the viewport's
  left boundary, clipping the "C" of "Crawl" and the "L" of "LEARN MORE", making both unreadable.
- **Automated:** not yet (requires triggering hover states per hotspot and measuring popup bounds).
