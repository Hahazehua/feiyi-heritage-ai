from streamlit.testing.v1 import AppTest


def _buyer_app() -> AppTest:
    """Open the buyer side directly, past the entry chooser."""
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "buyer"
    return app


def _images(app: AppTest):  # type: ignore[no-untyped-def]
    """Return image elements across Streamlit AppTest protocol names."""
    return app.get("imgs") or app.get("image")


def test_reference_catalog_is_a_secondary_single_page_section() -> None:
    app = _buyer_app().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "advisor"
    assert any(expander.label == "浏览完整礼品目录" for expander in app.expander)
    assert len(_images(app)) == 54
    assert any("¥" in str(item.value) for item in app.markdown)
