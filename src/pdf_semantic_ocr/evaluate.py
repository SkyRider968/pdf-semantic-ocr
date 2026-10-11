"""Source transcriptions measure samples; they never certify an entire corpus."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .export import BODY_KINDS, region_text
from .geometry import area, overlap, reading_order, join_lines
from .storage import fingerprint, read_json, write_json


def normalize(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def edit_counts(reference, prediction):
    # Tuple order: edit cost, deletions, insertions, substitutions, matches.
    previous = [(i, 0, i, 0, 0) for i in range(len(prediction) + 1)]
    for row, expected in enumerate(reference, 1):
        current = [(row, row, 0, 0, 0)]
        for column, actual in enumerate(prediction, 1):
            cost, deleted, inserted, substituted, matched = previous[column - 1]
            diagonal = (cost + (actual != expected), deleted, inserted,
                        substituted + (actual != expected), matched + (actual == expected))
            cost, deleted, inserted, substituted, matched = previous[column]
            deletion = (cost + 1, deleted + 1, inserted, substituted, matched)
            cost, deleted, inserted, substituted, matched = current[column - 1]
            insertion = (cost + 1, deleted, inserted + 1, substituted, matched)
            current.append(min((diagonal, deletion, insertion), key=lambda item: (item[0], -item[4])))
        previous = current
    distance, deleted, inserted, substituted, matched = previous[-1]
    return {"reference_characters": len(reference), "output_characters": len(prediction),
            "distance": distance, "deletions": deleted, "insertions": inserted,
            "substitutions": substituted, "matches": matched}


def metrics(counts):
    total = counts["reference_characters"]
    if total == 0:
        return {**counts, "accuracy_percent": None, "completeness_percent": None, "correct_recall_percent": None}
    return {**counts, "accuracy_percent": round(100 * max(0, 1 - counts["distance"] / total), 3),
            "completeness_percent": round(100 * (1 - counts["deletions"] / total), 3),
            "correct_recall_percent": round(100 * counts["matches"] / total, 3)}


def sample_text(page, sample):
    if sample.get("bbox"):
        box = sample["bbox"]
        if sample.get("normalized_bbox", True):
            box = [v * page["size"][i % 2] for i, v in enumerate(box)]
        by_id = {line["id"]: line for line in page["lines"]}
        pieces = []
        for region in reading_order([r for r in page["regions"] if r["line_ids"]]):
            lines = [by_id[i] for i in region["line_ids"]
                     if overlap(by_id[i]["bbox"], box) / max(1, area(by_id[i]["bbox"])) > 0.5]
            if lines:
                pieces.append(join_lines(lines, page.get("language", "auto")))
        return "\n".join(pieces)
    region_id = sample.get("region_id")
    selected = [r for r in reading_order(page["regions"]) if
                (r["id"] == region_id if region_id else r["kind"] in BODY_KINDS)]
    return "\n".join(region_text(page, r) for r in selected)


def evaluate(run: Path, gold_path: Path, minimum=95.0):
    if not 0 <= minimum <= 100:
        raise ValueError("minimum must be between 0 and 100")
    gold = read_json(gold_path)
    manifest = read_json(run / "manifest.json")
    if gold.get("pdf_sha256") and gold["pdf_sha256"] != manifest["pdf_sha256"]:
        raise ValueError("Gold reference belongs to a different PDF")
    if not gold.get("samples") and not gold.get("tables"):
        raise ValueError("Gold file contains no samples")
    total = dict.fromkeys(("reference_characters", "output_characters", "distance", "deletions",
                          "insertions", "substitutions", "matches"), 0)
    results, table_results, revisions = [], [], {}
    for sample in gold.get("samples", []):
        path = run / "pages" / f"{sample['page']:04d}.json"
        page = read_json(path) if path.exists() else None
        expected = normalize(sample["reference"])
        if not expected:
            raise ValueError("Empty gold text cannot measure accuracy")
        actual = sample_text(page, sample) if page else ""
        counts = edit_counts(expected, normalize(actual))
        for key, value in counts.items():
            total[key] += value
        results.append({"id": sample.get("id"), "page": sample["page"], "split": sample.get("split", "unspecified"),
                        "status": "measured" if page else "missing_page", "metrics": metrics(counts),
                        "reference": sample["reference"], "prediction": actual})
        if page:
            revisions[str(page["page"])] = fingerprint(page)
    correct_cells = reference_cells = 0
    for sample in gold.get("tables", []):
        path = run / "pages" / f"{sample['page']:04d}.json"
        page = read_json(path) if path.exists() else None
        region = None
        if page:
            candidates = [r for r in page["regions"] if r["kind"] == "table"]
            if sample.get("region_id"):
                region = next((r for r in candidates if r["id"] == sample["region_id"]), None)
            elif sample.get("bbox"):
                box = [v * page["size"][i % 2] for i, v in enumerate(sample["bbox"])]
                candidates = [r for r in candidates if overlap(r["bbox"], box) / max(1, area(box)) > 0.5]
                if len(candidates) == 1:
                    region = candidates[0]
            revisions[str(page["page"])] = fingerprint(page)
        grid = region.get("grid") if region else None
        predicted = {(c["row"], c["column"]): c for c in grid["cells"]} if grid else {}
        failures = []
        for expected in sample["cells"]:
            reference_cells += 1
            actual = predicted.get((expected["row"], expected["column"]))
            exact = bool(actual) and normalize(actual["text"]) == normalize(expected["text"])
            exact = exact and all(actual.get(key, 1) == expected.get(key, 1) for key in ("rowspan", "colspan"))
            correct_cells += bool(exact)
            if not exact:
                failures.append({"reference": expected, "prediction": actual})
        expected_positions = {(c["row"], c["column"]) for c in sample["cells"]}
        extras = sorted(set(predicted) - expected_positions) if sample.get("complete_table", True) else []
        table_results.append({"id": sample.get("id"), "page": sample["page"],
                              "split": sample.get("split", "unspecified"), "failures": failures,
                              "extra_cell_positions": extras, "grid_present": grid is not None})
    aggregate = metrics(total)
    text_pass = not results or (aggregate["accuracy_percent"] >= minimum and aggregate["completeness_percent"] >= minimum)
    table_percent = 100 * correct_cells / reference_cells if reference_cells else None
    table_pass = not table_results or (table_percent is not None and table_percent >= minimum
                                       and not any(t["extra_cell_positions"] for t in table_results))
    report = {"pdf_sha256": manifest["pdf_sha256"], "gold_sha256": fingerprint(gold),
              "page_fingerprints": revisions, "normalization": "NFKC and whitespace removal; punctuation retained",
              "text": aggregate, "samples": results,
              "table_cells": {"reference": reference_cells, "exact": correct_cells, "exact_percent": table_percent},
              "tables": table_results, "minimum_percent": minimum,
              "sample_status": "PASS" if text_pass and table_pass else "FAIL",
              "scope": "Selected source transcriptions only. Development and corrected samples are regressions, not independent holdouts."}
    write_json(run / "evaluation.json", report)
    return report
