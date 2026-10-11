# Release validation: 0.1.0

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
