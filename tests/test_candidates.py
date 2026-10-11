from pathlib import Path

from pdf_semantic_ocr.candidates import import_candidate, integrate
from pdf_semantic_ocr.extract import extract
from pdf_semantic_ocr.storage import read_json, write_json
from pdf_semantic_ocr.patches import apply_patch

ROOT = Path(__file__).resolve().parents[1]
OTSL = ("<fcel>Training thresholds<lcel><lcel><nl>"
        "<fcel>Category<fcel>Limit<fcel>Unit<nl>"
        "<fcel>Short effort<fcel><100<fcel>seconds*<nl>"
        "<fcel>Long effort<fcel>150-200<fcel>seconds<nl>")


def make_run(tmp_path):
    run = tmp_path / "run"
    extract(ROOT / "examples/digital.pdf", run, ocr="never", pages="1")
    table = next(r for r in read_json(run / "pages/0001.json")["regions"] if r["kind"] == "table")
    path = tmp_path / "table.otsl"
    path.write_text(OTSL, encoding="utf-8", newline="\n")
    return run, table, path


def test_external_candidate_uses_same_gates_and_repeated_integration_is_safe(tmp_path):
    run, table, path = make_run(tmp_path)
    import_candidate(run, 1, table["id"], path)
    result = integrate(run)
    assert result["tables"][0]["status"] == "automated_evidence"
    result = integrate(run)
    assert result["tables"][0]["status"] == "already_applied"


def test_candidate_is_rejected_after_source_text_changes(tmp_path):
    run, table, path = make_run(tmp_path)
    # Remove the derived structure first so only the source text change invalidates the candidate.
    record = read_json(run / "pages/0001.json")
    current = next(r for r in record["regions"] if r["id"] == table["id"])
    current.pop("grid")
    write_json(run / "pages/0001.json", record)
    import_candidate(run, 1, table["id"], path)
    line = next(item for item in record["lines"] if item["id"] in table["line_ids"])
    repair = {"pdf_sha256": record["pdf_sha256"],
              "evidence": {"method": "original_page_image", "note": "Test source revision"},
              "operations": [{"op": "replace_text", "page": 1, "line_id": line["id"],
                              "expected": line["text"], "text": line["text"] + " revised"}]}
    patch = tmp_path / "repair.json"
    write_json(patch, repair)
    apply_patch(run, patch)
    result = integrate(run)
    assert result["tables"][0]["reason"] == "stale_source"
