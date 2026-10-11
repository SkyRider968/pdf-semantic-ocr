# Commands and engine selection

Install the repository with `python -m pip install '.[ocr]'` or a release wheel.
Run `pdf-semantic-ocr doctor`. Native digital text extraction needs no OCR extras.
For complex scanned layouts add `[layout]`; for macOS crosscheck add `[vision]`;
for Apple Silicon table recognition add `[mlx]`.

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
