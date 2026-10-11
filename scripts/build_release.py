"""Package the standalone skill and checksum release artifacts; no local runs."""
import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from pdf_semantic_ocr import __version__
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    source = ROOT / "skills/pdf-semantic-ocr"
    archive = output / f"pdf-semantic-ocr-skill-{__version__}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(source.parent).as_posix())
        z.write(ROOT / "LICENSE", "LICENSE")
    shutil.copyfile(ROOT / "docs/SOP.zh-CN.md", output / "SOP.zh-CN.md")
    shutil.copyfile(ROOT / "docs/validation.md", output / "validation.md")
    # Older releases may coexist locally; never checksum them as this release.
    names = {f"pdf_semantic_ocr-{__version__}-py3-none-any.whl",
             f"pdf_semantic_ocr-{__version__}.tar.gz", archive.name, "SOP.zh-CN.md", "validation.md"}
    files = sorted(p for p in output.iterdir() if p.is_file() and p.name in names)
    (output / "SHA256SUMS").write_text("".join(
        hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in files))
    print("Release artifacts: " + ", ".join(p.name for p in files))


if __name__ == "__main__":
    main()
