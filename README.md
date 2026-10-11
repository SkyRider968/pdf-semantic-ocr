# PDF Semantic OCR

Extract complex PDFs into traceable learning text. Keep body text, figure text and
table structure separate; stage model results before accepting them; repair a
specific page without rerunning the book.

**Status: early release (0.1.1).** This is an extraction and audit workflow, not a
guarantee of 99% accuracy on arbitrary PDFs. Character recognition, reading order,
table relationships and complete figure detection require separate evidence.

中文文档：[使用与验收 SOP](docs/SOP.zh-CN.md)。

[GitHub repository](https://github.com/SkyRider968/pdf-semantic-ocr) ·
[0.1.1 release](https://github.com/SkyRider968/pdf-semantic-ocr/releases/tag/v0.1.1)

## Install

Python 3.10+. Open a terminal in the downloaded/cloned source directory, then
create a virtual environment (macOS/Linux):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[ocr]'
pdf-semantic-ocr doctor
```

On Windows, use `py -m venv .venv` and `.venv\Scripts\Activate.ps1` in PowerShell.
For a downloaded wheel, replace the install command with
`python -m pip install 'pdf_semantic_ocr-0.1.1-py3-none-any.whl[ocr]'`.
You can also install the released wheel directly in your activated environment:

```bash
python -m pip install 'pdf-semantic-ocr[ocr] @ https://github.com/SkyRider968/pdf-semantic-ocr/releases/download/v0.1.1/pdf_semantic_ocr-0.1.1-py3-none-any.whl'
pdf-semantic-ocr demo --output first-ocr
```

The public USDA demo is bundled in the wheel. Synthetic examples require the source archive/checkout.
This release is not currently published on PyPI.
Digital PDFs with a useful text layer only need `pip install .`.
Optional extras: `layout` (DocLayout-YOLO), `vision` (macOS independent OCR),
`mlx` (Apple Silicon table recognition), `dev` (tests/build).

## Try a real publication in about five minutes

After installing `[ocr]`, run from **any directory**:

```bash
pdf-semantic-ocr demo --output my-first-ocr
```

Open `my-first-ocr/preview.html` to compare the page image, actual body OCR,
illustration labels, source references and highlighted differences. The command
performs actual OCR, exports the text/crops, audits source-line accounting and
runs separate body (99%) and auxiliary-label (95%) acceptance checks. A failed
measured check exits 2 while keeping the comparison available. It never substitutes
reference text for OCR output.

The source is USDA/HHS's **Start Simple With MyPlate Today**, December 2020.
The official four-page PDF is included; the demo uses original page 2 as a **one-page,
2.1 MB, lossless image-only derivative** with zero native text. It is not a paper
scan. This readable modern brochure exercises large headings, paragraphs, bullets,
photographs, icon labels and body/figure separation; it has no table.
[Source, rights and benchmark scope](docs/demo.md).

First use downloads a 75 MB pinned ONNX layout model and RapidOCR weights.
The layout adapter runs on CPU using the basic `[ocr]` environment, without
PyTorch. Downloads are cached; the layout checksum is verified. Five minutes is a
local measured target, not a guarantee across connections or computers. Timings
and exact results are in [validation](docs/validation.md).

## Additional synthetic examples

```bash
# Native text layer, table geometry and detected figure crops.
pdf-semantic-ocr extract examples/digital.pdf --output runs/digital --ocr never
pdf-semantic-ocr evaluate runs/digital --gold examples/digital_gold.json --minimum 99

# Raster scans: real OCR, plus a simple ruled table. First use downloads models.
pdf-semantic-ocr extract examples/holdout_scanned.pdf --output runs/first-scan --language auto
pdf-semantic-ocr evaluate runs/first-scan --gold examples/holdout_scanned_gold.json --minimum 99
```

Successful evaluation exits 0 and writes `evaluation.json`. The supplied digital
and first-scan references scored 100% character accuracy/completeness in our local
validation. Open `learning.md` and `images/pages/` together to see the result and
its source. A passing example does not certify your own document. See
[the validation report](docs/validation.md) for sample sizes and known failures.

## Complex documents and optional backends

```bash
# Recommended trained layout model for complex scanned books.
python -m pip install '.[layout]'
pdf-semantic-ocr fetch-layout --output models/doclayout.pt
pdf-semantic-ocr extract book.pdf --output runs/book --pages 1-3,20 \
  --layout doclayout --layout-weights models/doclayout.pt --dpi 250
```

Replace `book.pdf` and choose representative pages that exist in your PDF. Review
that trial, then repeat the same command without `--pages` to process all pages.
DocLayout installs PyTorch and downloads a layout model; installation is larger
than the basic OCR path. These commands use the same activated environment.

```bash
# Optional independent audit on macOS; do not use the same OCR engine twice.
python -m pip install '.[vision]'
pdf-semantic-ocr crosscheck runs/book --backend vision

# Optional table reconstruction on Apple Silicon: candidates first, then gates.
python -m pip install '.[mlx]'
pdf-semantic-ocr recognize-tables runs/book --pages 20-30
pdf-semantic-ocr integrate runs/book
```

Choose table page numbers present in your run. The default MLX model card lists
about 0.68 GB of weights, excluding runtime dependencies. Windows/Linux can
import another engine's OTSL using `import-candidate`; no portable table model is
bundled. The merged-header scan `examples/scanned.pdf` requires this more advanced
table path to reproduce the reported exact-cell result.

```bash
# Review the original image, record a patch, apply and reassemble.
# repair.json must be created from source evidence using docs/schema.md.
pdf-semantic-ocr repair runs/book repair.json
pdf-semantic-ocr sample runs/book --count 20 --seed 42
pdf-semantic-ocr audit runs/book
```

`run` combines extraction, optional `--tables mlx`, optional `--crosscheck vision`,
export and audit. It performs one bounded pass. An agent or person reviews the
remaining candidates and decides whether another targeted pass is justified.

## Output

| File/directory | Purpose |
| --- | --- |
| `manifest.json` | Document hash, settings, dependency versions and requested pages |
| `raw/` | Original page recognition and layout observations; repairs do not overwrite these |
| `pages/` | Current structured page records, source line IDs and repair history |
| `body.md` | Body text, titles, formulas and preserved unassigned text |
| `figures_tables.md` | Figure labels/captions, tables and footnotes |
| `learning.md` | Combined text in region reading order with PDF page numbers |
| `images/pages/` | Complete page renders for audit |
| `images/regions/`, `assets.json` | Detected figure/table crops, including associated text bounds |
| `audit.json`, `audit.md` | Engineering coverage and anomaly candidates |
| `candidates/`, `candidate_audit.json` | Model table outputs and integration decisions |
| `independent/`, `crosscheck.json` | Independent observations and current disagreement candidates |
| `repairs/` | Replayable source-image repair manifests |
| `evaluation.json` | Sample character and cell/position measurements |

No review placeholders are injected into the learning text. Uncertain recognized
text stays available and appears in diagnostics. A confirmed `noise` region is
excluded from learning text but retained in structured/raw records.

Markdown repeats a merged cell's value over its logical span for readability;
the JSON grid preserves the actual `rowspan`/`colspan`. Use JSON for programmatic
relationship analysis. Region crops preserve detected content; they do not prove
that every image or vector diagram in the original PDF was detected.

## What is reusable here?

- Joint layout/OCR source mapping and column-aware reading order.
- OTSL merged-cell parsing, including literal `<100` and footnote preservation.
- Conservative table gates: source character multiset and unique-coordinate anchors.
- Independent OCR matching, explicit uncertainty and sample-scoped quality reports.
- Configuration-checked resume, raw evidence retention and validated local repairs.
- A [SOP](docs/SOP.zh-CN.md) and an installable [agent skill](skills/pdf-semantic-ocr/SKILL.md).

The recognition models come from upstream projects. This repository contributes
the integration and evidence workflow. It does not claim superiority over other
document parsers without an independent benchmark.

## Limits and reproducibility

The native/raster fallback is deliberately lightweight and cannot fully classify
complex diagrams or borderless tables. Prefer DocLayout on those documents.
Even DocLayout can misclassify headings and figures. Independent engines can
share omissions; matching character multisets do not prove table semantics.
Repairs require original-image evidence and cannot substitute subject-matter
knowledge for printed text.

Output directories are bound to the PDF hash and extraction configuration. Use a
new directory when changing either. Resume never silently mixes OCR settings.
Do not run concurrent mutations against the same output directory. Optional
model downloads require network access; extraction itself does not upload PDFs.

See [schema and patch format](docs/schema.md), [models and licenses](docs/models.md),
and [release validation](docs/validation.md).

Install the bundled skill with `python scripts/install_skill.py`. It is copied to
`~/.codex/skills/pdf-semantic-ocr` by default; the CLI must also be installed in the
agent's environment. The script refuses to overwrite an existing skill unless
`--replace` is explicitly supplied.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
ruff check src tests examples
python -m build
```

The synthetic PDFs are generated by
`python examples/make_fixtures.py`. Gold content comes from source declarations,
not OCR predictions. Tests cover actual PDF extraction, merged tables, literal
inequalities, wrong-coordinate candidates, missing pages and repair preconditions.
Real OCR smoke tests are opt-in because they download models; see validation docs.
The bundled USDA example is a real federal publication with an explicit raster
derivative and source-transcribed references, reproduced by `examples/make_usda_demo.py`.

## License

AGPL-3.0-or-later. Dependencies and model weights retain their own licenses.
See [third-party notices](THIRD_PARTY_NOTICES.md). No user-provided documents, extracted input
text, private paths, credentials or model weights are included. The attributed
USDA/HHS publication and its image-only demo derivative are included.
The software license grants no rights to input documents or their extracted
content. AGPL obligations matter when distributing integrations or providing a
network service; see the dated [license and publication review](docs/legal-review.zh-CN.md).
