"""The README publishes a catalogue table and states that its numbers come from
the current CSV contents rather than from older documents. Nothing enforced
that promise, so every figure drifted the moment a product was added. These
tests recompute each cell from the data files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from heritagelink.data_loader import load_data

ROOT = Path(__file__).parents[1]
DATA_DIR = ROOT / "data" / "demo"
README = ROOT / "README.md"


@pytest.fixture(scope="module")
def readme_table() -> dict[str, tuple[int, ...]]:
    """Every two-column README row whose value cell carries numbers."""
    rows: dict[str, tuple[int, ...]] = {}
    for line in README.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 2:
            continue
        numbers = tuple(int(number) for number in re.findall(r"\d+", cells[1]))
        if numbers:
            rows.setdefault(cells[0], numbers)
    return rows


def _cell(table: dict[str, tuple[int, ...]], label: str) -> tuple[int, ...]:
    assert label in table, f"README no longer has a numeric row labelled {label!r}"
    return table[label]


def test_readme_product_counts_match_the_catalogue(readme_table) -> None:  # type: ignore[no-untyped-def]
    products = load_data(DATA_DIR).products
    roles = products["catalog_role"]

    assert _cell(readme_table, "Catalogue records") == (len(products),)
    recommendable = int((roles == "recommendation_demo").sum())
    reference = int((roles == "catalog_reference").sum())
    assert _cell(readme_table, "Recommendation-eligible") == (recommendable,)
    assert _cell(readme_table, "Museum or cultural reference") == (reference,)


def test_readme_reports_every_unverified_record(readme_table) -> None:  # type: ignore[no-untyped-def]
    """A record that declares needs_verification must be counted in the open,
    not folded into the museum-sourced total."""
    products = load_data(DATA_DIR).products
    pending = int((products["verification_status"] == "needs_verification").sum())

    assert _cell(readme_table, "Partner-supplied, pending verification") == (pending,)


def test_readme_content_and_category_counts_match(readme_table) -> None:  # type: ignore[no-untyped-def]
    bundle = load_data(DATA_DIR)
    texts = bundle.product_texts
    per_locale = {int(count) for count in texts["locale"].value_counts()}

    assert len(per_locale) == 1, "the two locales no longer carry equal text counts"
    assert _cell(readme_table, "Bilingual content records") == (len(texts), per_locale.pop())
    assert _cell(readme_table, "Category coverage") == (bundle.products["category_code"].nunique(),)


def test_readme_data_quality_row_covers_the_whole_catalogue(readme_table) -> None:  # type: ignore[no-untyped-def]
    products = load_data(DATA_DIR).products
    level_c = int((products["data_quality_level"] == "C").sum())

    assert level_c == len(products), "the table claims every record is Level C"
    assert _cell(readme_table, "Data quality") == (level_c,)


def test_readme_category_list_names_every_category() -> None:
    """The prose under the table enumerates the category codes; a new category
    has to appear there too, not only in the count."""
    products = load_data(DATA_DIR).products
    sentences = [
        line
        for line in README.read_text(encoding="utf-8").splitlines()
        if line.startswith("Categories: `")
    ]
    assert len(sentences) == 1, "expected exactly one category-list sentence in the README"
    listed = set(re.findall(r"`([a-z_]+)`", sentences[0]))

    assert listed == set(products["category_code"])
