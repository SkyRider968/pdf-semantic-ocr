"""Model output staging, stale-result detection and conservative integration."""
from __future__ import annotations

from pathlib import Path
from PIL import Image

from .backends import MLXTableBackend
from .geometry import union
from .schema import validate_page
from .storage import fingerprint, parse_pages, read_json, records, write_json
from .tables import parse_otsl, consensus_grid


def source_fingerprint(page, region):
    by_id = {line["id"]: line for line in page["lines"]}
    return fingerprint({"region": region, "lines": [by_id[i] for i in region["line_ids"]]})


def store_candidate(run, page, region, otsl, engine):
    candidate = {"pdf_sha256": page["pdf_sha256"], "page": page["page"], "region_id": region["id"],
                 "source_fingerprint": source_fingerprint(page, region), "engine": engine, "otsl": otsl,
                 "status": "candidate"}
    path = run / "candidates" / f"{page['page']:04d}_{region['id']}.json"
    write_json(path, candidate)
    return candidate


def import_candidate(run: Path, number: int, region_id: str, otsl_file: Path):
    page = read_json(run / "pages" / f"{number:04d}.json")
    region = next(r for r in page["regions"] if r["id"] == region_id)
    if region["kind"] != "table":
        raise ValueError("Candidate requires a table region")
    return store_candidate(run, page, region, otsl_file.read_text(encoding="utf-8"), "external_otsl")


def recognize_tables(run: Path, pages=None, model="mlx-community/PaddleOCR-VL-1.6-4bit"):
    manifest = read_json(run / "manifest.json")
    selected = set(parse_pages(pages, manifest["total_pages"]))
    tasks = []
    for _, page in records(run):
        if page["page"] not in selected:
            continue
        for region in page["regions"]:
            if region["kind"] != "table" or region.get("review"):
                continue
            cache = run / "candidates" / f"{page['page']:04d}_{region['id']}.json"
            if cache.exists():
                old = read_json(cache)
                if old["source_fingerprint"] == source_fingerprint(page, region) and old["engine"] == model:
                    continue
            tasks.append((page, region))
    if not tasks:
        return {"generated": 0}
    engine = MLXTableBackend(model)
    for page, region in tasks:
        by_id = {item["id"]: item for item in page["lines"]}
        box = union([region["bbox"]] + [by_id[i]["bbox"] for i in region["line_ids"]])
        with Image.open(run / "images" / "pages" / f"{page['page']:04d}.png") as image:
            crop = image.crop((max(0, int(box[0]) - 8), max(0, int(box[1]) - 8),
                               min(image.width, int(box[2]) + 9), min(image.height, int(box[3]) + 9))).convert("RGB")
            otsl = engine.recognize(crop)
        store_candidate(run, page, region, otsl, model)
        print(f"Staged table candidate {page['page']}:{region['id']}", flush=True)
    return {"generated": len(tasks)}


def integrate(run: Path):
    manifest = read_json(run / "manifest.json")
    results = []
    for path in sorted((run / "candidates").glob("*.json")):
        candidate = read_json(path)
        page_path = run / "pages" / f"{candidate['page']:04d}.json"
        page = read_json(page_path)
        region = next(r for r in page["regions"] if r["id"] == candidate["region_id"])
        candidate_id = fingerprint(candidate)
        if region.get("candidate_id") == candidate_id:
            evidence = {"status": "already_applied"}
        elif region.get("review"):
            evidence = {"status": "skipped_source_reviewed"}
        elif candidate["pdf_sha256"] != manifest["pdf_sha256"]:
            evidence = {"status": "rejected", "reason": "document_mismatch"}
        elif region["kind"] != "table" or candidate["source_fingerprint"] != source_fingerprint(page, region):
            evidence = {"status": "rejected", "reason": "stale_source"}
        else:
            try:
                parsed = parse_otsl(candidate["otsl"])
                by_id = {item["id"]: item for item in page["lines"]}
                grid, evidence = consensus_grid([by_id[i] for i in region["line_ids"]], parsed)
                if grid:
                    region["grid"] = grid
                    region["candidate_evidence"] = evidence
                    region["candidate_id"] = candidate_id
                    validate_page(page)
                    write_json(page_path, page)
            except (ValueError, KeyError) as error:
                evidence = {"status": "rejected", "reason": "invalid_structure", "detail": str(error)}
        results.append({"page": candidate["page"], "region_id": candidate["region_id"], **evidence})
    report = {"tables": results, "scope": "Automated supporting evidence, not original-image semantic acceptance"}
    write_json(run / "candidate_audit.json", report)
    return report
