"""Rebuild the image-only demo and source references; never read OCR predictions."""
import argparse
from pathlib import Path
import shutil

import pymupdf

from pdf_semantic_ocr.storage import file_hash, write_json

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/pdf_semantic_ocr/assets/usda"
URL = "https://www.dietaryguidelines.gov/sites/default/files/2021-03/DGA_2020-2025_StartSimple_withMyPlate_English_color.pdf"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ASSETS / "official-original.pdf")
    parser.add_argument("--output", type=Path, default=ASSETS)
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    original = root / "official-original.pdf"
    if original.resolve() != args.source.resolve():
        shutil.copyfile(args.source, original)
    with pymupdf.open(original) as document:
        if len(document) != 4 or "Make every bite count" not in document[1].get_text():
            raise ValueError("Expected the selected USDA/HHS four-page 2020 publication")
        page = document[1]
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(200 / 72, 200 / 72), alpha=False)
        reference = "\n".join(b[4].strip() for b in sorted(page.get_text("blocks"), key=lambda b: b[1])
                              if b[1] < 750)
        with pymupdf.open() as raster:
            target = raster.new_page(width=page.rect.width, height=page.rect.height)
            target.insert_image(target.rect, stream=pixmap.tobytes("png"))
            raster.set_metadata({"title": "USDA/HHS 2020 MyPlate, original page 2 — generated image-only OCR fixture",
                                 "author": "USDA/HHS (source); PDF Semantic OCR (raster derivative)",
                                 "subject": "Generated at 200 DPI lossless; not a physical paper scan. Official original bundled."})
            raster.save(root / "image-only.pdf", deflate=True, garbage=4, no_new_id=True)
    digest = file_hash(root / "image-only.pdf")
    write_json(root / "body-gold.json", {"pdf_sha256": digest,
        "reference_method": "Official original text blocks sorted vertically; verified against original page 2. Never derived from OCR. Includes every body heading, paragraph and 9 bullets; excludes figure labels and page marker.",
        "samples": [{"id": "complete-body", "page": 1, "split": "development-regression", "reference": reference}]})
    samples = [("plate-labels", [.06, .10, .235, .22], "Dairy Fruits Grains Vegetables Protein MyPlate.gov"),
               ("fruit-badge", [.055, .37, .15, .48], "Fruits"),
               ("vegetable-badge", [.055, .57, .15, .68], "Vegetables"),
               ("grain-badge", [.055, .76, .15, .88], "Grains"),
               ("page-marker", [.07, .95, .105, .98], "2")]
    write_json(root / "auxiliary-gold.json", {"pdf_sha256": digest,
        "reference_method": "Visual transcription of all visible illustration labels and printed page marker. Photos contain no printed text. Each bbox is source-selected.",
        "samples": [{"id": name, "page": 1, "bbox": box, "split": "development-regression", "reference": ref}
                    for name, box, ref in samples]})
    names = ("official-original.pdf", "image-only.pdf", "body-gold.json", "auxiliary-gold.json")
    write_json(root / "provenance.json", {
        "title": "Start Simple With MyPlate Today",
        "publisher": ["U.S. Department of Agriculture", "U.S. Department of Health and Human Services"],
        "publication_date": "2020-12", "retrieved": "2026-10-11", "official_url": URL,
        "original_pages": 4, "demo_original_page": 2,
        "input_kind": "Generated image-only derivative of a born-digital federal publication; not a physical paper scan",
        "rasterization": {"dpi": 200, "encoding": "lossless PNG", "physical_size_points": [612, 792],
                          "native_text_characters": 0},
        "files": {name: {"sha256": file_hash(root / name), "bytes": (root / name).stat().st_size} for name in names},
        "rights_note": "Federal agency publication. U.S. government-authored work is generally excluded from U.S. copyright under 17 USC 105; third-party materials and marks can be exceptions. No third-party copyright notice found in these four pages. Attribution preserved; this tool has no USDA/HHS endorsement. Nonprofit status is not the basis of this selection.",
        "gold_scope": "Complete body of original page 2 plus separately transcribed illustration labels/page marker. Development regression, not independent benchmark. No table on this page."})
    print(f"Rebuilt demo in {root}; raster SHA-256 {digest}")


if __name__ == "__main__":
    main()
