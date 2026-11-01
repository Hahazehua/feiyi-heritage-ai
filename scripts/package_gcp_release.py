"""Build an allowlisted Cloud Shell upload; never package local secrets or databases."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "app.py",
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    ".streamlit/config.toml",
    "static/pitch-deck.pdf",
    "scripts/index_catalog_vectors.py",
    "scripts/package_gcp_release.py",
    "docs/GCP_FREE_TIER.md",
    "deploy/gcp/deploy.sh",
    "deploy/gcp/Dockerfile",
    "deploy/gcp/cloudbuild.yaml",
    "deploy/gcp/ensure_indexes.py",
    "deploy/gcp/stage_source.py",
    "deploy/gcp/source-lifecycle.json",
)
PATTERNS = (
    "src/heritagelink/**/*.py",
    "data/catalog/*.csv",
    "data/demo/*.csv",
    "assets/catalog/products/*.jpg",
    "assets/catalog/products/*.jpeg",
    "assets/catalog/products/*.png",
    "assets/catalog/products/*.webp",
    "skills/**/*.md",
    "skills/**/*.yaml",
)


def release_files(root: Path) -> tuple[Path, ...]:
    """Select only app source and public demo assets, rejecting linked outside files."""
    root = root.resolve()
    required = {root / relative for relative in REQUIRED_FILES}
    missing = sorted(str(path.relative_to(root)) for path in required if not path.is_file())
    if missing:
        raise ValueError("Missing release inputs: " + ", ".join(missing))
    selected = required | {path for pattern in PATTERNS for path in root.glob(pattern)}
    files = []
    for path in sorted(selected):
        if not path.is_file():
            continue
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(root)
            or any(parent.is_symlink() for parent in path.parents if parent != root)
        ):
            raise ValueError(f"Refusing linked release input: {path}")
        files.append(path)
    return tuple(files)


def package_release(root: Path, destination: Path) -> int:
    """Write a source zip that can be extracted as haha-gcp in Cloud Shell."""
    files = release_files(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            relative = path.relative_to(root.resolve())
            archive.write(path, arcname=(Path("haha-gcp") / relative).as_posix())
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".local/gcp-release/haha-gcp-source.zip"
    )
    args = parser.parse_args()
    destination = args.output.resolve()
    count = package_release(ROOT, destination)
    with destination.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    print(f"Packaged {count} files: {destination}")
    print(f"Size: {destination.stat().st_size / 1024 / 1024:.1f} MiB")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()
