# Structured pages, candidates and repairs

Coordinates are pixels in `images/pages/NNNN.png`, with top-left origin.
PDF page numbers are 1-based. `bbox` is `[left, top, right, bottom]`.

Each page contains `lines`, `regions`, `original_line_ids` and `revisions`.
A line has `id`, `text`, `original_text`, `bbox`, `confidence` and `engine`.
Native text has null confidence: it is not assigned a fabricated 100% confidence.
A region has `id`, `kind`, `bbox` and `line_ids`.
`page_marker` preserves an isolated numeric bottom-margin marker in auxiliary text;
it is a layout classification, not a removed observation.
`isolated_color_badge` supplements detected figures for dense isolated color icons
containing OCR; it is conservative and does not establish universal figure coverage.

Table grids contain `row_count`, `column_count`, `cells`, `unassigned_line_ids` and
`method`. Each cell has zero-based `row`, `column`, positive `rowspan`/`colspan`,
`text` and `line_ids`. Every logical slot belongs to exactly one cell. Duplicate
text need not have unique source matches; those source IDs remain unassigned and
are exported after the table rather than discarded.

`grid` only means a structure exists. `candidate_evidence` is automated supporting
evidence. `review` records declared source-image verification; it is a provenance
record, not an independent proof that the reviewer made no mistake.

## Repair example

Read the current line/region IDs from the page JSON and the document hash from
manifest.json. Replace the example values below with those actually observed.

```json
{
  "pdf_sha256": "THE_DOCUMENT_HASH",
  "evidence": {
    "method": "original_page_image",
    "note": "Page 3, enlarged threshold row: printed value is <100."
  },
  "operations": [
    {
      "op": "replace_text",
      "page": 3,
      "line_id": "p0003-l00012",
      "expected": "100",
      "text": "<100"
    }
  ]
}
```

Supported operations:

| Operation | Required additional fields |
| --- | --- |
| `replace_text` | `line_id`, `expected`, `text` |
| `restore_line` | New `line_id`, `region_id`, `bbox`, `text` |
| `reclassify` | `region_id`, `expected_kind`, `kind` |
| `move_line` | `line_id`, `from_region`, `to_region` |
| `set_table` | `region_id`, complete validated `grid` |
| `set_groups` | `region_id`, `groups` of `{line_ids, text}` covering all figure lines |

All operations are staged and validated before writes. Each page write is atomic;
a multi-page patch is not a filesystem transaction. After an interrupted write,
reapplying the same patch skips pages already carrying its fingerprint and finishes
the remainder. Never mutate the same run concurrently.

Text replacements invalidate derived grid/groups for that region. Add a verified
`set_table`/`set_groups` operation after the replacement when appropriate.
`restore_line` requires explicit source-image evidence and creates a new observation;
it cannot silently delete an original OCR observation.

## Gold format

See `examples/digital_gold.json`. A text sample specifies `page`, `reference` and
optionally `bbox` (normalized to 0..1 by default), `region_id`, `id` and `split`.
Without a selector it evaluates body regions. Table references specify `page`,
`bbox` or `region_id`, and source-declared `cells` with position/text/spans.
Set `complete_table: false` only for deliberately partial cell samples.

Empty text references are rejected. Missing predicted pages count as omissions.
Evaluation fingerprints record the exact page revisions and reference used.
