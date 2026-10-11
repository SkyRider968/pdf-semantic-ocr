"""Explicit opt-in: downloads OCR models and performs real raster recognition."""
import os
from pathlib import Path

import pytest

from pdf_semantic_ocr.evaluate import evaluate
from pdf_semantic_ocr.extract import extract
from pdf_semantic_ocr.storage import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.environ.get("PDF_OCR_SMOKE") != "1", reason="Set PDF_OCR_SMOKE=1 for real model inference")
def test_real_scanned_chinese_and_english_body(tmp_path):
    run = tmp_path / "scan"
    extract(ROOT / "examples/scanned.pdf", run, language="auto")
    gold = read_json(ROOT / "examples/scanned_gold.json")
    # This smoke test measures body recognition; complex raster table structure is separate.
    gold.pop("tables")
    path = tmp_path / "body_gold.json"
    write_json(path, gold)
    report = evaluate(run, path, 95)
    assert report["sample_status"] == "PASS"
    assert all(read_json(run / "pages" / f"{n:04d}.json")["used_ocr"] for n in [1, 2])
