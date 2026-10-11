"""Engineering and anomaly evidence, deliberately separate from semantic acceptance."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .export import region_text
from .schema import validate_page
from .storage import read_json, records, write_json, write_text


def audit(run: Path):
    manifest = read_json(run / "manifest.json")
    issues, counts, processed = [], Counter(), []
    engineering_errors = []
    for path, page in records(run):
        processed.append(page["page"])
        try:
            validate_page(page)
            if page["pdf_sha256"] != manifest["pdf_sha256"]:
                raise ValueError("Page belongs to another document")
            if not 1 <= page["page"] <= manifest["total_pages"]:
                raise ValueError("Page number outside document")
            if path.stem != f"{page['page']:04d}":
                raise ValueError("Page file number mismatch")
            if not (run / "raw" / path.name).exists():
                raise ValueError("Original recognition record missing")
            raw = read_json(run / "raw" / path.name)
            if Counter(page.get("original_line_ids", [])) != Counter(line["id"] for line in raw["lines"]):
                raise ValueError("Original source-line ID baseline changed")
            if not (run / "images" / "pages" / f"{page['page']:04d}.png").exists():
                raise ValueError("Source page render missing")
        except (ValueError, KeyError, TypeError) as error:
            engineering_errors.append({"page": page.get("page"), "error": str(error)})
            continue
        if not page["lines"]:
            issues.append({"page": page["page"], "kind": "empty_page_candidate"})
        for line in page["lines"]:
            if line.get("confidence") is not None and line["confidence"] < 0.85:
                issues.append({"page": page["page"], "line": line["id"], "kind": "low_confidence",
                               "text": line["text"], "confidence": line["confidence"]})
            if "\ufffd" in line["text"]:
                issues.append({"page": page["page"], "line": line["id"], "kind": "replacement_character"})
        for region in page["regions"]:
            counts[region["kind"]] += 1
            if region["kind"] == "unassigned":
                issues.append({"page": page["page"], "region": region["id"], "kind": "unassigned_region"})
            if region["kind"] in {"table", "figure"} and not region.get("review"):
                issues.append({"page": page["page"], "region": region["id"], "kind": "relationship_not_reviewed"})
            if region["kind"] == "table":
                if not region.get("grid"):
                    issues.append({"page": page["page"], "region": region["id"], "kind": "table_without_grid"})
                elif region["grid"].get("unassigned_line_ids"):
                    issues.append({"page": page["page"], "region": region["id"], "kind": "table_lines_outside_cells",
                                   "line_ids": region["grid"]["unassigned_line_ids"]})
            text = region_text(page, region)
            if re.search(r"(.{4,80})\1{5,}", text.replace("\n", "")):
                issues.append({"page": page["page"], "region": region["id"], "kind": "repetition_candidate"})
            if "此位置隔离" in text or "禁止跨此处拼接" in text:
                issues.append({"page": page["page"], "region": region["id"], "kind": "review_placeholder"})
    expected = set(range(1, manifest["total_pages"] + 1))
    missing = sorted(expected - set(processed))
    requested_missing = sorted(set(manifest["requested_pages"]) - set(processed))
    report = {"pdf_sha256": manifest["pdf_sha256"], "total_pages": manifest["total_pages"],
              "processed_pages": processed, "missing_pages": missing, "requested_missing_pages": requested_missing,
              "full_document_coverage": not missing,
              "engineering_status": "PASS" if not engineering_errors and not requested_missing else "FAIL",
              "engineering_errors": engineering_errors, "region_counts": dict(counts),
              "issue_counts": dict(Counter(i["kind"] for i in issues)), "issues": issues,
              "semantic_acceptance": "NOT_CERTIFIED",
              "scope": "Source-line accounting and anomaly candidates. Confidence and absence of candidates do not prove correctness."}
    write_json(run / "audit.json", report)
    write_text(run / "audit.md", "# Extraction audit\n\n"
               f"Processed {len(processed)}/{manifest['total_pages']} pages. "
               f"Engineering: {report['engineering_status']}. Semantic acceptance: NOT_CERTIFIED.\n\n"
               "| Candidate | Count |\n| --- | ---: |\n" +
               "\n".join(f"| {k} | {v} |" for k, v in sorted(report["issue_counts"].items())) +
               "\n\nInspect audit.json and original page renders. Counts are review candidates, not measured errors.\n")
    return report
