import pytest

from pdf_semantic_ocr.tables import parse_otsl, consensus_grid, table_markdown


def test_literal_inequalities_and_footnotes_are_not_tokens():
    grid = parse_otsl("<fcel>Threshold<fcel>Unit<nl><fcel><100<fcel>mg^{*}<nl>")
    assert grid["row_count"] == 2
    assert grid["cells"][2]["text"] == "<100"
    assert grid["cells"][3]["text"] == "mg*"
    assert "<100" in table_markdown(grid)


def test_merged_header_and_empty_cells():
    grid = parse_otsl("<fcel>Header<lcel><nl><fcel>Left<ecel><nl>")
    assert grid["cells"][0]["colspan"] == 2
    assert grid["column_count"] == 2
    assert grid["cells"][-1]["text"] == ""


@pytest.mark.parametrize("value", [
    "<fcel>A<lcel><nl><fcel>B<nl>",
    "<ucel><fcel>B<nl>",
    "<fcel>A<lcel><nl><ucel><fcel>B<nl>",
    "<fcel>A<ecel>unexpected<nl>",
    "<fcel>A<nl>garbage",
    "prefix<fcel>A<nl>",
    "<fcel>A<div>B</div><nl>",
])
def test_malformed_tables_are_rejected(value):
    with pytest.raises(ValueError):
        parse_otsl(value)


def source():
    return [{"id": "a", "text": "Alpha", "bbox": [0, 0, 20, 10]},
            {"id": "b", "text": "Beta", "bbox": [100, 0, 120, 10]},
            {"id": "c", "text": "Gamma", "bbox": [0, 100, 20, 110]},
            {"id": "d", "text": "Delta", "bbox": [100, 100, 120, 110]}]


def test_consensus_rejects_hallucinated_or_omitted_text():
    candidate = parse_otsl("<fcel>Alpha<fcel>Beta<nl><fcel>Gamma<fcel>extra<nl>")
    grid, evidence = consensus_grid(source(), candidate)
    assert grid is None
    assert evidence["reason"] == "text_disagreement"


def test_consensus_rejects_same_characters_in_wrong_rows():
    candidate = parse_otsl("<fcel>Gamma<fcel>Delta<nl><fcel>Alpha<fcel>Beta<nl>")
    grid, evidence = consensus_grid(source(), candidate)
    assert grid is None
    assert evidence["reason"] == "row_coordinate_conflict"


def test_consensus_rejects_same_characters_in_wrong_columns():
    candidate = parse_otsl("<fcel>Beta<fcel>Alpha<nl><fcel>Delta<fcel>Gamma<nl>")
    grid, evidence = consensus_grid(source(), candidate)
    assert grid is None
    assert evidence["reason"] == "column_coordinate_conflict"


def test_consensus_conserves_lines_without_claiming_semantic_pass():
    candidate = parse_otsl("<fcel>Alpha<fcel>Beta<nl><fcel>Gamma<fcel>Delta<nl>")
    grid, evidence = consensus_grid(source(), candidate)
    assert [c["line_ids"] for c in grid["cells"]] == [["a"], ["b"], ["c"], ["d"]]
    assert evidence["status"] == "automated_evidence"
