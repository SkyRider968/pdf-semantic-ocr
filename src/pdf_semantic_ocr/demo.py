"""A wheel-contained public-publication demo with actual OCR and honest evidence."""
from __future__ import annotations

import difflib
import html
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from importlib.resources import files
from pathlib import Path

from .storage import file_hash, read_json, write_json, write_text

LAYOUT_REVISION = "ee7c3d744e5c47c58e267044ac825f95abe69653"
LAYOUT_SHA256 = "fece9af02f618b603ff7921ccec6861d13e7e1f9830e091dfb7e8ad9311e5b21"
LAYOUT_URL = ("https://huggingface.co/wybxc/DocLayout-YOLO-DocStructBench-onnx/resolve/"
              + LAYOUT_REVISION + "/doclayout_yolo_docstructbench_imgsz1024.onnx")


def fetch_layout(cache: Path, *, url=LAYOUT_URL, expected=LAYOUT_SHA256):
    """Pinned, checksum-verified, atomic cache. No partially written model survives."""
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"doclayout-{expected[:12]}.onnx"
    if target.exists() and file_hash(target) == expected:
        return target, False
    deadline = time.monotonic() + 180
    last_error = None
    for _ in range(2):
        descriptor, temporary = tempfile.mkstemp(prefix=".layout-", dir=cache)
        try:
            with os.fdopen(descriptor, "wb") as output:
                request = urllib.request.Request(url, headers={"User-Agent": "pdf-semantic-ocr-demo"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    while True:
                        if time.monotonic() > deadline:
                            raise TimeoutError("Layout download exceeded 180 seconds; retry with a faster connection")
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
            if file_hash(Path(temporary)) != expected:
                raise ValueError("Layout model checksum mismatch; downloaded file was rejected")
            os.replace(temporary, target)
            return target, True
        except (OSError, urllib.error.URLError) as error:
            last_error = error
            if time.monotonic() > deadline:
                break
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    raise OSError(f"Could not download verified layout model: {last_error}")


def copy_assets(output):
    destination = output / "source"
    destination.mkdir(parents=True, exist_ok=True)
    resource = files("pdf_semantic_ocr").joinpath("assets", "usda")
    for name in ("official-original.pdf", "image-only.pdf", "body-gold.json", "auxiliary-gold.json", "provenance.json"):
        (destination / name).write_bytes(resource.joinpath(name).read_bytes())
    provenance = read_json(destination / "provenance.json")
    for name, evidence in provenance["files"].items():
        if file_hash(destination / name) != evidence["sha256"]:
            raise ValueError(f"Bundled demo resource hash mismatch: {name}")
    return destination, provenance


def text_diff(reference, prediction):
    left, right = [], []
    for op, a, b, c, d in difflib.SequenceMatcher(None, reference, prediction, autojunk=False).get_opcodes():
        ref, actual = html.escape(reference[a:b]), html.escape(prediction[c:d])
        left.append(ref if op == "equal" else f"<del>{ref}</del>")
        right.append(actual if op == "equal" else f"<ins>{actual}</ins>")
    return "".join(left), "".join(right)


def preview(output, report, body, auxiliary):
    evidence = []
    for evaluation in (body, auxiliary):
        for sample in evaluation["samples"]:
            reference, prediction = text_diff(sample["reference"], sample["prediction"])
            accuracy = sample["metrics"]["accuracy_percent"]
            evidence.append(f'<h3>{html.escape(sample["id"])} · {accuracy}% character accuracy</h3>'
                            f'<div class="pair"><section><h4>Source reference</h4><pre>{reference}</pre></section>'
                            f'<section><h4>Actual OCR</h4><pre>{prediction}</pre></section></div>')
    metrics = body["text"]
    value = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>USDA OCR demo · evidence</title>
<style>body{{margin:0;background:#f4f6f8;color:#17212b;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1400px;margin:auto;padding:28px}}h1{{font-size:30px}}a{{color:#0757a2}}
.cards,.pair{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}section{{background:white;padding:20px;border-radius:12px;min-width:0}}
img{{width:100%;height:auto}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.7 system-ui,sans-serif}}
.metrics{{padding:14px;background:#e4f1ea;border-radius:8px}}del{{background:#ffd8d8;text-decoration:none}}ins{{background:#cdf1d6;text-decoration:none}}
.note{{background:#fff2d9;padding:14px;border-radius:8px}}@media(max-width:850px){{.cards,.pair{{grid-template-columns:1fr}}}}</style>
<main><h1>Make every bite count · real publication, actual OCR</h1>
<p>USDA/HHS · December 2020 · original page 2. The input is an image-only raster derivative of the official
born-digital PDF, <strong>not a physical paper scan</strong>. No text layer is available to OCR.</p>
<p><a href="source/official-original.pdf">Official original (4 pages)</a> · <a href="source/image-only.pdf">Demo input (1 page)</a> ·
<a href="source/provenance.json">Provenance</a> · <a href="demo.json">Run report</a> · <a href="audit.json">Audit</a></p>
<div class="metrics">Complete-body character accuracy: <b>{metrics['accuracy_percent']}%</b> ·
completeness: <b>{metrics['completeness_percent']}%</b> · reference: {metrics['reference_characters']} normalized characters ·
run: {report['elapsed_seconds']} s · sample checks: {report['demo_status']}</div>
<p class="note">Development regression on one English brochure page. This does not certify arbitrary PDFs,
Chinese text, physical scanning damage, tables or figure relationships. Bullets and typography may differ.
All auxiliary OCR remains visible, including possible recognition of icon strokes as text.
Engineering PASS is distinct from semantic acceptance, which remains NOT_CERTIFIED.</p>
<div class="cards"><section><h2>Original page image</h2><img src="images/pages/0001.png" alt="Original USDA MyPlate page 2"></section>
<section><h2>Body only · actual OCR</h2><pre>{html.escape((output / 'body.md').read_text(encoding='utf-8'))}</pre>
<h2>Figure labels and page marker · actual OCR</h2><pre>{html.escape((output / 'figures_tables.md').read_text(encoding='utf-8'))}</pre></section></div>
<h2>Reference / prediction differences</h2><p>Red = reference differences; green = OCR differences. Reference text never enters extraction.</p>
{''.join(evidence)}</main></html>'''
    write_text(output / "preview.html", value)


def run_demo(output: Path, cache: Path | None = None, weights: Path | None = None):
    from .audit import audit
    from .evaluate import evaluate
    from .export import export
    from .extract import extract
    start = time.monotonic()
    source, provenance = copy_assets(output)
    print("USDA/HHS 2020 brochure, original page 2; generated image-only input. Preparing layout model…", flush=True)
    model_start = time.monotonic()
    if weights:
        if file_hash(weights) != LAYOUT_SHA256:
            raise ValueError("Demo requires the pinned ONNX layout model; provided file has a different checksum")
        downloaded = False
    else:
        weights, downloaded = fetch_layout(cache or Path.home() / ".cache/pdf-semantic-ocr/models")
    model_seconds = time.monotonic() - model_start
    print("Layout ready. Running local OCR; first use may download recognition models…", flush=True)
    inference_start = time.monotonic()
    extract(source / "image-only.pdf", output, ocr="always", language="en",
            layout="doclayout-onnx", weights=weights)
    export(output)
    engineering = audit(output)
    body = evaluate(output, source / "body-gold.json", 99)
    shutil.copyfile(output / "evaluation.json", output / "body-evaluation.json")
    auxiliary = evaluate(output, source / "auxiliary-gold.json", 95)
    shutil.copyfile(output / "evaluation.json", output / "auxiliary-evaluation.json")
    # Keep the standard evaluation entry point focused on the declared body gate.
    shutil.copyfile(output / "body-evaluation.json", output / "evaluation.json")
    passed = (engineering["engineering_status"] == "PASS" and body["sample_status"] == "PASS"
              and auxiliary["sample_status"] == "PASS")
    report = {"demo_status": "PASS" if passed else "FAIL", "publication": provenance["title"],
              "input_kind": provenance["input_kind"], "source_original_page": 2,
              "layout_revision": LAYOUT_REVISION, "layout_sha256": file_hash(weights),
              "layout_downloaded": downloaded, "layout_prepare_seconds": round(model_seconds, 3),
              "ocr_export_audit_evaluate_seconds": round(time.monotonic() - inference_start, 3),
              "elapsed_seconds": round(time.monotonic() - start, 3), "body": body["text"],
              "auxiliary": auxiliary["text"], "body_minimum_percent": 99, "auxiliary_minimum_percent": 95,
              "engineering_status": engineering["engineering_status"], "semantic_acceptance": "NOT_CERTIFIED",
              "scope": "One development page. Complete body gate and aggregate illustration-label/page-marker gate, reported separately; inspect each sample, not only aggregate scores.",
              "five_minute_target": "Measured runtime only; installation, hardware and download speed vary.",
              "preview": str((output / "preview.html").resolve())}
    write_json(output / "demo.json", report)
    preview(output, report, body, auxiliary)
    return report
