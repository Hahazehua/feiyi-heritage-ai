from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from streamlit.testing.v1 import AppTest


def _buyer_app() -> AppTest:
    """Open the buyer side directly.

    The app now asks which side you are here for before rendering either one.
    These tests exercise what happens after that choice, so they arrive by the
    same deep link a returning visitor or a reviewer would use; the chooser
    itself is covered in test_entry_screen.py.
    """
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "buyer"
    return app


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
    return "\n".join(str(item.value) for item in elements)


def _open_recommendations(text: str = "送给合作伙伴的周年礼物") -> AppTest:
    app = _buyer_app().run(timeout=30)
    app.chat_input[0].set_value(text).run(timeout=30)
    if "recommendation_response" not in app.session_state:
        _button(app, "先为我推荐").click().run(timeout=30)
    return app


def test_app_opens_directly_as_single_page_advisor() -> None:
    app = _buyer_app().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "advisor"
    assert any("HAHA｜飞颐礼遇" in str(item.value) for item in app.markdown)
    assert any("连接非遗手艺人与全球礼赠及商业机会" in str(item.value) for item in app.markdown)
    assert app.chat_input
    assert any("您好，我是 HAHA｜飞颐礼遇顾问" in str(item.value) for item in app.markdown)
    assert {"送海外合作伙伴", "送教授或长辈", "企业周年纪念", "我还没有明确想法"}.issubset(
        {button.label for button in app.button}
    )


def test_customer_flow_hides_technical_and_competition_language() -> None:
    app = _buyer_app().run(timeout=30)
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
    app = _buyer_app().run(timeout=30)
    app.chat_input[0].set_value("我想给外国朋友准备一件有中国特色的礼物").run(timeout=30)

    state = app.session_state["conversation_state"]
    assert state.clarification_questions
    question = state.clarification_questions[0]
    assert question.count("？") + question.count("?") <= 1
    assert _button(app, "先为我推荐")

    _button(app, "先为我推荐").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "advisor"
    assert app.chat_input
    assert len(app.session_state["recommendation_response"].recommendations) <= 3
    assert [button for button in app.button if button.label == "选择这件礼品"]


def test_sufficient_information_recommends_without_meaningless_question() -> None:
    app = _open_recommendations("送给合作伙伴的周年礼物")

    state = app.session_state["conversation_state"]
    assert state.ready_to_recommend
    assert not state.clarification_questions
    assert len(_images(app)) >= len(app.session_state["recommendation_response"].recommendations)


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
    _button(app, "选择这件礼品").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["selected_product_id"]
    assert app.chat_input
    assert _button(app, "生成我的礼品方案")

    _button(app, "生成我的礼品方案").click().run(timeout=30)

    assert not app.exception
    assert "customization_inquiry" in app.session_state
    assert app.get("download_button")
    assert any("您的专属礼品方案" in str(item.value) for item in app.markdown)
    assert "MVP" not in _all_customer_text(app)


def test_no_result_does_not_force_a_product() -> None:
    app = _buyer_app().run(timeout=30)
    _text_input(app, "单件预算（元）").set_value("100")
    _text_input(app, "采购数量").set_value("1")
    _button(app, "填写完成，开始匹配").click().run(timeout=30)

    assert not app.exception
    assert not app.session_state["recommendation_response"].recommendations
    assert not [button for button in app.button if button.label == "选择这件礼品"]
    assert any("暂时没有同时符合" in str(item.value) for item in app.info)


