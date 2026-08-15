"""Streamlit smoke tests for the bilingual product journeys."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _customer_text(app: AppTest) -> str:
    values = [
        str(item.value)
        for group in (app.markdown, app.caption, app.info, app.success, app.warning)
        for item in group
    ]
    return "\n".join(values)


def test_buyer_page_renders_in_english() -> None:
    app = AppTest.from_file("app.py")
    app.query_params["lang"] = "en"
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["interface_language"] == "en-US"
    assert {"I'm a Buyer", "I'm an Artisan", "How HAHA Works"}.issubset(
        {button.label for button in app.button}
    )
    assert "AI Gift Advisor" in _customer_text(app)
    assert app.chat_input[0].placeholder.startswith("Example:")

    [button for button in app.button if button.label == "Professor or Mentor"][0].click().run(
        timeout=30
    )
    assert "Thanks. I'll organize suitable gifts from the information provided." in _customer_text(
        app
    )
    assert "gifts selected for this occasion" in _customer_text(app)
    assert any(button.label == "Recommend Now" for button in app.button)


def test_artisan_and_growth_pages_render_in_english() -> None:
    app = AppTest.from_file("app.py")
    app.query_params["lang"] = "en"
    app.query_params["mode"] = "artisan"
    app.run(timeout=30)

    assert not app.exception
    assert "Turn your craftsmanship into a trusted digital asset." in _customer_text(app)
    growth_button = [button for button in app.button if button.label == "Growth Studio"][0]
    growth_button.click().run(timeout=30)

    assert not app.exception
    assert app.session_state["artisan_workspace"] == "growth"
    assert "Your AI Growth Team" in _customer_text(app)
    assert any(item.label == "Campaign Language" for item in app.selectbox)


def test_chinese_defaults_remain_compatible() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)

    assert not app.exception
    assert app.session_state["interface_language"] == "zh-CN"
    assert {"我是买家", "我是手艺人", "了解 HAHA"}.issubset({button.label for button in app.button})
    assert "AI 礼赠顾问" in _customer_text(app)
    assert app.chat_input[0].placeholder.startswith("例如")
