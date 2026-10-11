"""Unified CLI. Successful extraction is not a claim of semantic correctness."""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

from . import __version__
from .storage import records, write_json


def summarize(report):
    print(json.dumps(report, ensure_ascii=False, indent=2))


def refresh(run):
    from .export import export
    from .audit import audit
    export(run)
    return audit(run)


def extraction_arguments(parser):
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pages", help="1-based pages, e.g. 1-3,7; absent means all")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--ocr", choices=["auto", "always", "never"], default="auto")
    parser.add_argument("--ocr-backend", choices=["rapidocr", "vision"], default="rapidocr")
    parser.add_argument("--layout", choices=["native", "doclayout", "none"], default="native")
    parser.add_argument("--layout-weights", type=Path)
    parser.add_argument("--language", choices=["auto", "en", "zh"], default="auto")
    parser.add_argument("--threads", type=int, default=4)


def parser():
    p = argparse.ArgumentParser(description="Traceable PDF OCR, table reconstruction and evidence-driven repairs")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Show optional engine availability without exposing credentials")
    for name in ("extract", "run"):
        q = sub.add_parser(name, help="Extract PDF" if name == "extract" else "Extract and optionally crosscheck/reconstruct tables")
        extraction_arguments(q)
        if name == "run":
            q.add_argument("--crosscheck", choices=["vision", "rapidocr"])
            q.add_argument("--tables", choices=["mlx"])
    for name in ("audit", "export", "integrate"):
        q = sub.add_parser(name)
        q.add_argument("run", type=Path)
    q = sub.add_parser("repair")
    q.add_argument("run", type=Path)
    q.add_argument("patch", type=Path)
    q = sub.add_parser("evaluate")
    q.add_argument("run", type=Path)
    q.add_argument("--gold", type=Path, required=True)
    q.add_argument("--minimum", type=float, default=95)
    q = sub.add_parser("crosscheck")
    q.add_argument("run", type=Path)
    q.add_argument("--backend", choices=["vision", "rapidocr"], default="vision")
    q.add_argument("--language", choices=["auto", "en", "zh"], default="auto")
    q = sub.add_parser("recognize-tables")
    q.add_argument("run", type=Path)
    q.add_argument("--pages")
    q.add_argument("--model", default="mlx-community/PaddleOCR-VL-1.6-4bit")
    q = sub.add_parser("import-candidate")
    q.add_argument("run", type=Path)
    q.add_argument("--page", type=int, required=True)
    q.add_argument("--region", required=True)
    q.add_argument("--file", type=Path, required=True)
    q = sub.add_parser("sample")
    q.add_argument("run", type=Path)
    q.add_argument("--count", type=int, default=12)
    q.add_argument("--seed", type=int, default=20261011)
    q = sub.add_parser("fetch-layout")
    q.add_argument("--output", type=Path, required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            from .extract import dependency_versions
            summarize({"version": __version__, "python": sys.version.split()[0], "platform": sys.platform,
                       "dependencies": dependency_versions(), "optional": {
                           name: importlib.util.find_spec(name) is not None for name in
                           ("rapidocr", "doclayout_yolo", "mlx_vlm", "Vision")}})
        elif args.command in {"extract", "run"}:
            from .extract import extract
            extract(args.pdf, args.output, pages=args.pages, dpi=args.dpi, ocr=args.ocr,
                    backend=args.ocr_backend, layout=args.layout, weights=args.layout_weights,
                    language=args.language, threads=args.threads)
            if args.command == "run":
                if args.tables:
                    from .candidates import recognize_tables, integrate
                    recognize_tables(args.output, args.pages)
                    integrate(args.output)
                if args.crosscheck:
                    from .crosscheck import crosscheck
                    crosscheck(args.output, args.crosscheck, args.language)
            report = refresh(args.output)
            summarize({k: report[k] for k in ("processed_pages", "engineering_status", "semantic_acceptance", "issue_counts")})
            return 0 if report["engineering_status"] == "PASS" else 2
        elif args.command == "audit":
            from .audit import audit
            report = audit(args.run)
            summarize({k: report[k] for k in ("engineering_status", "full_document_coverage", "issue_counts", "semantic_acceptance")})
            return 0 if report["engineering_status"] == "PASS" else 2
        elif args.command == "export":
            refresh(args.run)
        elif args.command == "repair":
            from .patches import apply_patch
            summarize(apply_patch(args.run, args.patch))
            refresh(args.run)
        elif args.command == "evaluate":
            from .evaluate import evaluate
            report = evaluate(args.run, args.gold, args.minimum)
            summarize({k: report[k] for k in ("sample_status", "text", "table_cells", "scope")})
            return 0 if report["sample_status"] == "PASS" else 2
        elif args.command == "crosscheck":
            from .crosscheck import crosscheck
            report = crosscheck(args.run, args.backend, args.language)
            summarize({"observations": report["observations"], "candidates": len(report["candidates"])})
        elif args.command == "recognize-tables":
            from .candidates import recognize_tables
            summarize(recognize_tables(args.run, args.pages, args.model))
        elif args.command == "import-candidate":
            from .candidates import import_candidate
            candidate = import_candidate(args.run, args.page, args.region, args.file)
            summarize({k: candidate[k] for k in ("page", "region_id", "status")})
        elif args.command == "integrate":
            from .candidates import integrate
            summarize(integrate(args.run))
            refresh(args.run)
        elif args.command == "sample":
            if args.count < 1:
                raise ValueError("Sample count must be positive")
            population = [{"page": page["page"], "region_id": r["id"], "kind": r["kind"], "bbox": r["bbox"]}
                          for _, page in records(args.run) for r in page["regions"] if r["kind"] != "noise"]
            selected = random.Random(args.seed).sample(population, min(args.count, len(population)))
            report = {"seed": args.seed, "population": len(population), "selected": selected,
                      "method": "Uniform region sampling; separately cover chapters, small text, formulas and complex tables"}
            write_json(args.run / "sample_plan.json", report)
            summarize(report)
        elif args.command == "fetch-layout":
            import shutil
            try:
                from huggingface_hub import hf_hub_download
            except ImportError as error:
                raise ValueError("Install layout extras before fetching weights") from error
            downloaded = hf_hub_download("juliozhao/DocLayout-YOLO-DocStructBench",
                                         "doclayout_yolo_docstructbench_imgsz1024.pt")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(downloaded, args.output)
            summarize({"weights": str(args.output), "notice": "See upstream model licensing in docs/models.md"})
    except (ValueError, KeyError, OSError, StopIteration, ImportError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
