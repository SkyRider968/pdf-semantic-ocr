"""Portable run storage and source/configuration fingerprints."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

SCHEMA_VERSION = 1


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_text(path: Path, value: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="." + path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def parse_pages(spec: str | None, count: int) -> list[int]:
    if not spec:
        return list(range(1, count + 1))
    result = set()
    for part in spec.split(","):
        values = part.split("-")
        if len(values) == 1:
            first = last = int(values[0])
        elif len(values) == 2:
            first, last = map(int, values)
        else:
            raise ValueError("Pages must be a comma-separated list such as 1-3,7")
        if first < 1 or last < first or last > count:
            raise ValueError(f"Page range {part!r} outside 1..{count}")
        result.update(range(first, last + 1))
    return sorted(result)


def records(run: Path):
    for path in sorted((run / "pages").glob("*.json")):
        yield path, read_json(path)
