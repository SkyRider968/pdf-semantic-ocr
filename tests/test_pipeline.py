import copy
import subprocess
import sys
from pathlib import Path

import pytest

from pdf_semantic_ocr.audit import audit
from pdf_semantic_ocr.evaluate import evaluate, edit_counts, metrics
from pdf_semantic_ocr.export import export
from pdf_semantic_ocr.extract import extract
from pdf_semantic_ocr.patches import apply_patch
from pdf_semantic_ocr.schema import validate_page
from pdf_semantic_ocr.storage import read_json, write_json, write_text, parse_pages, file_hash

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def run(tmp_path):
    directory = tmp_path / "result"
    extract(ROOT / "examples/digital.pdf", directory, ocr="never")
    export(directory)
    return directory


def test_actual_pdf_text_and_merged_tables_match_source_gold(run):
    report = evaluate(run, ROOT / "examples/digital_gold.json", 99)
    assert report["sample_status"] == "PASS"
    assert report["text"]["accuracy_percent"] == 100
    assert report["table_cells"]["exact_percent"] == 100
    assert report["table_cells"]["reference"] == 19


def test_figure_labels_are_preserved_separately_from_body(run):
    body = (run / "body.md").read_text(encoding="utf-8")
    auxiliary = (run / "figures_tables.md").read_text(encoding="utf-8")
    assert "Stimulus" not in body
    assert "Recovery" in auxiliary and "Stimulus" in auxiliary
    assert "Figure 1." in auxiliary and "Figure 1." not in body
    assert "Strength training improves force production." in body
    assert "<100" in auxiliary
    assets = read_json(run / "assets.json")
    assert any(a["kind"] == "figure" for a in assets["regions"])
    assert all((run / a["path"]).exists() for a in assets["regions"])


def test_full_coverage_does_not_claim_semantic_acceptance(run):
    report = audit(run)
    assert report["engineering_status"] == "PASS"
    assert report["full_document_coverage"]
    assert report["semantic_acceptance"] == "NOT_CERTIFIED"
    assert report["issue_counts"]["relationship_not_reviewed"] > 0


def test_selective_pages_report_incomplete_document(tmp_path):
    extract(ROOT / "examples/digital.pdf", tmp_path, pages="2", ocr="never")
    report = audit(tmp_path)
    assert report["engineering_status"] == "PASS"
    assert not report["full_document_coverage"]
    assert report["missing_pages"] == [1]


def test_cache_reuse_and_input_config_mismatch_are_checked(run):
    path = run / "pages/0001.json"
    before = path.stat().st_mtime_ns
    extract(ROOT / "examples/digital.pdf", run, ocr="never")
    assert path.stat().st_mtime_ns == before
    with pytest.raises(ValueError, match="another input/configuration"):
        extract(ROOT / "examples/digital.pdf", run, dpi=250, ocr="never")
    with pytest.raises(ValueError, match="another input/configuration"):
        extract(ROOT / "examples/scanned.pdf", run, ocr="never")


def test_dropped_and_duplicated_lines_fail_accounting(run):
    page = read_json(run / "pages/0001.json")
    bad = copy.deepcopy(page)
    bad["regions"][0]["line_ids"].pop()
    with pytest.raises(ValueError):
        validate_page(bad)
    bad = copy.deepcopy(page)
    bad["lines"].append(bad["lines"][0])
    with pytest.raises(ValueError):
        validate_page(bad)


def patch(run, operations):
    return {"pdf_sha256": read_json(run / "manifest.json")["pdf_sha256"],
            "evidence": {"method": "original_page_image", "note": "Test source image reviewed"},
            "operations": operations}


def test_repairs_preserve_raw_and_are_replayable(run, tmp_path):
    page = read_json(run / "pages/0001.json")
    line = next(item for item in page["lines"] if "Strength training" in item["text"])
    raw_hash = file_hash(run / "raw/0001.json")
    path = tmp_path / "patch.json"
    write_json(path, patch(run, [{"op": "replace_text", "page": 1, "line_id": line["id"],
                                  "expected": line["text"], "text": line["text"] + " Verified."}]))
    apply_patch(run, path)
    apply_patch(run, path)
    result = read_json(run / "pages/0001.json")
    assert len(result["revisions"]) == 1
    assert file_hash(run / "raw/0001.json") == raw_hash
    assert "Verified." in next(item["text"] for item in result["lines"] if item["id"] == line["id"])


