from pdf_semantic_ocr.export import region_text


def test_repeated_ambiguous_source_labels_do_not_duplicate_table_text():
    lines = [{"id": "a", "text": "Same", "bbox": [0, 0, 40, 10]},
             {"id": "b", "text": "Same", "bbox": [100, 0, 140, 10]}]
    grid = {"row_count": 1, "column_count": 2, "method": "otsl",
            "cells": [{"row": 0, "column": 0, "text": "Same", "line_ids": []},
                      {"row": 0, "column": 1, "text": "Same", "line_ids": []}],
            "unassigned_line_ids": ["a", "b"]}
    text = region_text({"lines": lines}, {"kind": "table", "line_ids": ["a", "b"], "grid": grid})
    assert text.count("Same") == 2


def test_genuinely_missing_table_line_is_retained_after_table():
    lines = [{"id": "a", "text": "Body", "bbox": [0, 0, 40, 10]},
             {"id": "b", "text": "Footnote", "bbox": [0, 20, 100, 30]}]
    grid = {"row_count": 1, "column_count": 1, "method": "source",
            "cells": [{"row": 0, "column": 0, "text": "Body", "line_ids": ["a"]}],
            "unassigned_line_ids": ["b"]}
    text = region_text({"lines": lines}, {"kind": "table", "line_ids": ["a", "b"], "grid": grid})
    assert "Footnote" in text and text.count("Body") == 1
