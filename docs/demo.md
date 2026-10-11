# Public nutrition onboarding demo

**Start Simple With MyPlate Today** — U.S. Department of Agriculture and
U.S. Department of Health and Human Services, December 2020.
[Official PDF](https://www.dietaryguidelines.gov/sites/default/files/2021-03/DGA_2020-2025_StartSimple_withMyPlate_English_color.pdf).

The original has four pages. The onboarding fixture is original page 2 rendered
at 200 DPI into a lossless, image-only PDF with zero native text. It is **not a
physical paper scan**. The input is 2.1 MB; the complete official original is
3.6 MB. Both are packaged so the installed wheel runs from any directory.

This page has understandable everyday nutrition content, large headings,
paragraphs, nine bullet tips, three illustrated badges, a MyPlate diagram and
four photographs. It exposes reading-order and body/figure classification errors
which the earlier synthetic fixture did not. It has no table and does not test
Chinese, skew, paper damage, handwriting or difficult low-resolution scans.
Keep the synthetic table and Chinese fixtures as separate tests.

## Run and inspect

```bash
pdf-semantic-ocr demo --output first-ocr
```

Open `first-ocr/preview.html`. The output also includes the official original,
input, reference files and provenance under `source/`, all ordinary extraction
files, and `demo.json`, `body-evaluation.json`, `auxiliary-evaluation.json`.
The preview shows every individual comparison; it does not hide a bad small
sample inside an aggregate. Exit 0 requires engineering checks plus aggregate
body accuracy/completeness ≥99% and auxiliary accuracy/completeness ≥95%.
Exit 2 means a measured gate failed; the evidence remains available. Configuration
or download errors exit 1. No gold text is injected into extraction or repaired
automatically from the reference.

References are source-derived: complete body transcription from official text
blocks, visually checked in source reading order; illustration labels/page marker
transcribed from visible artwork. There are 1,611 normalized body characters and
68 auxiliary characters. NFKC/whitespace normalization retains punctuation.
The measured development output misses the article “a” in the opening sentence
and differs in bullet glyphs/apostrophe/dash typography; the preview displays
these remaining errors. This page was used for development, so its score is a regression, not an
independent benchmark. The text refers to the publication date's nutrition advice;
the OCR demo does not present it as current clinical guidance.

First use downloads a pinned, SHA-256-verified 75 MB DocLayout ONNX conversion,
plus upstream RapidOCR models. `[ocr]` suffices; no PyTorch or MLX installation
is required. `--cache-dir PATH` controls the layout cache. An offline setup can
provide the exact published model with `--layout-weights PATH`. See
[model provenance](models.md), including conflicting upstream license metadata.

To rebuild the bundled derivative and references from the bundled official source:

```bash
python examples/make_usda_demo.py
```

To validate real inference (opt-in because downloads are possible):

```bash
PDF_OCR_SMOKE=1 PDF_DEMO_SMOKE=1 pytest -q
```

`PDF_DEMO_WEIGHTS` can point to the pinned ONNX file for this test. Portable tests
also check that input has no text layer, resource hashes match, model downloads
are atomic/verified, layout letterboxing is correct and empty photos cannot
interleave text columns. See [actual validation](validation.md) for measured timing.

## Source rights and attribution

This is an attributed federal agency publication. Under
[17 U.S.C. §105](https://www.govinfo.gov/content/pkg/USCODE-2023-title17/pdf/USCODE-2023-title17-chap1-sec105.pdf),
U.S. government-authored works are generally outside U.S. copyright protection.
No third-party copyright notice was found in these four pages. Federal documents
can still contain third-party material; this is not an independent clearance of
every photograph. Agency marks are not an endorsement of this project.
Nonprofit status is not the basis for reusability. Keep the source attribution
and provenance when sharing the example; software/model terms remain separate.
