"""Input-independent extraction with resumable, configuration-checked page caches."""
from __future__ import annotations

import copy
import importlib.metadata
import re
import time
from pathlib import Path

import pymupdf
from PIL import Image

from . import __version__
from .backends import DocLayoutBackend, ocr_backend
from .geometry import area, overlap, union, join_lines
from .layout import assign, fallback_text_regions, fill_grid, native_figures, native_tables, ruled_grid, ruled_tables
from .schema import validate_page
from .storage import SCHEMA_VERSION, file_hash, fingerprint, parse_pages, read_json, write_json


def dependency_versions():
    result = {}
    for name in ("PyMuPDF", "rapidocr", "onnxruntime", "doclayout-yolo", "pyobjc-framework-Vision"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def implementation_hash():
    return fingerprint({p.name: file_hash(p) for p in sorted(Path(__file__).parent.glob("*.py"))})


def native_lines(page, scale):
    lines, regions = [], []
    data = page.get_text("dict")
    for block in data["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            text = "".join(s["text"] for s in line["spans"])
            if not text.strip():
                continue
            lines.append({"text": text, "confidence": None, "engine": "pdf_text_layer",
                          "bbox": [v * scale for v in line["bbox"]]})
        regions.append({"kind": "text", "bbox": [v * scale for v in block["bbox"]], "method": "pdf_text_block"})
    return lines, regions


def needs_ocr(page, native, mode):
    if mode == "always":
        return True
    if mode == "never":
        return False
    image_area = max((area(info["bbox"]) for info in page.get_image_info()), default=0)
    return image_area > page.rect.width * page.rect.height * 0.4 or (
        image_area > 0 and sum(len(item["text"]) for item in native) < 40)


def extract(pdf: Path, run: Path, *, pages=None, dpi=200, ocr="auto", backend="rapidocr",
            layout="native", weights=None, language="auto", threads=4):
    if dpi < 72 or dpi > 600:
        raise ValueError("DPI must be between 72 and 600")
    if threads < 1:
        raise ValueError("threads must be positive")
    pdf = pdf.resolve()
    config = {"dpi": dpi, "ocr": ocr, "backend": backend, "layout": layout,
              "language": language, "threads": threads, "tool_version": __version__,
              "implementation_sha256": implementation_hash(),
              "dependencies": dependency_versions(), "weights_sha256": file_hash(Path(weights)) if weights else None}
    if layout == "doclayout" and not weights:
        raise ValueError("--layout doclayout requires --layout-weights PATH; see docs/models.md")
    source_hash = file_hash(pdf)
    cache_key = fingerprint({"pdf_sha256": source_hash, "config": config})
    manifest_path = run / "manifest.json"
    if manifest_path.exists():
        old = read_json(manifest_path)
        if old["cache_key"] != cache_key:
            raise ValueError("Output directory belongs to another input/configuration. Choose a new output directory.")
    with pymupdf.open(pdf) as document:
        if document.needs_pass:
            raise ValueError("Encrypted PDF needs a decrypted local copy")
        selected = parse_pages(pages, len(document))
        old_selected = read_json(manifest_path).get("requested_pages", []) if manifest_path.exists() else []
        manifest = {"schema_version": SCHEMA_VERSION, "tool_version": __version__, "pdf_sha256": source_hash,
                    "source_name": pdf.name, "total_pages": len(document), "config": config, "cache_key": cache_key,
                    "requested_pages": sorted(set(selected + old_selected))}
        run.mkdir(parents=True, exist_ok=True)
        write_json(manifest_path, manifest)
        ocr_engine = None
        detector = DocLayoutBackend(weights) if layout == "doclayout" else None
        for number in selected:
            path = run / "pages" / f"{number:04d}.json"
            if path.exists():
                cached = read_json(path)
                validate_page(cached)
                if cached["pdf_sha256"] != source_hash:
                    raise ValueError("Cached page belongs to another input")
                if not (run / "raw" / path.name).exists():
                    raise ValueError("Cached page lost its original record; recover raw evidence or use a new output")
                image_path = run / "images" / "pages" / f"{number:04d}.png"
                if not image_path.exists():
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    document[number - 1].get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), alpha=False).save(image_path)
                continue
            start = time.monotonic()
            page = document[number - 1]
            scale = dpi / 72
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            image_path = run / "images" / "pages" / f"{number:04d}.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(image_path)
            lines, _ = native_lines(page, scale)
            use_ocr = needs_ocr(page, lines, ocr)
            if use_ocr:
                if ocr_engine is None:
                    ocr_engine = ocr_backend(backend, language, threads)
                observations = ocr_engine.recognize(image)
                for observation in observations:
                    observation["engine"] = ocr_engine.name
                # Digital captions on scanned pages are retained if spatially unmatched.
                if ocr != "always":
                    for line in lines:
                        matches = [item for item in observations if overlap(item["bbox"], line["bbox"]) /
                                   max(1, min(area(item["bbox"]), area(line["bbox"]))) > 0.6]
                        if not matches:
                            observations.append(line)
                lines = observations
            for i, line in enumerate(lines):
                line["id"] = f"p{number:04d}-l{i:05d}"
                line["original_text"] = line["text"]
                # Some engines return subpixel boxes just outside page borders.
                line["bbox"] = [max(0, line["bbox"][0]), max(0, line["bbox"][1]),
                                min(image.width, line["bbox"][2]), min(image.height, line["bbox"][3])]
            if detector:
                regions = detector.detect(image)
                ruled = ruled_tables(image)
                native = native_tables(page, scale) if not use_ocr else []
                for region in regions:
                    if region["kind"] == "table":
                        native_matches = [r for r in native if overlap(r["bbox"], region["bbox"]) /
                                          max(1, min(area(r["bbox"]), area(region["bbox"]))) > 0.8]
                        if len(native_matches) == 1:
                            region["grid_template"] = native_matches[0].get("grid_template")
                        matches = [r for r in ruled if overlap(r["bbox"], region["bbox"]) /
                                   max(1, min(area(r["bbox"]), area(region["bbox"]))) > 0.8]
                        if len(matches) == 1:
                            region.update({k: matches[0][k] for k in ("rule_xs", "rule_ys")})
            else:
                tables = ruled_tables(image) if use_ocr else native_tables(page, scale)
                figures = native_figures(page, scale, tables, use_ocr) if layout == "native" else []
                occupied = tables + figures
                remaining = [item for item in lines if not any(overlap(item["bbox"], r["bbox"]) /
                             max(1, area(item["bbox"])) > 0.45 for r in occupied)]
                texts = fallback_text_regions(remaining, image.size)
                regions = occupied + texts
            regions = assign(lines, regions, image.size)
            by_id = {line["id"]: line for line in lines}
            split_regions = []
            for region in regions:
                source_lines = [by_id[i] for i in region["line_ids"]]
                if region["kind"] == "text" and len(source_lines) >= 4:
                    middle = image.width / 2
                    left = [line for line in source_lines if line["bbox"][2] < middle - 2]
                    right = [line for line in source_lines if line["bbox"][0] > middle + 2]
                    if len(left) >= 2 and len(right) >= 2 and len(left) + len(right) == len(source_lines):
                        # Some layout models merge aligned columns into one paragraph.
                        for suffix, column in (("left", left), ("right", right)):
                            split_regions.append({**region, "id": region["id"] + "-" + suffix,
                                                  "bbox": union([line["bbox"] for line in column]),
                                                  "line_ids": [line["id"] for line in column],
                                                  "method": "detected_text_column_split"})
                        continue
                split_regions.append(region)
            regions = split_regions
            for region in regions:
                source_lines = [by_id[i] for i in region["line_ids"]]
                if region["kind"] == "text" and len(source_lines) <= 3:
                    value = join_lines(source_lines, language)
                    if re.match(r"^(?:Figure\s*\d+|Fig\.\s*\d+|图\s*\d+)", value, re.I):
                        region["kind"] = "figure_caption"
                    elif re.match(r"^(?:Table\s*\d+|表\s*\d+)", value, re.I):
                        region["kind"] = "table_caption"
                template = region.pop("grid_template", None)
                if template:
                    region["grid"] = fill_grid(template, source_lines, language)
                    grid = region["grid"]
                    # Native line geometry can mistake two connected diagram boxes
                    # for a sparse table. Preserve the region as an ambiguous figure.
                    occupied_columns = {c["column"] for c in grid["cells"] if c["text"].strip()}
                    if grid["row_count"] <= 2 and len(occupied_columns) < grid["column_count"]:
                        region["kind"] = "figure"
                        region["method"] = "ambiguous_native_grid"
                        region.pop("grid")
                elif region["kind"] == "table" and region.get("rule_xs"):
                    grid = ruled_grid(image, region, source_lines, language)
                    if grid:
                        region["grid"] = grid
            record = {"schema_version": SCHEMA_VERSION, "page": number, "size": list(image.size),
                      "pdf_sha256": source_hash, "language": language, "used_ocr": use_ocr,
                      "primary_engine": ocr_engine.name if use_ocr else "pdf_text_layer",
                      "layout": layout, "lines": lines, "regions": regions,
                      "original_line_ids": [item["id"] for item in lines], "revisions": [],
                      "elapsed_seconds": round(time.monotonic() - start, 3)}
            validate_page(record)
            write_json(run / "raw" / f"{number:04d}.json", copy.deepcopy(record))
            write_json(path, record)
            print(f"Extracted page {number}/{len(document)} ({record['primary_engine']}, {len(lines)} lines)", flush=True)
    return manifest
