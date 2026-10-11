"""Coordinate-only ordering; diagrams do not imply causal relationships."""
from __future__ import annotations

import re


def area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def overlap(a, b):
    return area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def reading_order(nodes):
    """Recursive whitespace cuts, preserving columns under full-width headings."""
    if len(nodes) < 2:
        return nodes
    for axis in (1, 0):
        ordered = sorted(nodes, key=lambda n: n["bbox"][axis])
        end = ordered[0]["bbox"][axis + 2]
        cuts = []
        for i, node in enumerate(ordered[1:], 1):
            gap = node["bbox"][axis] - end
            if gap > 0.5:
                cuts.append((gap, i))
            end = max(end, node["bbox"][axis + 2])
        if cuts:
            # Horizontal sections first; the largest vertical gap separates columns.
            index = cuts[0][1] if axis == 1 else max(cuts)[1]
            return reading_order(ordered[:index]) + reading_order(ordered[index:])
    return sorted(nodes, key=lambda n: (n["bbox"][1], n["bbox"][0]))


def ordered_lines(lines):
    rows = []
    for line in sorted(lines, key=lambda item: item["bbox"][1]):
        box = line["bbox"]
        target = next((r for r in rows if min(r["bottom"], box[3]) - max(r["top"], box[1])
                       > min(r["bottom"] - r["top"], box[3] - box[1]) * 0.5), None)
        if target is None:
            target = {"top": box[1], "bottom": box[3], "lines": []}
            rows.append(target)
        target["lines"].append(line)
    return [line for row in rows for line in sorted(row["lines"], key=lambda item: item["bbox"][0])]


def join_lines(lines, language="auto"):
    result = ""
    for line in ordered_lines(lines):
        text = line["text"].strip()
        if not text:
            continue
        is_list = re.match(r"^(?:[•●①②③④⑤]|\d{1,3}[.、]\s*|[a-d][.)]\s+)", text)
        if not result:
            separator = ""
        elif is_list:
            separator = "\n"
        elif language == "en" or (re.search(r"[A-Za-z0-9.!?:;)]$", result) and re.match(r"[A-Za-z0-9]", text)):
            separator = " "
        else:
            separator = ""
        result += separator + text
    return result
