"""Guards on the deployment image.

Layer order is invisible until a deploy takes forty minutes instead of thirty
seconds, and the mistake reintroduces itself easily, so it is asserted here.
"""

from __future__ import annotations

from pathlib import Path

DOCKERFILE = Path(__file__).parents[1] / "deploy" / "Dockerfile"


def _lines() -> list[str]:
    return [line.strip() for line in DOCKERFILE.read_text(encoding="utf-8").splitlines()]


def _index_of(prefix: str) -> int:
    for index, line in enumerate(_lines()):
        if line.startswith(prefix):
            return index
    raise AssertionError(f"Dockerfile has no line starting with {prefix!r}")


def test_application_code_is_copied_after_dependencies_are_installed() -> None:
    """Otherwise every code push reinstalls every dependency from scratch."""
    install = _index_of("&& pip install -r requirements.txt")
    copy_src = _index_of("COPY src/")
    copy_app = _index_of("COPY app.py")

    assert install < copy_src, "COPY src/ above pip install busts the dependency cache"
    assert install < copy_app


def test_dependency_layer_depends_only_on_project_metadata() -> None:
    """The stub package is what lets `-e .` install without the real source."""
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY pyproject.toml requirements.txt README.md ./" in text
    assert "mkdir -p src/heritagelink" in text
    assert "touch src/heritagelink/__init__.py" in text


def test_imports_resolve_from_the_copied_source_tree() -> None:
    """PYTHONPATH makes the real package win over the stub's editable install."""
    assert "PYTHONPATH=/app/src" in DOCKERFILE.read_text(encoding="utf-8")


def test_pip_index_is_overridable_for_builds_outside_china() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert "ARG PIP_INDEX_URL=" in text
    assert "PIP_INDEX_URL=${PIP_INDEX_URL}" in text


def test_container_does_not_run_as_root() -> None:
    lines = _lines()

    assert "USER appuser" in lines
    assert lines.index("USER appuser") < _index_of("CMD [")
