import os
from pathlib import Path

import numpy as np
import pymupdf
import pytest
from PIL import Image, ImageDraw

from pdf_semantic_ocr.backends import ONNXLayoutBackend
from pdf_semantic_ocr.demo import copy_assets, fetch_layout, run_demo, text_diff
from pdf_semantic_ocr.export import page_texts
from pdf_semantic_ocr.geometry import reading_order
from pdf_semantic_ocr.layout import colored_graphic_regions
from pdf_semantic_ocr.storage import file_hash, read_json


def test_bundled_real_publication_forces_ocr_and_has_bound_reference(tmp_path):
    source, provenance = copy_assets(tmp_path)
    with pymupdf.open(source / "image-only.pdf") as doc:
        assert len(doc) == 1
        assert not doc[0].get_text().strip()
        assert len(doc[0].get_image_info()) == 1
    with pymupdf.open(source / "official-original.pdf") as doc:
        assert len(doc) == 4
        assert "Make every bite count" in doc[1].get_text()
    assert provenance["demo_original_page"] == 2
    assert read_json(source / "body-gold.json")["pdf_sha256"] == file_hash(source / "image-only.pdf")


def test_empty_photograph_cannot_interleave_uneven_text_columns():
    boxes = [[5, 20, 90, 40], [5, 75, 90, 100], [110, 20, 190, 60], [110, 80, 190, 120]]
    lines = [{"id": str(i), "bbox": b, "text": text} for i, (b, text) in
             enumerate(zip(boxes, ["Left start", "Left end", "Right start", "Right end"]))]
    regions = [{"id": str(i), "kind": "text", "bbox": line["bbox"], "line_ids": [line["id"]]}
               for i, line in enumerate(lines)]
    page = {"page": 1, "size": [200, 200], "language": "en", "lines": lines,
            "regions": regions + [{"id": "photo", "kind": "figure", "bbox": [0, 50, 200, 70], "line_ids": []}]}
    body, _, _ = page_texts(page)
    assert body.index("Left end") < body.index("Right start")
    assert [n["id"] for n in reading_order(regions)] == ["0", "1", "2", "3"]


def test_color_badge_supplement_preserves_graphical_labels_but_not_colored_headings():
    image = Image.new("RGB", (800, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 300, 120, 450], fill="orange")
    draw.rectangle([200, 300, 600, 325], fill="red")
    lines = [{"id": "badge", "text": "Grains", "bbox": [55, 330, 105, 345]},
             {"id": "title", "text": "Heading", "bbox": [200, 300, 600, 325]}]
    figures = colored_graphic_regions(image, lines, [])
    assert len(figures) == 1
    assert figures[0]["bbox"][0] == 40
    assert not colored_graphic_regions(image, lines, [{"bbox": [30, 290, 130, 460]}])


class FakeSession:
    def __init__(self, result):
        self.result = result

    def run(self, _, feeds):
        tensor = feeds["images"]
        assert tensor.shape == (1, 3, 1024, 1024)
        assert tensor.dtype == np.float32
        return [self.result]


def fake_layout(result):
    detector = ONNXLayoutBackend.__new__(ONNXLayoutBackend)
    detector.engine = FakeSession(result)
    detector.input_name, detector.size, detector.names = "images", 1024, {0: "title", 1: "figure"}
    return detector


def test_onnx_letterbox_coordinates_duplicates_and_invalid_outputs():
    # 512x1024 image has 256 pixels of letterbox padding on each horizontal side.
    rows = [[[266, 20, 356, 100, .9, 0], [266, 20, 356, 100, .7, 0],
             [0, 0, 1024, 1024, .1, 1], [np.nan, 20, 356, 100, .8, 0]]]
    detector = fake_layout(np.array(rows))
    result = detector.detect(Image.new("RGB", (512, 1024)))
    assert len(result) == 1 and result[0]["bbox"] == [10, 20, 100, 100]
    assert result[0]["kind"] == "title"
    with pytest.raises(ValueError, match="Unsupported"):
        fake_layout(np.zeros((1, 84, 300))).detect(Image.new("RGB", (512, 1024)))


def test_model_cache_download_is_atomic_verified_and_reused(tmp_path):
    source = tmp_path / "published-model"
    source.write_bytes(b"Known published bytes")
    expected = file_hash(source)
    cache = tmp_path / "cache"
    target, downloaded = fetch_layout(cache, url=source.as_uri(), expected=expected)
    assert downloaded and target.read_bytes() == source.read_bytes()
    reused, downloaded = fetch_layout(cache, url="https://unreachable.invalid", expected=expected)
    assert reused == target and not downloaded
    target.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        fetch_layout(cache, url=source.as_uri(), expected="f" * 64)
    assert not list(cache.glob(".layout-*"))


def test_model_network_failure_keeps_no_partial_file(tmp_path, monkeypatch):
    def failure(*args, **kwargs):
        raise OSError("network unavailable")
    monkeypatch.setattr("urllib.request.urlopen", failure)
    with pytest.raises(OSError, match="verified layout"):
        fetch_layout(tmp_path)
    assert not list(tmp_path.iterdir())


def test_preview_escapes_document_markup():
    reference, prediction = text_diff("<script>source</script>", "<script>OCR</script>")
    assert "<script>" not in reference + prediction
    assert "&lt;script&gt;" in reference and "&lt;script&gt;" in prediction


def test_demo_cli_does_not_report_success_after_failed_quality_gate(tmp_path, monkeypatch):
    from pdf_semantic_ocr.cli import main
    monkeypatch.setattr("pdf_semantic_ocr.demo.run_demo", lambda *args: {"demo_status": "FAIL"})
    assert main(["demo", "--output", str(tmp_path)]) == 2


@pytest.mark.skipif(os.environ.get("PDF_DEMO_SMOKE") != "1", reason="Set PDF_DEMO_SMOKE=1 for public-demo model inference")
def test_real_public_brochure_end_to_end(tmp_path):
    supplied = os.environ.get("PDF_DEMO_WEIGHTS")
    report = run_demo(tmp_path / "run", weights=Path(supplied) if supplied else None)
    assert report["demo_status"] == "PASS"
    assert report["body"]["reference_characters"] == 1611
    assert report["body"]["accuracy_percent"] >= 99
    assert report["semantic_acceptance"] == "NOT_CERTIFIED"
    run = tmp_path / "run"
    page = read_json(run / "pages/0001.json")
    assert page["used_ocr"] and page["primary_engine"] == "rapidocr"
    assert "MyPlate.gov" not in (run / "body.md").read_text(encoding="utf-8")
    assert "MyPlate.gov" in (run / "figures_tables.md").read_text(encoding="utf-8")
    assert (run / "preview.html").exists()
