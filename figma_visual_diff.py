import os

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


# Images are compared at 1/DOWNSCALE size so 1-2px shifts and font
# anti-aliasing differences do not count as visual changes.
DOWNSCALE = 4
PIXEL_THRESHOLD = 40          # 0-255 grayscale difference that counts as "changed"
BAND_PX = 40                  # row band height (full-size px) used to locate changed regions
BAND_CHANGED_RATIO = 0.2      # a band is "changed" when this share of its pixels differ
MAX_REGIONS = 3
SEARCH_PX = 160               # how far (full-size px) around the text-based offset to search
TILE_PX = 32                  # tile size (full-size px) for spotting small localized changes
TILE_CHANGED_RATIO = 0.35     # a tile is "hot" when this share of it changed
SHIFT_TOLERANCE_PX = 8        # localized changes must survive shifts up to this many px
MAX_HOT_SPOTS = 5
REPORT_SCALE = 0.5            # size of the side-by-side evidence image


def load_rgb(path):
    image = Image.open(path)
    if image.mode != "RGB":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.convert("RGBA").split()[-1])
        image = background
    return image


def crop_padded(image, top, height):
    """Crop rows [top, top+height); rows outside the image are filled grey."""
    canvas = Image.new("RGB", (image.width, height), (200, 200, 200))
    source_top = max(0, top)
    source_bottom = min(image.height, top + height)
    if source_bottom > source_top:
        canvas.paste(image.crop((0, source_top, image.width, source_bottom)), (0, source_top - top))
    return canvas


