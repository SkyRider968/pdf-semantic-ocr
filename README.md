# PDF Semantic OCR

Extract complex PDFs into traceable learning text. Keep body text, figure text and
table structure separate; stage model results before accepting them; repair a
specific page without rerunning the book.

**Status: early release (0.1.0).** This is an extraction and audit workflow, not a
guarantee of 99% accuracy on arbitrary PDFs. Character recognition, reading order,
table relationships and complete figure detection require separate evidence.

中文文档：[使用与验收 SOP](docs/SOP.zh-CN.md)。

## Install

Python 3.10+:

```bash
python -m pip install '.[ocr]'
pdf-semantic-ocr doctor
```

Run the command from this repository after cloning. For a downloaded wheel,
use `pip install 'pdf_semantic_ocr-0.1.0-py3-none-any.whl[ocr]'` instead.
Digital PDFs with a useful text layer only need `pip install .`.
Optional extras: `layout` (DocLayout-YOLO), `vision` (macOS independent OCR),
`mlx` (Apple Silicon table recognition), `dev` (tests/build).

## Quick start

```bash
# Native text layer, table geometry and detected figure crops.
pdf-semantic-ocr extract examples/digital.pdf --output runs/digital --ocr never
pdf-semantic-ocr evaluate runs/digital --gold examples/digital_gold.json --minimum 99

# Raster scans: real OCR. Models are downloaded by the selected backend.
pdf-semantic-ocr extract examples/scanned.pdf --output runs/scanned --language auto

# Recommended trained layout model for complex scanned books.
pdf-semantic-ocr fetch-layout --output models/doclayout.pt
pdf-semantic-ocr extract book.pdf --output runs/book --layout doclayout \
  --layout-weights models/doclayout.pt --dpi 250

# Optional independent audit on macOS; do not use the same OCR engine twice.
pdf-semantic-ocr crosscheck runs/book --backend vision

# Optional table reconstruction on Apple Silicon: candidates first, then gates.
pdf-semantic-ocr recognize-tables runs/book --pages 20-30
pdf-semantic-ocr integrate runs/book

# Review the original image, record a patch, apply and reassemble.
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

The committed PDFs are original synthetic fixtures, generated by
`python examples/make_fixtures.py`. Gold content comes from source declarations,
not OCR predictions. Tests cover actual PDF extraction, merged tables, literal
inequalities, wrong-coordinate candidates, missing pages and repair preconditions.
Real OCR smoke tests are opt-in because they download models; see validation docs.

## License

AGPL-3.0-or-later. Dependencies and model weights retain their own licenses.
See [third-party notices](THIRD_PARTY_NOTICES.md). No source books, extracted book
text, private paths, credentials or model weights are included.
