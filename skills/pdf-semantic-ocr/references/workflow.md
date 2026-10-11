# Commands and engine selection

Install the CLI separately from the skill: from an activated virtual environment
in the source checkout, run `python -m pip install '.[ocr]'`; alternatively use
`python -m pip install 'pdf_semantic_ocr-0.1.2-py3-none-any.whl[ocr]'` for a downloaded
release wheel. The wheel contains the public USDA demo; synthetic fixtures require the source archive. This release is not on PyPI.
Run `pdf-semantic-ocr doctor`. For first-run validation, use
`pdf-semantic-ocr demo --output first-ocr` and open `first-ocr/preview.html`.
It OCRs a rasterized official 2020 USDA/HHS page, not a physical paper scan.
It downloads a pinned CPU ONNX layout model without PyTorch and reports complete-body
versus illustration-label measurements separately. Demo PASS is a development
regression result, not a quality guarantee for the user’s document.
 Native digital text extraction needs no OCR extras.
Install selected extras before using their commands: `python -m pip install '.[layout]'`
for complex scanned layouts, `'.[vision]'` for macOS crosscheck, or `'.[mlx]'` for
Apple Silicon table recognition. When using a wheel, put the extra on its filename
instead of `.`. Windows/Linux table engines can connect through `import-candidate`.

```bash
pdf-semantic-ocr extract INPUT.pdf --output RUN --pages 1-3,20 --dpi 250
# Inspect RUN/images/pages, pages/*.json and audit.json.
pdf-semantic-ocr extract INPUT.pdf --output RUN --dpi 250
pdf-semantic-ocr crosscheck RUN --backend vision
pdf-semantic-ocr recognize-tables RUN --pages 20-25
pdf-semantic-ocr integrate RUN
pdf-semantic-ocr repair RUN repair.json
pdf-semantic-ocr evaluate RUN --gold gold.json --minimum 95
pdf-semantic-ocr sample RUN --count 20 --seed 42
```

Choose a new output directory when changing extraction settings. Pages are 1-based;
region and line IDs come from structured page JSON. `fetch-layout --output MODEL.pt`
downloads the optional layout weights; pass `--layout doclayout --layout-weights MODEL.pt`
to extraction. Do not treat the lightweight native fallback as a universal diagram parser.

Use `import-candidate RUN --page N --region ID --file table.otsl` to connect other
table engines to the same gates. `repair` accepts replace_text, restore_line,
reclassify, move_line, set_table and set_groups. The full schema is in [schema.md](schema.md); all repairs require document hash and source-image evidence.

Exit codes: 0 = command completed / engineering or sample checks passed in their
reported scope; 1 = invalid input, configuration or unavailable dependency;
2 = measured sample or engineering failure. Semantic acceptance remains a separate
judgment even when the CLI exits 0.

`--layout doclayout-onnx --layout-weights MODEL.onnx` runs the supported
DocLayout ONNX conversion with `[ocr]`; the demo caches it in
`~/.cache/pdf-semantic-ocr/models`. See CLI `demo --help` for a custom cache.
