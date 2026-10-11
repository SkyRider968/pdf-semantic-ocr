"""Loss accounting checks. Passing these does not prove the OCR recognized everything."""
from __future__ import annotations

from collections import Counter
import math

KINDS = {"text", "title", "figure", "figure_caption", "table", "table_caption",
         "table_footnote", "formula", "unassigned", "noise", "page_marker"}


def validate_bbox(box, size=None):
    if len(box) != 4 or not all(isinstance(n, (float, int)) and math.isfinite(n) for n in box):
        raise ValueError("bbox must contain four finite coordinates")
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("bbox must have positive area")
    if size and (box[0] < 0 or box[1] < 0 or box[2] > size[0] + 1 or box[3] > size[1] + 1):
        raise ValueError("bbox is outside the rendered page")


def validate_grid(grid, available_ids=None):
    rows, columns = grid["row_count"], grid["column_count"]
    if not isinstance(rows, int) or not isinstance(columns, int) or rows < 1 or columns < 1:
        raise ValueError("Invalid table dimensions")
    if rows * columns > 100000:
        raise ValueError("Table exceeds structural size limit")
    slots = set()
    assigned = []
    for cell in grid["cells"]:
        r, c = cell["row"], cell["column"]
        rs, cs = cell.get("rowspan", 1), cell.get("colspan", 1)
        if not all(isinstance(n, int) for n in (r, c, rs, cs)) or min(r, c) < 0 or min(rs, cs) < 1:
            raise ValueError("Invalid cell position/span")
        if r + rs > rows or c + cs > columns:
            raise ValueError("Cell extends beyond table")
        if not isinstance(cell["text"], str):
            raise ValueError("Cell text must be a string")
        for i in range(r, r + rs):
            for j in range(c, c + cs):
                if (i, j) in slots:
                    raise ValueError("Overlapping merged cells")
                slots.add((i, j))
        assigned.extend(cell.get("line_ids", []))
    if len(slots) != rows * columns:
        raise ValueError("Table has missing logical cells")
    assigned.extend(grid.get("unassigned_line_ids", []))
    if available_ids is not None and Counter(assigned) != Counter(available_ids):
        raise ValueError("Table source-line accounting mismatch")


def validate_page(page):
    ids = [line["id"] for line in page["lines"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate line IDs")
    if len({r["id"] for r in page["regions"]}) != len(page["regions"]):
        raise ValueError("Duplicate region IDs")
    for line in page["lines"]:
        validate_bbox(line["bbox"], page["size"])
        if not isinstance(line["text"], str):
            raise ValueError("Line text must be a string")
    assigned = []
    for region in page["regions"]:
        if region["kind"] not in KINDS:
            raise ValueError("Unknown region kind")
        validate_bbox(region["bbox"], page["size"])
        assigned.extend(region["line_ids"])
        if region.get("grid"):
            validate_grid(region["grid"], region["line_ids"])
        if region.get("groups"):
            grouped = [i for group in region["groups"] for i in group["line_ids"]]
            if Counter(grouped) != Counter(region["line_ids"]):
                raise ValueError("Figure group source-line accounting mismatch")
    if Counter(assigned) != Counter(ids):
        raise ValueError("Each recognized line must belong to exactly one region")
    if not set(page.get("original_line_ids", ids)).issubset(ids):
        raise ValueError("Original recognized lines were removed")
