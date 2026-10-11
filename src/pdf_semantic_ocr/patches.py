"""Validated, replayable source-image repairs with optimistic preconditions."""
from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path

from .schema import KINDS, validate_page, validate_grid
from .storage import fingerprint, read_json, write_json


def apply_patch(run: Path, patch_path: Path):
    patch = read_json(patch_path)
    manifest = read_json(run / "manifest.json")
    if patch.get("pdf_sha256") != manifest["pdf_sha256"]:
        raise ValueError("Patch document hash mismatch")
    evidence = patch.get("evidence", {})
    if not evidence.get("method") or not evidence.get("note"):
        raise ValueError("Patch requires an evidence method and note; record original-image verification")
    if not patch.get("operations"):
        raise ValueError("Patch has no operations")
    patch_id = fingerprint(patch)
    # All operations are validated in memory before any page is changed.
    staged, paths = {}, {}
    for operation in patch["operations"]:
        number = operation["page"]
        if number not in staged:
            paths[number] = run / "pages" / f"{number:04d}.json"
            staged[number] = copy.deepcopy(read_json(paths[number]))
        page = staged[number]
        if any(r.get("patch_id") == patch_id for r in page["revisions"]):
            continue
        kind = operation["op"]
        if kind == "replace_text":
            line = next(item for item in page["lines"] if item["id"] == operation["line_id"])
            if line["text"] != operation["expected"]:
                raise ValueError("Text precondition failed; patch targets a different revision")
            line["text"] = operation["text"]
            for region in page["regions"]:
                if line["id"] in region["line_ids"]:
                    # A prior grid/group contains rendered text; invalidate it until reverified.
                    region.pop("grid", None)
                    region.pop("groups", None)
                    region.pop("review", None)
        elif kind == "restore_line":
            if any(item["id"] == operation["line_id"] for item in page["lines"]):
                raise ValueError("Restored line ID already exists")
            region = next(r for r in page["regions"] if r["id"] == operation["region_id"])
            page["lines"].append({"id": operation["line_id"], "text": operation["text"],
                                  "original_text": None, "bbox": operation["bbox"], "confidence": None,
                                  "engine": "source_image_review", "evidence": evidence})
            region["line_ids"].append(operation["line_id"])
            for key in ("grid", "groups", "review"):
                region.pop(key, None)
        elif kind == "reclassify":
            region = next(r for r in page["regions"] if r["id"] == operation["region_id"])
            if region["kind"] != operation["expected_kind"] or operation["kind"] not in KINDS:
                raise ValueError("Region kind precondition failed")
            region["kind"] = operation["kind"]
            region.pop("review", None)
            if operation["kind"] != "table":
                region.pop("grid", None)
        elif kind in {"set_table", "set_groups"}:
            region = next(r for r in page["regions"] if r["id"] == operation["region_id"])
            if kind == "set_table":
                if region["kind"] != "table":
                    raise ValueError("set_table requires a table region")
                if not isinstance(operation["grid"], dict):
                    raise ValueError("set_table requires a complete grid object")
                validate_grid(operation["grid"], region["line_ids"])
                region["grid"] = operation["grid"]
            else:
                if region["kind"] != "figure":
                    raise ValueError("set_groups requires a figure region")
                groups = operation["groups"]
                if not isinstance(groups, list) or not groups:
                    raise ValueError("set_groups requires nonempty source groups")
                if Counter(i for g in groups for i in g["line_ids"]) != Counter(region["line_ids"]):
                    raise ValueError("Figure groups must account for every source line")
                if not all(isinstance(g["text"], str) and g["text"].strip() for g in groups):
                    raise ValueError("Figure groups require nonempty text")
                region["groups"] = operation["groups"]
            region["review"] = {"status": "source_reviewed", "evidence": evidence, "patch_id": patch_id}
        elif kind == "move_line":
            source = next(r for r in page["regions"] if r["id"] == operation["from_region"])
            target = next(r for r in page["regions"] if r["id"] == operation["to_region"])
            source["line_ids"].remove(operation["line_id"])
            target["line_ids"].append(operation["line_id"])
            for region in (source, target):
                for key in ("grid", "groups", "review"):
                    region.pop(key, None)
        else:
            raise ValueError(f"Unknown patch operation: {kind}")
    for page in staged.values():
        validate_page(page)
    for number, page in staged.items():
        if not any(r.get("patch_id") == patch_id for r in page["revisions"]):
            page["revisions"].append({"patch_id": patch_id, "evidence": evidence})
            write_json(paths[number], page)
    write_json(run / "repairs" / f"{patch_id}.json", patch)
    return {"patch_id": patch_id, "pages": sorted(staged)}
