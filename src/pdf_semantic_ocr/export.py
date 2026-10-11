"""Plain learning text and page/region assets; diagnostics stay in audit files."""
from __future__ import annotations

from pathlib import Path
from collections import Counter
from PIL import Image

from .geometry import join_lines, ordered_lines, reading_order, union
from .schema import validate_page
from .storage import records, write_json, write_text
from .tables import table_markdown, normalize

BODY_KINDS = {"text", "title", "formula", "unassigned"}


def region_text(page, region):
    by_id = {line["id"]: line for line in page["lines"]}
    lines = [by_id[i] for i in region["line_ids"]]
    if region.get("groups"):
        return "\n\n".join(g["text"] for g in region["groups"])
    if region.get("grid"):
        text = table_markdown(region["grid"])
        remaining = [by_id[i] for i in region["grid"].get("unassigned_line_ids", [])]
        # Ambiguous repeated labels may lack a unique provenance cell while their
        # characters are already fully represented. Do not duplicate them in text.
        conserved = Counter(normalize("".join(line["text"] for line in lines))) == Counter(
            normalize("".join(cell["text"] for cell in region["grid"]["cells"])))
        if remaining and not conserved:
            text += "\n\n" + "\n".join(item["text"] for item in ordered_lines(remaining))
        return text
    if region["kind"] in {"table", "figure"}:
        return "\n".join(item["text"] for item in ordered_lines(lines))
    return join_lines(lines, page.get("language", "auto"))


def page_texts(page):
    validate_page(page)
    body, auxiliary, combined = [], [], []
    # Empty photographs still produce crops, but cannot divide text into false
    # reading sections when their rectangles cross a column gutter.
    readable = [r for r in page["regions"] if r["line_ids"] or r.get("grid") or r.get("groups")]
    for region in reading_order(readable):
        if region["kind"] == "noise":
            continue
        value = region_text(page, region)
        if not value.strip():
            continue
        if region["kind"] == "title":
            value = "## " + value
        if region["kind"] in BODY_KINDS:
            body.append(value)
        else:
            auxiliary.append(value)
        combined.append(value)
    header = f"# PDF page {page['page']}\n\n"
    return tuple(header + "\n\n".join(parts) + "\n" for parts in (body, auxiliary, combined))


def export(run: Path):
    body, auxiliary, learning, assets = [], [], [], []
    for _, page in records(run):
        texts = page_texts(page)
        for accumulator, text in zip((body, auxiliary, learning), texts):
            accumulator.append(text)
        for suffix, text in zip(("", "_figures_tables", "_learning"), texts):
            write_text(run / "text" / f"{page['page']:04d}{suffix}.md", text)
        image_path = run / "images" / "pages" / f"{page['page']:04d}.png"
        with Image.open(image_path) as image:
            by_id = {item["id"]: item for item in page["lines"]}
            for region in page["regions"]:
                if region["kind"] not in {"figure", "table"}:
                    continue
                box = union([region["bbox"]] + [by_id[i]["bbox"] for i in region["line_ids"]])
                box = [max(0, int(box[0]) - 6), max(0, int(box[1]) - 6),
                       min(image.width, int(box[2]) + 7), min(image.height, int(box[3]) + 7)]
                target = run / "images" / "regions" / f"{page['page']:04d}_{region['id']}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                image.crop(box).save(target)
                assets.append({"page": page["page"], "region": region["id"], "kind": region["kind"],
                               "bbox": box, "path": target.relative_to(run).as_posix()})
    for name, parts in (("body", body), ("figures_tables", auxiliary), ("learning", learning)):
        write_text(run / f"{name}.md", "\n\n".join(parts))
    write_json(run / "assets.json", {"regions": assets,
               "scope": "Full-page renders and detected-region crops; not proof of every figure being detected"})