def test_consent_controls_idempotent_ui_persistence(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "ui_choices.sqlite3"
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")
    monkeypatch.setenv("ANALYTICS_DATABASE_URL", f"sqlite:///{database.as_posix()}")
    app = _open_recommendations()
    app.checkbox[0].set_value(True).run(timeout=30)

    choices = [button for button in app.button if button.label == "选择这件礼品"]
    choices[0].click().run(timeout=30)
    app.run(timeout=30)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM selection_events").fetchone()[0] == 1

    choices = [button for button in app.button if button.label == "选择这件礼品"]
    choices[1].click().run(timeout=30)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM selection_events").fetchone()[0] == 2


def _theme_css() -> str:
    """Theme source with whitespace collapsed, so assertions describe rules
    rather than formatting."""
    source = (Path(__file__).parents[1] / "src" / "heritagelink" / "ui" / "theme.py").read_text(
        encoding="utf-8"
    )
    return re.sub(r"\s+", "", source)


def test_mobile_css_prevents_horizontal_overflow() -> None:
    css = _theme_css()

    assert "@media(max-width:760px)" in css
    assert "overflow-x:hidden" in css
    # The wide comparison table is replaced by stacked cards on narrow
    # screens; both halves of that swap have to exist or one layout leaks.
    assert ".hl-comparison-mobile{display:none" in css
    assert ".hl-comparison-desktop{display:none}" in css
    assert ".hl-comparison-mobile{display:block}" in css


def test_theme_exposes_design_tokens() -> None:
    """Every page has to draw from one token set rather than local values."""
    css = _theme_css()

    for token in (
        "--paper:",
        "--ink-900:",
        "--ink-500:",
        "--bronze:",
        "--line:",
        "--text-base:",
        "--sp-4:",
        "--r-md:",
        "--shadow-md:",
        "--font-ui:",
        "--font-display:",
    ):
        assert token in css, f"missing design token {token}"


def test_theme_defines_visible_focus_styles() -> None:
    """Keyboard users need a visible focus indicator on interactive elements."""
    css = _theme_css()

    assert ":focus-visible" in css
    assert "outline:2pxsolidvar(--focus)" in css


def test_review_trace_is_hidden_by_default_and_requires_both_gates(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("AGENT_REVIEW_MODE_ENABLED", raising=False)
    customer = _buyer_app().run(timeout=30)
    assert not any("Agent 执行轨迹" in str(item.value) for item in customer.markdown)

    query_only = _buyer_app()
    query_only.query_params["review_mode"] = "1"
    query_only.run(timeout=30)
    assert not any("Agent 执行轨迹" in str(item.value) for item in query_only.markdown)

    monkeypatch.setenv("AGENT_REVIEW_MODE_ENABLED", "true")
    env_only = _buyer_app().run(timeout=30)
    assert not any("Agent 执行轨迹" in str(item.value) for item in env_only.markdown)

    review = _buyer_app()
    review.query_params["review_mode"] = "1"
    review.run(timeout=30)
    assert any("Agent 执行轨迹" in str(item.value) for item in review.markdown)


def test_customer_can_restart_through_existing_agent_action() -> None:
    app = _buyer_app().run(timeout=30)
    app.chat_input[0].set_value("我想准备一份礼物").run(timeout=30)

    _button(app, "重新开始").click().run(timeout=30)

    assert not app.session_state["conversation_state"].raw_user_texts
    assert (
        "recommendation_response" not in app.session_state
        or app.session_state["recommendation_response"] is None
    )


def test_catalog_snapshot_keeps_twenty_formal_and_thirty_reference_only_products() -> None:
    app = _open_recommendations("送给合作伙伴的周年礼物")
    recommendation_trace = next(
        trace
        for trace in app.session_state["agent_execution_trace"]
        if trace.skill_id == "recommend_heritage_gifts"
    )

    assert not app.exception
    assert recommendation_trace.input_summary["catalog_total"] == 50
    assert recommendation_trace.input_summary["formally_recommendable"] == 20
    assert recommendation_trace.input_summary["reference_only"] == 30


def test_comparison_button_renders_shopping_guide_and_keeps_chat_available() -> None:
    app = _open_recommendations("送给合作伙伴的周年礼物")
    count = len(app.session_state["recommendation_response"].recommendations)

    _button(app, f"比较这{count}件").click().run(timeout=30)

    text = _all_customer_text(app)
    assert not app.exception
    assert app.session_state["comparison_result"] is not None
    assert app.session_state["recommendation_response"].recommendations
    assert app.chat_input
    assert any("件礼物怎么选" in str(item.value) for item in app.markdown)
    assert {"选择推荐款", "继续比较", "调整需求"}.issubset({button.label for button in app.button})
    for forbidden in (
        "comparison_score",
        "overall_comparison_score",
        "comparison_explanation_source",
        "deterministic_fallback",
        "Application Action",
        "API",
        "DataFrame",
    ):
        assert forbidden not in text


def test_two_recommendations_use_correct_comparison_count_copy() -> None:
    app = _open_recommendations("需要5件礼物，每件预算380元")
    if app.session_state["recommendation_response"] is None:
        _button(app, "先为我推荐").click().run(timeout=30)

    assert len(app.session_state["recommendation_response"].recommendations) == 2
    _button(app, "比较这2件").click().run(timeout=30)

    assert not app.exception
    assert len(app.session_state["comparison_result"].items) == 2
    assert any("这两件礼物怎么选" in str(item.value) for item in app.markdown)


def test_natural_language_comparison_then_selection_remain_in_one_session() -> None:
    app = _open_recommendations("送给合作伙伴的周年礼物")
    app.chat_input[-1].set_value("第一个和第三个哪个更适合商务伙伴？").run(timeout=30)

    assert not app.exception
    assert app.session_state["comparison_result"] is not None
    compared_ids = app.session_state["comparison_result"].compared_product_ids
    assert len(compared_ids) == 2
    assert app.chat_input

    app.chat_input[-1].set_value("那我选第一个").run(timeout=30)

    assert not app.exception
    assert app.session_state["selected_product_id"] == compared_ids[0]
    assert app.session_state["comparison_result"] is not None
    assert app.chat_input


def test_natural_language_modern_refinement_replaces_old_style_and_clears_comparison() -> None:
    app = _open_recommendations("送给合作伙伴的周年礼物，希望风格传统")
    _button(
        app,
        f"比较这{len(app.session_state['recommendation_response'].recommendations)}件",
    ).click().run(timeout=30)
    assert app.session_state["comparison_result"] is not None

    app.chat_input[-1].set_value("再现代一点").run(timeout=30)

    parsed = app.session_state["pending_request"]
    assert not app.exception
    assert parsed.style_preferences == ("modern",)
    assert "traditional" not in parsed.style_preferences
    assert app.session_state["comparison_result"] is None
    assert app.session_state["recommendation_response"].recommendations


def test_review_mode_shows_application_trace_only_behind_existing_double_gate(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("AGENT_REVIEW_MODE_ENABLED", "true")
    customer = _open_recommendations("送给合作伙伴的周年礼物")
    _button(
        customer,
        f"比较这{len(customer.session_state['recommendation_response'].recommendations)}件",
    ).click().run(timeout=30)
    assert "Application Action" not in _all_customer_text(customer)

    review = _buyer_app()
    review.query_params["review_mode"] = "1"
    review.run(timeout=30)
    review.chat_input[0].set_value("送给合作伙伴的周年礼物").run(timeout=30)
    if "recommendation_response" not in review.session_state:
        _button(review, "先为我推荐").click().run(timeout=30)
    _button(
        review,
        f"比较这{len(review.session_state['recommendation_response'].recommendations)}件",
    ).click().run(timeout=30)

    assert any("Application Actions" in str(item.value) for item in review.markdown)
    assert any("Application Action：product_comparison" in item.label for item in review.expander)
    assert len(review.session_state["agent_execution_trace"]) == 7
    assert all(
        trace.status.value == "skipped" for trace in review.session_state["agent_execution_trace"]
    )
