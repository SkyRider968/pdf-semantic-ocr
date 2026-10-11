# Release validation: 0.1.1

Validated on Apple Silicon macOS, Python 3.12, 2026-10-11. Remote CI results are available separately under
[GitHub Actions](https://github.com/SkyRider968/pdf-semantic-ocr/actions); local
measurements below do not substitute for the remote workflow result.

## Real federal-publication demo

USDA/HHS **Start Simple With MyPlate Today**, December 2020, original page 2.
The official original is born digital; the tested input is an explicitly labeled
200-DPI lossless image-only derivative with zero native text. It is not a physical
scan. The official original and the derivative are included in the wheel.

| Measured scope | Reference characters | Accuracy | Completeness | Gate |
| --- | ---: | ---: | ---: | --- |
| Entire body: all headings, paragraphs and nine tips | 1,611 | 99.255% | 99.379% | ≥99%: PASS |
| All visible illustration labels and page marker | 68 | 100% | 100% | ≥95%: PASS |

Reference text comes from the official source, visually checked; it is not copied
from predictions. NFKC/whitespace normalization retains punctuation. The demo was
used during development, so this is a regression score, not an independent
benchmark. The residual body errors include a missing article “a”, nine omitted
bullet glyphs and apostrophe/dash typography substitutions. Body words remain
in source order, and illustration labels/page number are exported separately.
No source-derived patches or reference substitution were applied.

The first broad-detector trial misread illustration strokes as extra text and
failed its auxiliary gate. Tightening English detection from 0.5 to 0.7 removed
noise but lost body words and failed the body gate. The final 0.6 setting passed
both declared gates. Trained layout through ONNX, exclusion of empty photos from
text ordering, column-gutter precedence and a conservative isolated-color-badge
supplement address the observed classification/ordering failures. These fixes
do not prove performance on another document.

## Installed-wheel onboarding and runtime

A new virtual environment without system packages installed the wheel with only
`[ocr]`, then ran from outside the repository with an empty layout cache and
freshly installed RapidOCR. The 75 MB pinned ONNX layout file and selected
RapidOCR detector/English recognition weights were downloaded on first use.
The installed versions were PyMuPDF 1.28.2, RapidOCR 3.10.0, ONNX Runtime 1.31.0,
OpenCV headless 5.0.0.93 and NumPy 2.5.4. No PyTorch, DocLayout Python library,
MLX or Apple Vision was installed. Both quality gates passed at the values above.

| Phase | Measured wall time |
| --- | ---: |
| New venv + wheel/dependency installation | 7.603 s |
| First CLI invocation, including model downloads and interpreter/import startup | 92.566 s |
| Total installation + first demo | 100.169 s |
| Within the demo: layout preparation/download | 4.252 s |
| Within the demo: OCR/model setup, export, audit and evaluation | 71.265 s |
| Development run with cached models, inside demo timer | 7.745 s |

Pip used cached dependency distributions; this does not measure downloading all
Python dependencies over a cold network. Models were fetched for the new engine
installation and empty layout cache. Demo timing starts after module imports;
the outer CLI wall time above includes startup. The five-minute target was met
locally; it is not a universal installation/runtime guarantee.

## Tests, packaging and evidence

The current complete local suite passed **46 tests**, including both real-inference
smoke tests. Portable tests pass 44 with those two explicitly skipped. Tests cover
raster resource/no-text-layer verification, source hashes, uneven columns, empty
photo interference, badge/heading distinction, ONNX letterboxing and invalid
outputs, checksum/atomic model cache, network failure cleanup, HTML escaping and
CLI quality-failure exit status, in addition to the existing extraction/table/repair
suite. Ruff and skill validation pass. Wheel/sdist contain all five demo resources
and no user-provided documents, local runs, credentials or model weights. Rebuilding the
five resources from the official original reproduces every bundled SHA-256.

Run actual-inference checks with:

```bash
PDF_OCR_SMOKE=1 PDF_DEMO_SMOKE=1 pytest -q
ruff check src tests examples scripts
python -m build
python scripts/build_release.py
```

The preview was opened and visually checked in the browser. It shows source,
actual body, auxiliary output and all reference/prediction differences, including
remaining errors. Engineering PASS remains separate from NOT_CERTIFIED semantic
acceptance. This single English brochure contains no table; Chinese, merged-table
and mixed-layout checks remain separate.

The following is the retained 0.1.0 validation record. Its MLX/PyTorch results
are historical measurements, not reruns of those optional engines for 0.1.1.

---

# Historical validation: 0.1.0

Validated locally on Apple Silicon macOS, Python 3.12, on 2026-10-11.
Portable tests also run in a fresh virtual environment with no access to the
development environment's installed OCR/layout packages. CI is configured for Python 3.10
and 3.12 on Linux, Windows and macOS; remote CI results are a separate status.

## Actual inference and source-declared gold

| Document / mode | Text reference characters | Character accuracy / completeness | Exact table cells |
| --- | ---: | --- | --- |
| Digital fixture / native | 317 | 100% / 100% | 19/19 |
| Raster fixture / RapidOCR + MLX table candidates | 317 | 100% / 100% | 19/19 |
| Five-page mixed fixture / DocLayout + native geometry + RapidOCR + MLX | 634 | 100% / 100% | 38/38 |
| New synthetic forward-test scan / RapidOCR + visible-rule table geometry | 144 | 100% / 100% | 12/12 |

The first three share content and must not be summed as independent samples.
The fourth was created and first evaluated after the initial development fixes;
it is a synthetic forward test, not a representative real-world corpus benchmark.
Source reference text/cells are declared in the fixture generators. OCR predictions
were not copied into gold. Confidence is not used to calculate these scores.

The raster merged-header table initially had no valid grid: table results were
9/19 cells, while text samples were correct. The table model then generated a
candidate accepted by conservation/coordinate gates, yielding 19/19. A diagram
misdetected as a table was rejected for insufficient anchors. This proves the
candidate workflow can expose and address this example, not that all tables work.

The initial mixed-layout trial exposed a detected text block spanning two columns;
the first score was 81.861% text accuracy and 18/38 table cells. Region splitting,
native-geometry integration and table reconstruction brought the final fixture
to the values above. These are development/regression results.

Apple Vision was actually run independently against the raster fixture: no
meaningful disagreements under the configured confidence/length filter. This
does not exclude shared omissions. Original full-page renders were also viewed.

## Engineering tests and installation

The local full suite passed 37 tests including the opt-in real OCR test. The
portable suite passed 36 tests with that model test explicitly skipped.
During the onboarding review, a second fresh Python 3.12 virtual environment
installed the source package with only `[ocr]`. The documented `doctor`, digital
extraction/evaluation and first-scan extraction/evaluation sequence completed:
317 reference characters / 19 exact cells and 144 reference characters / 12 exact
cells respectively, both 100%. This verifies the basic installation route on
local macOS; it is a repeat of existing fixtures, not a new independent benchmark.
The automated suite covers real native PDF extraction, merged headers, figure
labels, detected crops, column ordering, comparison symbols, invalid spans,
wrong-row/column model candidates, stale candidates, source-line accounting,
cache configuration changes, missing reference pages, replayable repairs and
preservation of raw data. A real Chinese/English scan test is opt-in:

```bash
python -m pip install -e '.[dev,ocr]'
PDF_OCR_SMOKE=1 pytest -q
ruff check src tests examples scripts
python -m build
python scripts/build_release.py
```

For the optional layout/table path:

```bash
python -m pip install '.[ocr,layout]'
pdf-semantic-ocr fetch-layout --output models/doclayout.pt
pdf-semantic-ocr extract examples/mixed.pdf --output runs/mixed \
  --layout doclayout --layout-weights models/doclayout.pt --dpi 250
# On Apple Silicon, in an environment with [mlx]:
pdf-semantic-ocr recognize-tables runs/mixed --pages 3-4
pdf-semantic-ocr integrate runs/mixed
pdf-semantic-ocr evaluate runs/mixed --gold examples/mixed_gold.json --minimum 99
```

## Known limits

Native/rule-based layout remains heuristic. In the raster fixture it classified
the connected diagram boxes as an unstructured table; the labels were preserved,
the audit flagged it, and the trained layout engine identified the figure.
Complex diagram semantics still require source review. Blank pages are flagged
as empty-page candidates rather than silently treated as complete content.

All audits continue to say `semantic_acceptance: NOT_CERTIFIED`, including when
engineering checks and the measured samples pass. There is no measured universal
99% guarantee. User-provided documents and their OCR outputs are excluded
from this repository and release archives.
