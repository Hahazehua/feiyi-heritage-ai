"""Copy an explicit public demo source allowlist; never upload the working tree."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = (
    "app.py",
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    ".streamlit/config.toml",
    "static/pitch-deck.pdf",
    "scripts/index_catalog_vectors.py",
    "data/demo/customization_options.csv",
    "data/demo/heritage_items.csv",
    "data/demo/merchants.csv",
    "data/demo/product_texts.csv",
    "data/demo/products.csv",
    "data/catalog/coverage_matrix.csv",
    "data/catalog/heritage_products.csv",
    "data/catalog/research_log.csv",
    "data/catalog/source_registry.csv",
    "deploy/gcp/Dockerfile",
    "deploy/gcp/cloudbuild.yaml",
    "deploy/gcp/source-lifecycle.json",
    "deploy/gcp/deploy.sh",
    "deploy/gcp/stage_source.py",
    "deploy/gcp/ensure_indexes.py",
)
TREES = {
    "src/heritagelink": {".py"},
    "assets/catalog/products": {".jpg", ".jpeg", ".png", ".webp"},
}


def stage_source(destination: Path, root: Path = ROOT) -> tuple[int, int]:
    """Create a new staging tree, rejecting symlinks and nonempty destinations."""
    root = root.resolve()
    destination = destination.resolve()
    if destination == root or destination in root.parents:
        raise ValueError("Staging destination must not contain the project root")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Staging destination must be empty")
    sources = [root / name for name in FILES]
    for folder, suffixes in TREES.items():
        for path in (root / folder).rglob("*"):
            relative = path.relative_to(root / folder)
            if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                continue
            if path.is_file() and path.suffix.lower() in suffixes:
                sources.append(path)
    sources = sorted(set(sources))
    for source in sources:
        if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError(f"Required regular project file is missing or unsafe: {source}")
        if any(parent.is_symlink() for parent in source.parents if parent != root):
            raise ValueError(f"Symlinked source path is not allowed: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    for source in sources:
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        total += source.stat().st_size
    # This directory already contains only allowed files. Do not inherit gitignore.
    (destination / ".gcloudignore").write_text(".gcloudignore\n", encoding="utf-8")
    return len(sources), total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    count, size = stage_source(args.destination)
    print(f"Prepared {count} public application files ({size / 1_000_000:.1f} MB).")


if __name__ == "__main__":
    main()
