from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.package_gcp_release import REQUIRED_FILES, package_release, release_files


def _release_tree(root: Path) -> None:
    for relative in (*REQUIRED_FILES, "src/heritagelink/__init__.py", "data/demo/products.csv"):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("public demo content", encoding="utf-8")


def test_release_excludes_credentials_personal_data_and_databases(tmp_path: Path) -> None:
    _release_tree(tmp_path)
    private_paths = (
        ".env",
        ".env.production",
        ".streamlit/secrets.toml",
        ".local/credentials.json",
        "data/analytics/choices.csv",
        "data/catalog/private.sqlite3",
        "src/heritagelink/__pycache__/secret.pyc",
        "deploy/gcp/credentials.json.txt",
        "deploy/gcp/service-account.json",
    )
    for relative in private_paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("PRIVATE", encoding="utf-8")
    destination = tmp_path / "release.zip"
    count = package_release(tmp_path, destination)
    with ZipFile(destination) as archive:
        assert len(archive.namelist()) == count
        assert "haha-gcp/app.py" in archive.namelist()
        assert not any("PRIVATE" in archive.read(name).decode() for name in archive.namelist())


def test_release_stops_if_deployment_inputs_are_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Missing release inputs"):
        release_files(tmp_path)