def shrink(image):
    return image.resize((max(1, image.width // DOWNSCALE), max(1, image.height // DOWNSCALE)), Image.BOX)


def changed_mask(figma_small, staging_small):
    diff = ImageChops.difference(figma_small, staging_small).convert("L")
    return diff.point(lambda value: 255 if value > PIXEL_THRESHOLD else 0)


def shift_tolerant_mask(figma_small_crop, staging_small, top, height):
    """
    Changed pixels that stay changed at every shift up to SHIFT_TOLERANCE_PX:
    something missing/added (an icon, a badge), not something that moved a little.
    """
    shift = SHIFT_TOLERANCE_PX // DOWNSCALE
    mask = None
    for dy in range(-shift, shift + 1):
        staging_crop = crop_padded(staging_small, top + dy, height)
        for dx in range(-shift, shift + 1):
            shifted = ImageChops.offset(staging_crop, dx, 0) if dx else staging_crop
            current = changed_mask(figma_small_crop, shifted)
            mask = current if mask is None else ImageChops.darker(mask, current)
    return mask


def best_offset(figma_small, staging_small, top, height, guess):
    """
    Small-pixel offset near `guess` where the section matches staging best.
    The text-based guess can be off when a section's texts moved unevenly, so
    nearby offsets are tried; ties keep the offset closest to the guess.
    """
    figma_crop = crop_padded(figma_small, top, height)
    search = SEARCH_PX // DOWNSCALE
    best_score, best = None, guess
    for shift in sorted(range(-search, search + 1), key=abs):
        staging_crop = crop_padded(staging_small, top + guess + shift, height)
        score = ImageStat.Stat(ImageChops.difference(figma_crop, staging_crop).convert("L")).mean[0]
        if best_score is None or score < best_score - 0.01:
            best_score, best = score, guess + shift
    return best


def changed_regions(mask, top_offset):
    """Merge consecutive changed row bands into regions (full-size Figma y)."""
    band_rows = max(1, BAND_PX // DOWNSCALE)
    width = mask.width
    pixels = mask.load()
    regions = []
    current = None
    for band_top in range(0, mask.height, band_rows):
        band_bottom = min(mask.height, band_top + band_rows)
        changed = sum(
            1 for y in range(band_top, band_bottom) for x in range(width) if pixels[x, y]
        )
        ratio = changed / max(1, width * (band_bottom - band_top))
        if ratio >= BAND_CHANGED_RATIO:
            if current and current["end"] == band_top:
                current["end"] = band_bottom
                current["changed"] += changed
            else:
                current = {"start": band_top, "end": band_bottom, "changed": changed}
                regions.append(current)
    for region in regions:
        region["ratio"] = region["changed"] / max(1, width * (region["end"] - region["start"]))
        region["start"] = region["start"] * DOWNSCALE + top_offset
        region["end"] = region["end"] * DOWNSCALE + top_offset
    regions.sort(key=lambda region: region["end"] - region["start"], reverse=True)
    return regions[:MAX_REGIONS]


def hot_spots(mask, top_offset):
    """
    Small areas that changed a lot (icons, arrows, badges) even when the whole
    section is under the warning threshold. Touching hot tiles are merged.
    """
    tile = max(1, TILE_PX // DOWNSCALE)
    columns = (mask.width + tile - 1) // tile
    rows = (mask.height + tile - 1) // tile
    hot = set()
    for row in range(rows):
        for column in range(columns):
            box = (column * tile, row * tile, min(mask.width, (column + 1) * tile), min(mask.height, (row + 1) * tile))
            changed = mask.crop(box).histogram()[255]
            if changed >= TILE_CHANGED_RATIO * (box[2] - box[0]) * (box[3] - box[1]):
                hot.add((row, column))

    spots = []
    seen = set()
    for start in sorted(hot):
        if start in seen:
            continue
        stack, cells = [start], []
        seen.add(start)
        while stack:
            row, column = stack.pop()
            cells.append((row, column))
            for neighbour in ((row + dr, column + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)):
                if neighbour in hot and neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        top = min(cell[0] for cell in cells) * tile * DOWNSCALE
        left = min(cell[1] for cell in cells) * tile * DOWNSCALE
        bottom = (max(cell[0] for cell in cells) + 1) * tile * DOWNSCALE
        right = (max(cell[1] for cell in cells) + 1) * tile * DOWNSCALE
        spots.append({
            "x": left, "y": top + top_offset, "width": right - left, "height": bottom - top,
            "tiles": len(cells),
        })
    spots.sort(key=lambda spot: spot["tiles"], reverse=True)
    return spots[:MAX_HOT_SPOTS]


def highlight(staging_crop, mask, spots, top_offset):
    overlay = Image.new("RGB", staging_crop.size, (255, 0, 0))
    full_mask = mask.resize(staging_crop.size, Image.NEAREST).point(lambda value: 140 if value else 0)
    image = Image.composite(overlay, staging_crop, full_mask)
    draw = ImageDraw.Draw(image)
    for spot in spots:
        top = spot["y"] - top_offset
        draw.rectangle((spot["x"], top, spot["x"] + spot["width"] - 1, top + spot["height"] - 1),
                       outline=(255, 140, 0), width=6)
    return image


def diff_sections(figma_png, staging_png, sections, output_path):
    """
    sections: [{"name", "y", "height", "offset"}] in Figma coordinates, where
    offset is how far the section sits lower (+) or higher (-) on staging.
    Returns one result per section and writes a Figma | Staging | Diff image.
    """
    figma = load_rgb(figma_png)
    staging = load_rgb(staging_png)
    width = min(figma.width, staging.width)
    figma = figma.crop((0, 0, width, figma.height))
    staging = staging.crop((0, 0, width, staging.height))

    figma_small = shrink(figma)
    staging_small = shrink(staging)

    results = []
    strips = []
    for section in sections:
        small_top = round(section["y"] / DOWNSCALE)
        small_height = max(1, round(section["height"] / DOWNSCALE))
        guess = round(section["offset"] / DOWNSCALE)
        small_offset = best_offset(figma_small, staging_small, small_top, small_height, guess)

        figma_small_crop = crop_padded(figma_small, small_top, small_height)
        mask = changed_mask(
            figma_small_crop,
            crop_padded(staging_small, small_top + small_offset, small_height),
        )
        mismatch = mask.histogram()[255] / max(1, mask.width * mask.height)
        stable_mask = shift_tolerant_mask(figma_small_crop, staging_small, small_top + small_offset, small_height)

        top = small_top * DOWNSCALE
        height = small_height * DOWNSCALE
        offset = small_offset * DOWNSCALE
        figma_crop = crop_padded(figma, top, height)
        staging_crop = crop_padded(staging, top + offset, height)
        section = {**section, "offset": offset}
        spots = hot_spots(stable_mask, top)
        results.append({
            **section,
            "staging_y": top + offset,
            "mismatch": mismatch,
            "regions": changed_regions(mask, top),
            "hot_spots": spots,
        })
        strips.append((section, figma_crop, staging_crop, highlight(staging_crop, mask, spots, top), mismatch))

    write_report_image(strips, width, output_path)
    return results


def write_report_image(strips, width, output_path):
    column = round(width * REPORT_SCALE)
    label_height = 28
    gap = 10
    total_height = sum(round(strip[1].height * REPORT_SCALE) + label_height for strip in strips) + label_height
    sheet = Image.new("RGB", (column * 3 + gap * 2, total_height), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, title in enumerate(("FIGMA", "STAGING", "DIFF (red = changed, orange box = localized change)")):
        draw.text((index * (column + gap) + 6, 8), title, fill=(0, 0, 0), font=font)

    y = label_height
    for section, figma_crop, staging_crop, diff_crop, mismatch in strips:
        draw.rectangle((0, y, sheet.width, y + label_height - 1), fill=(235, 235, 235))
        draw.text(
            (6, y + 8),
            f"{section['name']}  |  Figma y={section['y']:.0f}  |  staging offset {section['offset']:+.0f}px  |  {mismatch:.1%} changed",
            fill=(0, 0, 0), font=font,
        )
        y += label_height
        height = round(figma_crop.height * REPORT_SCALE)
        for index, image in enumerate((figma_crop, staging_crop, diff_crop)):
            sheet.paste(image.resize((column, max(1, height)), Image.BILINEAR), (index * (column + gap), y))
        y += height

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sheet.save(output_path, optimize=True)
