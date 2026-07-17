from streamlit.testing.v1 import AppTest


def test_reference_catalog_opens_and_renders_twenty_images() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)
    browse_button = [button for button in app.button if button.label == "浏览 20 件非遗礼赠产品"][0]

    browse_button.click().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "catalog"
    assert any("非遗礼赠产品库" in str(item.value) for item in app.markdown)
    assert len(app.get("image")) == 20
    assert any("¥" in str(item.value) for item in app.markdown)
