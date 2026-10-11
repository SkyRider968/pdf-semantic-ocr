"""Install the bundled skill without overwriting an existing skill implicitly."""
import argparse
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=Path.home() / ".codex/skills")
    parser.add_argument("--replace", action="store_true", help="Explicitly replace an existing installation")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / "skills/pdf-semantic-ocr"
    destination = args.target / source.name
    if destination.exists() and not args.replace:
        parser.error("Skill already exists; inspect it before using --replace")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    print(f"Installed skill: {destination}")


if __name__ == "__main__":
    main()
