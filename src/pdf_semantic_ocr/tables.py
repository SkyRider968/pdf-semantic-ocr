"""OTSL parsing and conservative integration of model-generated table candidates."""
from __future__ import annotations

import copy
import re
import unicodedata
from collections import Counter, defaultdict
from statistics import median

from .schema import validate_grid

CONTROLS = {"<fcel>", "<ecel>", "<lcel>", "<ucel>", "<xcel>", "<nl>"}
TOKEN = r"(<(?:fcel|ecel|lcel|ucel|xcel|nl)>)"


def normalize(text):
    # Preserve comparison signs, minus signs and units. Whitespace/NFKC only.
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def plain_math(text):
    for command, value in [(r"\mu", "μ"), (r"\times", "×"), (r"\leq", "≤"), (r"\geq", "≥")]:
        text = text.replace(command, value)
    text = re.sub(r"\\(?:text|mathrm)\{([^{}]*)\}", r"\1", text)
    text = text.replace(r"\(", "").replace(r"\)", "")
    text = re.sub(r"\^\{(?:\{)?(\*+)(?:\})?\}", r"\1", text)
    text = re.sub(r"\^\{\[([0-9, -]+)\]\}", r"[\1]", text)
    return text.strip()


def parse_otsl(text):
    if not re.search(TOKEN, text):
        raise ValueError("Missing OTSL tokens")
    stripped = re.sub(TOKEN, "", text)
    if re.search(r"</?[A-Za-z][^>]*>", stripped):
        raise ValueError("Unexpected markup in OTSL")
    tokens = re.split(TOKEN, text)
    if tokens[0].strip():
        raise ValueError("Unexpected content before table")
    cells, slots, widths = [], {}, []
    row = column = 0
    for index, token in enumerate(tokens):
        if token == "<nl>":
            if column == 0:
                raise ValueError("Empty logical row")
            widths.append(column)
            row += 1
            column = 0
        elif token in {"<fcel>", "<ecel>"}:
            content = tokens[index + 1] if index + 1 < len(tokens) and tokens[index + 1] not in CONTROLS else ""
            if token == "<ecel>" and content.strip():
                raise ValueError("Empty cell token has text")
            cell = {"row": row, "column": column, "rowspan": 1, "colspan": 1,
                    "text": plain_math(content), "line_ids": []}
            cells.append(cell)
            slots[(row, column)] = cell
            column += 1
        elif token == "<lcel>":
            cell = slots.get((row, column - 1))
            if cell is None:
                raise ValueError("Invalid horizontal merge")
            cell["colspan"] = max(cell["colspan"], column - cell["column"] + 1)
            slots[(row, column)] = cell
            column += 1
        elif token in {"<ucel>", "<xcel>"}:
            cell = slots.get((row - 1, column))
            if cell is None or (token == "<xcel>" and slots.get((row, column - 1)) is not cell):
                raise ValueError("Invalid vertical/rectangular merge")
            cell["rowspan"] = max(cell["rowspan"], row - cell["row"] + 1)
            slots[(row, column)] = cell
            column += 1
        elif token.strip() and index > 0 and tokens[index - 1] not in {"<fcel>", "<ecel>"}:
            raise ValueError("Unexpected text after control token")
    if column:
        widths.append(column)
        row += 1
    if not cells or len(set(widths)) != 1:
        raise ValueError(f"Missing/ragged table rows: {widths}")
    for cell in cells:
        for r in range(cell["row"], cell["row"] + cell["rowspan"]):
            for c in range(cell["column"], cell["column"] + cell["colspan"]):
                if slots.get((r, c)) is not cell:
                    raise ValueError("Nonrectangular merged cell")
    grid = {"row_count": row, "column_count": widths[0], "cells": cells,
            "unassigned_line_ids": [], "method": "otsl"}
    validate_grid(grid)
    return grid


def consensus_grid(lines, candidate):
    """Supporting evidence only. Repeated identical cell text may remain ambiguous."""
    grid = copy.deepcopy(candidate)
    validate_grid(grid)
    source = Counter(normalize("".join(line["text"] for line in lines)))
    predicted = Counter(normalize("".join(cell["text"] for cell in grid["cells"])))
    if source != predicted:
        return None, {"status": "rejected", "reason": "text_disagreement",
                      "missing_characters": sum((source - predicted).values()),
                      "extra_characters": sum((predicted - source).values())}
    anchors = defaultdict(list)
    for cell in grid["cells"]:
        cell["line_ids"] = []
    grid["unassigned_line_ids"] = []
    for line in lines:
        value = normalize(line["text"])
        matches = [i for i, cell in enumerate(grid["cells"]) if value and value in normalize(cell["text"])]
        if len(matches) == 1:
            grid["cells"][matches[0]]["line_ids"].append(line["id"])
            if len(value) >= 2:
                anchors[matches[0]].append(line["bbox"])
        else:
            grid["unassigned_line_ids"].append(line["id"])
    nonempty = sum(bool(normalize(c["text"])) for c in grid["cells"])
    if len(anchors) < max(3, nonempty * 0.4):
        return None, {"status": "rejected", "reason": "insufficient_unique_anchors", "anchors": len(anchors)}
    located = [(grid["cells"][i], median((r[0] + r[2]) / 2 for r in boxes),
                median((r[1] + r[3]) / 2 for r in boxes)) for i, boxes in anchors.items()]
    for i, (a, ax, ay) in enumerate(located):
        for b, bx, by in located[i + 1:]:
            if a["row"] + a["rowspan"] <= b["row"] and ay > by + 8:
                return None, {"status": "rejected", "reason": "row_coordinate_conflict"}
            if b["row"] + b["rowspan"] <= a["row"] and by > ay + 8:
                return None, {"status": "rejected", "reason": "row_coordinate_conflict"}
            if a["column"] + a["colspan"] <= b["column"] and ax > bx + 15:
                return None, {"status": "rejected", "reason": "column_coordinate_conflict"}
            if b["column"] + b["colspan"] <= a["column"] and bx > ax + 15:
                return None, {"status": "rejected", "reason": "column_coordinate_conflict"}
    validate_grid(grid, [line["id"] for line in lines])
    return grid, {"status": "automated_evidence", "anchors": len(anchors),
                  "scope": "Character multiset and unique-anchor coordinate agreement; not semantic acceptance"}


def table_markdown(grid):
    validate_grid(grid)
    rows = [[""] * grid["column_count"] for _ in range(grid["row_count"])]
    for cell in grid["cells"]:
        value = cell["text"].replace("|", r"\|").replace("\n", "<br>")
        for r in range(cell["row"], cell["row"] + cell.get("rowspan", 1)):
            for c in range(cell["column"], cell["column"] + cell.get("colspan", 1)):
                rows[r][c] = value
    result = ["| " + " | ".join(row) + " |" for row in rows]
    result.insert(1, "| " + " | ".join(["---"] * grid["column_count"]) + " |")
    return "\n".join(result)
