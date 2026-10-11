"""A second original document, first evaluated after the initial fixture fixes.

This is a synthetic forward test, not an independent real-world corpus benchmark.
"""
import hashlib
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent
PARAGRAPHS = ["A useful record separates observations from conclusions.",
              "Every correction needs a location and an explicit reason.",
              "工具核验关注文字是否遗漏，以及关系是否正确。",
              "抽检成绩只代表样本，不能证明每一页都完全正确。"]
VALUES = [["Observation", "Threshold", "Unit"], ["Baseline", "<18.5", "kg"],
          ["Follow-up", "40-60", "cm"], ["Recovery", ">150", "seconds"]]


def main():
    doc = pymupdf.open()
    page = doc.new_page(width=620, height=800)
    page.insert_text((55, 55), "Observations and evidence", fontsize=20)
    for i, text in enumerate(PARAGRAPHS):
        if i < 2:
            page.insert_text((55, 125 + i * 32), text, fontsize=13)
        else:
            writer = pymupdf.TextWriter(page.rect)
            writer.append((55, 125 + i * 32), text, font=pymupdf.Font("cjk"), fontsize=13)
            writer.write_text(page)
    xs, ys = [55, 245, 410, 565], [340, 385, 430, 475, 520]
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]), width=0.8)
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y), width=0.8)
    for r, values in enumerate(VALUES):
        for c, value in enumerate(values):
            page.insert_text((xs[c] + 12, ys[r] + 29), value, fontsize=13)
    page.insert_text((55, 570), "These values are synthetic extraction fixtures.", fontsize=11)
    pdf = ROOT / "holdout.pdf"
    doc.save(pdf, deflate=True)
    scanned = pymupdf.open()
    target = scanned.new_page(width=620, height=800)
    target.insert_image(target.rect, stream=page.get_pixmap(matrix=pymupdf.Matrix(3, 3)).tobytes("png"))
    scanned.save(ROOT / "holdout_scanned.pdf", deflate=True)
    for name in ("holdout", "holdout_scanned"):
        source = ROOT / f"{name}.pdf"
        gold = {"pdf_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "provenance": "Original forward-test source declarations",
                "samples": [{"id": "mixed_language_paragraphs", "page": 1, "bbox": [0.04, 0.12, 0.98, 0.3],
                             "reference": "\n".join(PARAGRAPHS), "split": "synthetic_forward"}],
                "tables": [{"id": "threshold_table", "page": 1, "bbox": [55/620, 340/800, 565/620, 520/800],
                            "split": "synthetic_forward",
                            "cells": [{"row": r, "column": c, "text": v} for r, row in enumerate(VALUES)
                                      for c, v in enumerate(row)]}]}
        (ROOT / f"{name}_gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n")
    doc.close()
    scanned.close()


if __name__ == "__main__":
    main()
