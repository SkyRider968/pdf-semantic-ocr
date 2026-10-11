"""Generate original, redistributable PDF fixtures and independent expected text.

No book content or third-party font files are distributed. MuPDF's built-in font
is used only to render a CJK fixture. Gold is declared from fixture source content,
not copied from OCR predictions.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent
EN_LEFT = ["Strength training improves force production.", "Adaptation depends on repeated practice.",
           "Recovery changes the response to loading."]
EN_RIGHT = ["Testing should use a consistent protocol.", "Record the units beside every measurement.",
            "Compare results within the same population."]
ZH_LEFT = ["训练适应来自刺激与恢复的共同作用。", "负荷、训练量和频率需要分别记录。", "正文应按左栏再右栏的顺序阅读。"]
ZH_RIGHT = ["评估需要保持测试条件的一致性。", "图中文字不能直接并入正文段落。", "数值、小于号和单位必须完整保留。"]
CELLS = [
    {"row": 0, "column": 0, "text": "Training thresholds", "colspan": 3},
    {"row": 1, "column": 0, "text": "Category"}, {"row": 1, "column": 1, "text": "Limit"},
    {"row": 1, "column": 2, "text": "Unit"},
    {"row": 2, "column": 0, "text": "Short effort"}, {"row": 2, "column": 1, "text": "<100"},
    {"row": 2, "column": 2, "text": "seconds*"},
    {"row": 3, "column": 0, "text": "Long effort"}, {"row": 3, "column": 1, "text": "150-200"},
    {"row": 3, "column": 2, "text": "seconds"},
]


def cjk_line(page, position, text, size=12):
    writer = pymupdf.TextWriter(page.rect)
    writer.append(position, text, font=pymupdf.Font("cjk"), fontsize=size)
    writer.write_text(page)


def english_page(document):
    page = document.new_page(width=600, height=780)
    page.insert_text((40, 42), "PDF extraction verification", fontsize=18)
    for i, text in enumerate(EN_LEFT):
        page.insert_text((40, 90 + i * 24), text, fontsize=10)
    for i, text in enumerate(EN_RIGHT):
        page.insert_text((320, 90 + i * 24), text, fontsize=10)
    xs, ys = [40, 220, 350, 540], [220, 256, 292, 328, 364]
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y), width=0.8)
    for x in (xs[0], xs[-1]):
        page.draw_line((x, ys[0]), (x, ys[-1]), width=0.8)
    for x in xs[1:-1]:
        page.draw_line((x, ys[1]), (x, ys[-1]), width=0.8)
    for cell in CELLS:
        page.insert_text((xs[cell["column"]] + 10, ys[cell["row"]] + 23), cell["text"], fontsize=11)
    page.insert_text((40, 390), "* Source footnote: do not remove comparison signs.", fontsize=10)
    page.draw_rect(pymupdf.Rect(70, 460, 230, 540), width=1.2)
    page.draw_rect(pymupdf.Rect(350, 460, 510, 540), width=1.2)
    page.draw_line((230, 500), (350, 500), width=1.2)
    page.insert_text((100, 505), "Stimulus", fontsize=14)
    page.insert_text((380, 505), "Recovery", fontsize=14)
    page.insert_text((40, 590), "Figure 1. Two labels and a connecting line.", fontsize=11)
    page.insert_text((40, 650), "1. Which value preserves the source threshold?", fontsize=11)
    page.insert_text((40, 678), "a. <100   b. 100   c. 150   d. 200", fontsize=11)
    return page


def chinese_page(document):
    page = document.new_page(width=600, height=780)
    cjk_line(page, (40, 42), "复杂文档提取测试", 18)
    for i, text in enumerate(ZH_LEFT):
        cjk_line(page, (40, 100 + i * 28), text, 11)
    for i, text in enumerate(ZH_RIGHT):
        cjk_line(page, (320, 100 + i * 28), text, 11)
    xs, ys = [40, 240, 420, 550], [240, 280, 320, 360]
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]), width=1)
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y), width=1)
    values = [["项目", "阈值", "单位"], ["测试甲", "<40", "毫克"], ["测试乙", "150", "毫克"]]
    for r, row in enumerate(values):
        for c, value in enumerate(row):
            cjk_line(page, (xs[c] + 14, ys[r] + 27), value, 12)
    cjk_line(page, (40, 410), "脚注：这些数值仅用于测试，不提供训练建议。", 11)
    return page


def gold(pdf, english_number=1, chinese_number=2):
    return {"pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "provenance": "Original fixture source declarations; not OCR output",
            "samples": [
                {"id": "english_columns", "page": english_number, "bbox": [0.05, 0.08, 0.95, 0.2],
                 "reference": "\n".join(EN_LEFT + EN_RIGHT), "split": "fixture"},
                {"id": "chinese_columns", "page": chinese_number, "bbox": [0.05, 0.09, 0.98, 0.23],
                 "reference": "\n".join(ZH_LEFT + ZH_RIGHT), "split": "fixture"}],
            "tables": [{"id": "merged_header", "page": english_number, "bbox": [40/600, 220/780, 540/600, 364/780],
                        "cells": CELLS, "split": "fixture"},
                       {"id": "chinese_thresholds", "page": chinese_number,
                        "bbox": [40/600, 240/780, 550/600, 360/780], "split": "fixture",
                        "cells": [{"row": r, "column": c, "text": value} for r, row in enumerate(
                            [["项目", "阈值", "单位"], ["测试甲", "<40", "毫克"], ["测试乙", "150", "毫克"]])
                            for c, value in enumerate(row)]}]}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    digital = pymupdf.open()
    english_page(digital)
    chinese_page(digital)
    digital.save(ROOT / "digital.pdf", deflate=True)
    scanned = pymupdf.open()
    for page in digital:
        target = scanned.new_page(width=page.rect.width, height=page.rect.height)
        target.insert_image(target.rect, stream=page.get_pixmap(matrix=pymupdf.Matrix(2.8, 2.8)).tobytes("png"))
    scanned.save(ROOT / "scanned.pdf", deflate=True)
    mixed = pymupdf.open()
    mixed.insert_pdf(digital)
    mixed.insert_pdf(scanned)
    mixed.new_page(width=600, height=780)
    mixed.save(ROOT / "mixed.pdf", deflate=True)
    for name in ("digital", "scanned"):
        (ROOT / f"{name}_gold.json").write_text(json.dumps(gold(ROOT / f"{name}.pdf"), ensure_ascii=False, indent=2) + "\n")
    first, second = gold(ROOT / "mixed.pdf"), gold(ROOT / "mixed.pdf", 3, 4)
    first["samples"] += second["samples"]
    first["tables"] += second["tables"]
    (ROOT / "mixed_gold.json").write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n")
    digital.close()
    scanned.close()
    mixed.close()
    print("Generated digital.pdf, scanned.pdf, mixed.pdf and source-declared gold files")


if __name__ == "__main__":
    main()
