---
name: Phase 7 Figma vs Staging Audit
description: Compare a Figma frame with its live staging page using Figma MCP and Chrome DevTools MCP.
argument-hint: Optional Figma frame URL, staging URL, and viewport
agent: agent
---

Run a Phase 7 design-to-runtime QA audit. Use Figma MCP for design specifications and Chrome DevTools MCP for the rendered staging page. Do not substitute manual assumptions for unavailable design values.

## Defaults

- Figma frame: `https://www.figma.com/design/uiq2WiIDnWQLFOPJG7K4ql/Alliance-Senior-Home--Copy-?node-id=10005-1068`
- Staging page: `https://www.allianceseniorhome.com/`
- Initial desktop frame size: `1920 x 8720` (confirm from Figma metadata; use a `1920 x 1080` browser viewport for full-page capture unless the user supplies another viewport)
- Output directory: `results/figma_comparison/`

Use URLs and viewport values supplied in the user's prompt instead of these defaults. If the user supplies no arguments, use the defaults above.

## Workflow

1. Read `AGENTS.md` and preserve this project's reporting conventions. Do not modify the staging website's source code.
2. Load the `figma-design-to-code` skill before calling Figma MCP `get_design_context`. Extract the file key and node ID from the Figma URL; request the design screenshot. If the response is sparse, use its child node IDs to request focused context for the visible sections. Do not guess missing values.
3. Use Chrome DevTools MCP `list_pages` to inspect open tabs. Use `new_page` for the staging audit so an existing user tab is not disrupted. Then use `navigate_page` and `emulate` to load the staging URL at the matching CSS viewport and device scale factor 1.
4. Wait for DOM content, web fonts, and visible images to settle. Scroll the page to trigger lazy-loaded content, return to the top, and capture both a viewport screenshot and a full-page screenshot with `take_screenshot`, saving them under the output directory.
5. Use Chrome DevTools MCP `evaluate_script` to inspect matched visible elements. Collect a stable selector or accessible identity, tag/role/text, bounding box, document coordinates, computed styles, and image dimensions. Include at least:
   - Header and navigation: position, dimensions, alignment, gaps, padding, colors, borders, and shadow.
   - Typography: family, size, weight, line height, letter spacing, and color.
   - Boxes and controls: width/height, spacing, padding, margin/gap, background, border color/width/style, radius, shadow, and opacity.
   - Images: source/alt identity, rendered and natural dimensions, object-fit, and crop behavior.
6. Match Figma layers to page elements by visible text, semantic role, image identity, and structural context. Record the mapping and confidence. Do not compare unrelated elements just because their labels or colors are similar. Use document coordinates for page sections and viewport coordinates for fixed/sticky elements.
7. Compare Figma properties or Dev Mode values with the browser's measured geometry and `getComputedStyle` values. Use a default geometry tolerance of 1 CSS pixel; compare explicit computed color values directly. Keep screenshot pixel differences as supporting evidence, not as the sole verdict, because dynamic content and font rasterization can differ.
8. Save a CSV at `results/figma_comparison/element_comparison.csv` with columns:
   `page,figma_node,viewport,element,selector,property,figma_value,staging_value,difference,status,confidence,evidence`
   Use `PASS` for verified values within tolerance, `WARNING` for a confirmed mismatch or uncertain mapping, `INFO` when a property is unavailable, and `ERROR` only when the audit itself cannot run. Include screenshot paths and relevant Figma node IDs in evidence.
9. Summarize verified matches, mismatches, unavailable specs, and any MCP/access blockers. Never mark a property `PASS` unless both reference and runtime values were actually obtained.

## MCP Source Rules

- Figma MCP is authoritative for frame/layer intent and design properties.
- Chrome DevTools MCP is authoritative for the live page's DOM, computed CSS, geometry, and screenshots.
- Figma Dev Mode code is reference material; it does not replace checking the deployed page's computed styles.
- If Figma MCP is rate-limited or a layer property is not exposed, report that limitation and stop that comparison. Do not silently replace MCP data with values inferred from a canvas screenshot.
- Keep the first run focused on the supplied frame and matching staging page. Expand to more pages/viewports only when requested or once this comparison is validated.