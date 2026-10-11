"""Cache independent observations and rematch them after text repairs."""
from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

from .backends import ocr_backend
from .geometry import area, overlap, ordered_lines
from .storage import fingerprint, read_json, records, write_json
from .tables import normalize


def crosscheck(run: Path, backend="vision", language="auto", minimum_confidence=0.5, minimum_length=6):
    pages = list(records(run))
    engine_name = "apple-vision" if backend == "vision" else "rapidocr"
    if any(page["primary_engine"] == engine_name for _, page in pages):
        raise ValueError("Crosscheck must use a different engine from primary OCR")
    engine = ocr_backend(backend, language)
    manifest = read_json(run / "manifest.json")
    cache_key = fingerprint({"input": manifest["cache_key"], "engine": engine_name, "language": language})
    candidates, observation_count = [], 0
    for _, page in pages:
        cache = run / "independent" / engine_name / f"{page['page']:04d}.json"
        if cache.exists() and read_json(cache)["cache_key"] == cache_key:
            observations = read_json(cache)["observations"]
        else:
            with Image.open(run / "images" / "pages" / f"{page['page']:04d}.png") as image:
                observations = engine.recognize(image.convert("RGB"))
            write_json(cache, {"cache_key": cache_key, "observations": observations})
        for observation in observations:
            observation_count += 1
            matching = [item for item in page["lines"] if overlap(item["bbox"], observation["bbox"]) /
                        max(1, min(area(item["bbox"]), area(observation["bbox"]))) > 0.35]
            text = "".join(item["text"] for item in ordered_lines(matching))
            similarity = SequenceMatcher(None, normalize(text), normalize(observation["text"])).ratio()
            if len(normalize(observation["text"])) >= minimum_length and observation["confidence"] >= minimum_confidence:
                if not matching or similarity < 0.85:
                    candidates.append({"page": page["page"], **observation,
                                       "matched_ids": [item["id"] for item in matching], "primary_text": text,
                                       "similarity": similarity, "kind": "unmatched" if not matching else "disagreement"})
    report = {"engine": engine_name, "observations": observation_count, "candidates": candidates,
              "minimum_confidence": minimum_confidence, "minimum_length": minimum_length,
              "scope": "Independent disagreement candidates; agreement does not rule out shared omissions or prove semantics."}
    write_json(run / "crosscheck.json", report)
    return report
