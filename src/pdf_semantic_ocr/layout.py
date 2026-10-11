"""Native PDF layout and conservative ruled-table fallback for raster pages."""
from __future__ import annotations

import cv2
import numpy as np

from .geometry import area, overlap, union, join_lines
from .schema import validate_grid


def clusters(values, gap=5):
    groups = []
    for v in values:
        if not groups or v - groups[-1][-1] > gap:
            groups.append([v])
        else:
            groups[-1].append(v)
    return [float(np.mean(g)) for g in groups]


def ruled_tables(image):
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 31, 12)
    h, w = binary.shape
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                 cv2.getStructuringElement(cv2.MORPH_RECT, (max(35, w // 20), 1)))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(35, h // 35))))
    mask = cv2.bitwise_or(horizontal, vertical)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width < w * 0.15 or height < 45:
            continue
        hmask, vmask = horizontal[y:y + height, x:x + width], vertical[y:y + height, x:x + width]
        xs = clusters(np.flatnonzero((vmask > 0).sum(axis=0) > height * 0.25))
        ys = clusters(np.flatnonzero((hmask > 0).sum(axis=1) > width * 0.25))
        if len(xs) < 3 or len(ys) < 3:
            continue
        xs, ys = [v + x for v in xs], [v + y for v in ys]
        regions.append({"kind": "table", "bbox": [x, y, x + width, y + height],
                        "method": "visible_rules", "rule_xs": xs, "rule_ys": ys})
    return regions


def ruled_grid(image, region, lines, language):
    """Do not claim merges are resolved: reject any incomplete interior boundary."""
    xs, ys = region["rule_xs"], region["rule_ys"]
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    cells = []
    for r in range(len(ys) - 1):
        for c in range(len(xs) - 1):
            for axis, position, first, last in ((0, xs[c + 1], ys[r], ys[r + 1]),
                                                (1, ys[r + 1], xs[c], xs[c + 1])):
                if axis == 0 and c == len(xs) - 2 or axis == 1 and r == len(ys) - 2:
                    continue
                p, a, b = int(position), int(first) + 5, int(last) - 5
                stripe = gray[a:b, max(0, p - 2):p + 3] if axis == 0 else gray[max(0, p - 2):p + 3, a:b]
                if not stripe.size or (stripe < 180).any(axis=1 if axis == 0 else 0).mean() < 0.7:
                    return None
            cells.append({"row": r, "column": c, "rowspan": 1, "colspan": 1,
                          "bbox": [xs[c], ys[r], xs[c + 1], ys[r + 1]], "line_ids": [], "text": ""})
    return fill_grid({"row_count": len(ys) - 1, "column_count": len(xs) - 1,
                      "cells": cells, "method": "visible_rules_no_merges"}, lines, language)


def fill_grid(grid, lines, language):
    unassigned = []
    assigned = {i: [] for i in range(len(grid["cells"]))}
    for line in lines:
        matches = [i for i, cell in enumerate(grid["cells"])
                   if overlap(line["bbox"], cell["bbox"]) / max(1, area(line["bbox"])) >= 0.65]
        if len(matches) == 1:
            assigned[matches[0]].append(line)
        else:
            unassigned.append(line["id"])
    for i, cell in enumerate(grid["cells"]):
        cell["line_ids"] = [line["id"] for line in assigned[i]]
        cell["text"] = join_lines(assigned[i], language)
    grid["unassigned_line_ids"] = unassigned
    validate_grid(grid, [line["id"] for line in lines])
    return grid


def native_tables(page, scale):
    result = []
    finder = page.find_tables()
    for table in finder.tables:
        # Null slots arise from merges. Infer span from the source cell rectangle.
        xs = sorted(set(round(v, 2) for cell in table.cells if cell for v in (cell[0], cell[2])))
        ys = sorted(set(round(v, 2) for cell in table.cells if cell for v in (cell[1], cell[3])))
        cells = []
        for cell in table.cells:
            if not cell:
                continue
            left, top, right, bottom = [round(v, 2) for v in cell]
            cells.append({"row": ys.index(top), "column": xs.index(left),
                          "rowspan": ys.index(bottom) - ys.index(top),
                          "colspan": xs.index(right) - xs.index(left),
                          "bbox": [v * scale for v in cell], "text": "", "line_ids": []})
        grid = {"row_count": len(ys) - 1, "column_count": len(xs) - 1, "cells": cells,
                "unassigned_line_ids": [], "method": "pdf_native_geometry"}
        try:
            validate_grid(grid)
        except ValueError:
            grid = None
        result.append({"kind": "table", "bbox": [v * scale for v in table.bbox],
                       "method": "pdf_native_geometry", "grid_template": grid})
    return result


def native_figures(page, scale, table_regions, use_ocr):
    regions = []
    for info in page.get_image_info():
        box = [v * scale for v in info["bbox"]]
        if use_ocr and area(box) > page.rect.width * page.rect.height * scale ** 2 * 0.4:
            continue
        regions.append({"kind": "figure", "bbox": box, "method": "pdf_image_instance"})
    drawing_boxes = []
    for drawing in page.get_drawings():
        box = [v * scale for v in drawing["rect"]]
        if area(box) < 100 or any(overlap(box, t["bbox"]) / max(1, area(box)) > 0.8 for t in table_regions):
            continue
        drawing_boxes.append(box)
    groups = []
    for box in drawing_boxes:
        touching = [g for g in groups if overlap([box[0] - 20, box[1] - 20, box[2] + 20, box[3] + 20], g)]
        if touching:
            for g in touching:
                groups.remove(g)
            groups.append(union([box] + touching))
        else:
            groups.append(box)
    for box in groups:
        if box[2] - box[0] < 60 or box[3] - box[1] < 40:
            continue
        regions.append({"kind": "figure", "bbox": box, "method": "pdf_drawing_cluster"})
    return regions


def fallback_text_regions(lines, size):
    """Lightweight grouping. It does not replace a trained layout detector."""
    if not lines:
        return []
    heights = [line["bbox"][3] - line["bbox"][1] for line in lines]
    typical = float(np.median(heights))
    full, left, right = [], [], []
    middle = size[0] / 2
    for line in lines:
        box = line["bbox"]
        if box[3] - box[1] > typical * 1.4 or box[0] < middle < box[2]:
            full.append(line)
        elif box[2] <= middle:
            left.append(line)
        else:
            right.append(line)
    columns = [left, right] if left and right else [left + right]
    regions = [{"kind": "title" if item["bbox"][3] - item["bbox"][1] > typical * 1.4 else "text",
                "bbox": item["bbox"], "method": "heuristic_text_group"} for item in full]
    for column in columns:
        groups = []
        for line in sorted(column, key=lambda item: item["bbox"][1]):
            if not groups or line["bbox"][1] - groups[-1][-1]["bbox"][3] > typical * 1.2:
                groups.append([line])
            else:
                groups[-1].append(line)
        regions.extend({"kind": "text", "bbox": union([item["bbox"] for item in g]),
                        "method": "heuristic_text_group"} for g in groups)
    return regions


def assign(lines, regions, size):
    for i, region in enumerate(regions):
        region["id"] = f"r{i:03d}"
        region["line_ids"] = []
        region["bbox"] = [max(0, region["bbox"][0]), max(0, region["bbox"][1]),
                          min(size[0], region["bbox"][2]), min(size[1], region["bbox"][3])]
    for line in lines:
        candidates = []
        for region in regions:
            coverage = overlap(line["bbox"], region["bbox"]) / max(1, area(line["bbox"]))
            if coverage >= 0.45:
                priority = 2 if region["kind"] == "table" else 1 if region["kind"] == "figure" else 0
                candidates.append((priority, coverage, -area(region["bbox"]), region))
        if candidates:
            winner = max(candidates, key=lambda c: c[:3])[3]
        else:
            winner = {"id": f"r{len(regions):03d}", "kind": "unassigned", "bbox": line["bbox"],
                      "line_ids": [], "method": "unmatched_preserved"}
            regions.append(winner)
        winner["line_ids"].append(line["id"])
    by_id = {line["id"]: line for line in lines}
    for region in regions:
        if region["line_ids"] and region["kind"] in {"text", "title", "unassigned", "figure_caption"}:
            region["bbox"] = union([by_id[i]["bbox"] for i in region["line_ids"]])
    return [r for r in regions if r["line_ids"] or r["kind"] in {"figure", "table"}]