def test_invalid_patch_has_no_partial_effect(run, tmp_path):
    page = read_json(run / "pages/0001.json")
    line = page["lines"][0]
    before = file_hash(run / "pages/0001.json")
    path = tmp_path / "patch.json"
    write_json(path, patch(run, [
        {"op": "replace_text", "page": 1, "line_id": line["id"], "expected": line["text"], "text": "Replacement"},
        {"op": "replace_text", "page": 1, "line_id": line["id"], "expected": "Wrong revision", "text": "Other"},
    ]))
    with pytest.raises(ValueError, match="precondition"):
        apply_patch(run, path)
    assert file_hash(run / "pages/0001.json") == before


def test_patch_requires_matching_document_and_evidence(run, tmp_path):
    path = tmp_path / "patch.json"
    write_json(path, {"pdf_sha256": "wrong", "operations": []})
    with pytest.raises(ValueError, match="hash"):
        apply_patch(run, path)


def test_missing_reference_page_is_measured_as_omission(run, tmp_path):
    gold = {"samples": [{"page": 9, "reference": "Missing real source content"}]}
    path = tmp_path / "gold.json"
    write_json(path, gold)
    report = evaluate(run, path)
    assert report["sample_status"] == "FAIL"
    assert report["text"]["completeness_percent"] == 0


def test_evaluation_distinguishes_substitution_from_completeness():
    report = metrics(edit_counts("abcd", "abxd"))
    assert report["accuracy_percent"] == 75
    assert report["completeness_percent"] == 100
    assert report["correct_recall_percent"] == 75


def test_text_storage_uses_utf8_and_identical_lf_bytes_on_every_platform(tmp_path):
    path = tmp_path / "mixed.md"
    write_text(path, "中文与 English\nSecond line\n")
    assert path.read_bytes() == "中文与 English\nSecond line\n".encode("utf-8")
    write_json(tmp_path / "mixed.json", {"text": "中文"})
    assert b"\r\n" not in (tmp_path / "mixed.json").read_bytes()
    assert read_json(tmp_path / "mixed.json") == {"text": "中文"}


def test_invalid_grid_patch_is_rejected_without_losing_lines(run, tmp_path):
    page = read_json(run / "pages/0001.json")
    table = next(r for r in page["regions"] if r["kind"] == "table")
    path = tmp_path / "patch.json"
    grid = copy.deepcopy(table["grid"])
    grid["cells"].pop()
    write_json(path, patch(run, [{"op": "set_table", "page": 1, "region_id": table["id"], "grid": grid}]))
    with pytest.raises(ValueError):
        apply_patch(run, path)


def test_empty_figure_groups_cannot_be_marked_reviewed(run, tmp_path):
    page = read_json(run / "pages/0001.json")
    figure = next(r for r in page["regions"] if r["kind"] == "figure")
    path = tmp_path / "patch.json"
    write_json(path, patch(run, [{"op": "set_groups", "page": 1, "region_id": figure["id"], "groups": []}]))
    with pytest.raises(ValueError, match="nonempty"):
        apply_patch(run, path)


def test_cli_runs_outside_repository(tmp_path):
    result = subprocess.run([sys.executable, "-m", "pdf_semantic_ocr", "extract",
                             str(ROOT / "examples/digital.pdf"), "--output", str(tmp_path / "from-cli"),
                             "--ocr", "never"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "from-cli/learning.md").exists()
    assert "NOT_CERTIFIED" in result.stdout


@pytest.mark.parametrize("spec", ["0", "3", "2-1", "1-3", "1-2-3"])
def test_page_selection_rejects_invalid_ranges(spec):
    with pytest.raises(ValueError):
        parse_pages(spec, 2)
