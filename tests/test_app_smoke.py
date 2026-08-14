from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from streamlit.testing.v1 import AppTest


def _button(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return [button for button in app.button if button.label == label][-1]


def _text_input(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return [item for item in app.text_input if item.label == label][-1]


def _images(app: AppTest):  # type: ignore[no-untyped-def]
    return app.get("imgs") or app.get("image")


def _all_customer_text(app: AppTest) -> str:
    elements = (
        list(app.markdown)
        + list(app.caption)
        + list(app.info)
        + list(app.warning)
        + list(app.error)
    )
    text = "\n".join(str(item.value) for item in elements)
    return re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", "", text)


def _open_recommendations(text: str = "送给合作伙伴的周年礼物") -> AppTest:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.chat_input[0].set_value(text).run(timeout=30)
    if "recommendation_response" not in app.session_state:
        _button(app, "先看看推荐").click().run(timeout=30)
    return app


def test_app_opens_directly_as_single_page_advisor() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "advisor"
    assert any("选一份真正有意义的礼物" in str(item.value) for item in app.markdown)
    assert any("Heritage Artisans, Horizons Ahead" in str(item.value) for item in app.markdown)
    assert app.chat_input
    assert any("推荐灵感" in str(item.value) for item in app.markdown)
    assert {
        "为海外合作伙伴准备一份中国礼物",
        "给教授或长辈选一份有文化底蕴的礼物",
        "为企业周年寻找可定制纪念礼品",
        "给外国朋友挑一份容易理解的中国文化礼物",
    }.issubset({button.label for button in app.button})


def test_inspiration_card_uses_agent_and_compacts_landing_hero() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)

    _button(app, "为海外合作伙伴准备一份中国礼物").click().run(timeout=30)

    assert app.session_state["conversation_state"].raw_user_texts
    assert str(app.session_state["entry_source"]).startswith("inspiration:")
    assert any('data-ui-state="conversation"' in str(item.value) for item in app.markdown)
    assert not any('data-ui-state="landing"' in str(item.value) for item in app.markdown)
    assert app.chat_input[0].placeholder == "继续描述你的想法…"


def test_customer_flow_hides_technical_and_competition_language() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)
    text = _all_customer_text(app)

    for forbidden in (
        "MVP",
        "Wave 2",
        "演示解析模式",
        "缺失字段",
        "以下内容仍需由您确认",
        "parser mode",
        "API Key",
        "信息覆盖度",
        "推荐置信度",
    ):
        assert forbidden not in text


def test_chat_asks_one_natural_question_and_can_recommend_early() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.chat_input[0].set_value("我想给外国朋友准备一件有中国特色的礼物").run(timeout=30)

    state = app.session_state["conversation_state"]
    assert state.clarification_questions
    question = state.clarification_questions[0]
    assert question.count("？") + question.count("?") <= 1
    assert _button(app, "先看看推荐")

    _button(app, "先看看推荐").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "advisor"
    assert app.chat_input
    assert len(app.session_state["recommendation_response"].recommendations) <= 3
    assert [button for button in app.button if button.label == "选择这件礼物"]


def test_sufficient_information_recommends_without_meaningless_question() -> None:
    app = _open_recommendations("送给合作伙伴的周年礼物")

    state = app.session_state["conversation_state"]
    assert state.ready_to_recommend
    assert not state.clarification_questions
    assert len(_images(app)) >= len(app.session_state["recommendation_response"].recommendations)
    assert all(
        item.product.product_id.startswith("prod_demo_")
        for item in app.session_state["recommendation_response"].recommendations
    )


def test_deepseek_unavailable_remains_customer_friendly() -> None:
    app = _open_recommendations("送给合作伙伴的周年礼物")
    text = _all_customer_text(app)

    assert not app.exception
    assert app.session_state["pending_request"].parser_mode == "deterministic_demo"
    assert "DeepSeek" not in text
    assert "API" not in text
    assert app.session_state["recommendation_response"].recommendations


def test_product_selection_and_final_plan_remain_on_same_page() -> None:
    app = _open_recommendations()
    _button(app, "选择这件礼物").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["selected_product_id"]
    assert app.chat_input
    assert _button(app, "生成我的礼品方案")
    assert any("✓ 已选择" in str(item.value) for item in app.markdown)

    _button(app, "生成我的礼品方案").click().run(timeout=30)

    assert not app.exception
    assert "customization_inquiry" in app.session_state
    assert app.get("download_button")
    assert any("您的专属礼赠方案" in str(item.value) for item in app.markdown)
    assert "MVP" not in _all_customer_text(app)


def test_no_result_does_not_force_a_product() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.chat_input[0].set_value("500件，每件100元，3天内交付到美国，还要Logo").run(timeout=30)
    if app.session_state["recommendation_response"] is None:
        _button(app, "先看看推荐").click().run(timeout=30)

    assert not app.exception
    assert not app.session_state["recommendation_response"].recommendations
    assert not [button for button in app.button if button.label == "选择这件礼物"]
    assert any("目前还没有作品同时满足" in str(item.value) for item in app.info)
    assert {"放宽预算", "调整交期", "看看接近的方案"}.issubset(
        {button.label for button in app.button}
    )


def test_consent_controls_idempotent_ui_persistence(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "ui_choices.sqlite3"
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")
    monkeypatch.setenv("ANALYTICS_DATABASE_URL", f"sqlite:///{database.as_posix()}")
    app = _open_recommendations()
    app.checkbox[0].set_value(True).run(timeout=30)

    choices = [button for button in app.button if button.label == "选择这件礼物"]
    choices[0].click().run(timeout=30)
    app.run(timeout=30)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM selection_events").fetchone()[0] == 1

    choices = [button for button in app.button if button.label == "选择这件礼物"]
    choices[1].click().run(timeout=30)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM selection_events").fetchone()[0] == 2


def test_mobile_css_prevents_horizontal_overflow() -> None:
    theme = (Path(__file__).parents[1] / "src" / "heritagelink" / "ui" / "theme.py").read_text(
        encoding="utf-8"
    )

    assert "@media(max-width:760px)" in theme
    assert "overflow-x:hidden" in theme
    assert ".st-key-landing_composer" in theme
    assert '[data-testid="stBottomBlockContainer"]' in theme
    assert "pointer-events:none" in theme
    assert ".hl-composer-safe-space" in theme


def test_review_trace_is_hidden_by_default_and_requires_both_gates(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("AGENT_REVIEW_MODE_ENABLED", raising=False)
    customer = AppTest.from_file("app.py").run(timeout=30)
    assert not any("Agent 执行轨迹" in str(item.value) for item in customer.markdown)

    query_only = AppTest.from_file("app.py")
    query_only.query_params["review_mode"] = "1"
    query_only.run(timeout=30)
    assert not any("Agent 执行轨迹" in str(item.value) for item in query_only.markdown)

    monkeypatch.setenv("AGENT_REVIEW_MODE_ENABLED", "true")
    env_only = AppTest.from_file("app.py").run(timeout=30)
    assert not any("Agent 执行轨迹" in str(item.value) for item in env_only.markdown)

    review = AppTest.from_file("app.py")
    review.query_params["review_mode"] = "1"
    review.run(timeout=30)
    assert any("Agent 执行轨迹" in str(item.value) for item in review.markdown)


def test_customer_can_restart_through_existing_agent_action() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.chat_input[0].set_value("我想准备一份礼物").run(timeout=30)

    _button(app, "重新开始").click().run(timeout=30)

    assert not app.session_state["conversation_state"].raw_user_texts
    assert (
        "recommendation_response" not in app.session_state
        or app.session_state["recommendation_response"] is None
    )
