from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from heritagelink.ui import catalog_gallery

GALLERY_APP = """
from pathlib import Path
from heritagelink.catalog import load_reference_catalog
from heritagelink.data_loader import load_data, build_products
from heritagelink.ui.catalog_gallery import render_catalog_gallery

root = Path.cwd()
items = load_reference_catalog(root / 'data/catalog/heritage_products.csv', project_root=root)
products = build_products(load_data(root / 'data/demo'))
render_catalog_gallery(items, products_by_id={p.product_id: p for p in products}, project_root=root)
"""


@pytest.fixture
def gallery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AppTest:
    monkeypatch.setenv("VECTOR_BACKEND", "sqlite")
    monkeypatch.setenv("VECTOR_SQLITE_PATH", str(tmp_path / "vectors.sqlite3"))
    catalog_gallery._similar_ids.clear()
    catalog_gallery._catalog_search.clear()
    return AppTest.from_string(GALLERY_APP).run(timeout=30)


def _images(app: AppTest):
    return app.get("imgs") or app.get("image")


def test_similar_search_is_visible_and_clear_restores_full_catalogue(gallery: AppTest) -> None:
    assert not gallery.exception
    assert len(_images(gallery)) == 50
    gallery.text_input(key="reference_catalog_query").set_value("瓷器 porcelain").run(timeout=30)
    assert not gallery.exception
    assert 0 < len(_images(gallery)) <= 12
    assert any("相关性排序" in item.value for item in gallery.caption)
    gallery.text_input(key="reference_catalog_query").set_value(" ").run(timeout=30)
    assert len(_images(gallery)) == 50


def test_category_is_preserved_with_similar_search(gallery: AppTest) -> None:
    category = gallery.selectbox(key="reference_catalog_category_zh-CN").options[1]
    gallery.selectbox(key="reference_catalog_category_zh-CN").select(category).run(timeout=30)
    expected_maximum = len(_images(gallery))
    gallery.text_input(key="reference_catalog_query").set_value(category).run(timeout=30)
    assert not gallery.exception
    assert 0 < len(_images(gallery)) <= min(12, expected_maximum)
    pills = [item.value for item in gallery.markdown if "hl-catalog-pill" in item.value]
    assert all(category in value for value in pills)


def test_database_failure_falls_back_to_keyword_search(
    gallery: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(catalog_gallery, "create_catalog_search", unavailable)
    gallery.text_input(key="reference_catalog_query").set_value("瓷").run(timeout=30)
    assert not gallery.exception
    assert len(_images(gallery)) > 0
    assert any("已改用精确关键词搜索" in item.value for item in gallery.info)


def test_exact_keyword_mode_does_not_open_vector_database(
    gallery: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Keyword search should not use the vector database")

    monkeypatch.setattr(catalog_gallery, "create_catalog_search", unavailable)
    gallery.radio(key="reference_catalog_search_mode").set_value("exact").run(timeout=30)
    gallery.text_input(key="reference_catalog_query").set_value("porcelain").run(timeout=30)
    assert not gallery.exception
    assert len(_images(gallery)) > 0
    assert not calls


def test_english_search_keeps_localized_category_filter(gallery: AppTest) -> None:
    from heritagelink.i18n import LANGUAGE_SESSION_KEY, Language

    gallery.session_state[LANGUAGE_SESSION_KEY] = Language.EN_US.value
    gallery.run(timeout=30)
    assert gallery.radio(key="reference_catalog_search_mode").options == [
        "Similar content",
        "Exact keywords",
    ]
    category_box = gallery.selectbox(key="reference_catalog_category_en-US")
    category_box.select(category_box.options[1]).run(timeout=30)
    gallery.text_input(key="reference_catalog_query").set_value("porcelain").run(timeout=30)
    assert not gallery.exception
    assert any("catalogue relevance" in item.value for item in gallery.caption)
