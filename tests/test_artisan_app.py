from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from heritagelink.artisan_studio import create_draft, enrich_draft, submit_for_review
from heritagelink.data_loader import build_products, load_data
from heritagelink.heritage_passport_models import PublicationStatus
from heritagelink.repositories.memory_artisan_draft_repository import (
    MemoryArtisanDraftRepository,
)

ROOT = Path(__file__).parents[1]


def _buyer_app() -> AppTest:
    """Open the buyer side directly, past the entry chooser.

    Tests that want the artisan side overwrite the mode after calling this.
    """
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "buyer"
    return app


def _by_label(elements, label: str):  # type: ignore[no-untyped-def]
    matches = [element for element in elements if element.label == label]
    assert len(matches) == 1, f"expected one {label!r} widget, found {len(matches)}"
    return matches[0]


def _button(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return _by_label(app.button, label)


def _text_input(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return _by_label(app.text_input, label)


def _text_area(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return _by_label(app.text_area, label)


def _selectbox(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return _by_label(app.selectbox, label)


def _customer_text(app: AppTest) -> str:
    elements = (
        list(app.markdown)
        + list(app.caption)
        + list(app.info)
        + list(app.warning)
        + list(app.error)
        + list(app.success)
    )
    return "\n".join(str(element.value) for element in elements)


def _artisan_app(*, review_mode: bool = False) -> AppTest:
    app = _buyer_app()
    app.query_params["mode"] = "artisan"
    if review_mode:
        app.query_params["review_mode"] = "1"
    return app.run(timeout=30)


def _advance_to_review(app: AppTest) -> AppTest:
    _button(app, "开始添加作品").click().run(timeout=30)
    assert app.session_state["artisan_stage"] == "story"

    _text_input(app, "作品名称").set_value("芜湖铁画迎客松")
    _text_input(app, "工艺类别").set_value("芜湖铁画")
    _text_input(app, "所在地区").set_value("安徽芜湖")
    _text_area(app, "自由描述").set_value(
        "这是一件芜湖铁画作品，以迎客松为主题，适合作为企业礼赠。"
    )
    _button(app, "保存并继续：商业信息").click().run(timeout=30)
    assert app.session_state["artisan_stage"] == "commercial"

    # The story step now renders a second widget group above its form, so its
    # keys leave AppTest's tree a run earlier than they used to. Restore them
    # before the next transition, the same way the commercial values are
    # restored below. Checked by hand in the running app: both the quick intake
    # and the step-by-step form behave correctly there.
    for key, value in {
        "artisan_story_product_name": "芜湖铁画迎客松",
        "artisan_story_craft_category": "芜湖铁画",
        "artisan_story_region": "安徽芜湖",
        "artisan_story_description": ("这是一件芜湖铁画作品，以迎客松为主题，适合作为企业礼赠。"),
        "artisan_quick_description": "",
    }.items():
        app.session_state[key] = value

    # Every commercial field is intentionally optional. Blank means unknown,
    # never a negative claim.
    _button(app, "保存并继续：文化与来源").click().run(timeout=30)
    assert app.session_state["artisan_stage"] == "culture"
    # Streamlit's test tree can retain nodes from a replaced form for one event.
    # Restore their values so that AppTest can serialize the transition exactly
    # as the browser already does. The story step needs the same treatment now
    # that it renders a second widget group above its form: the browser drops
    # those keys a run earlier than AppTest expects. Verified by hand in the
    # running app — the quick intake and the step form both behave correctly.
    stale_commercial_values = {
        "artisan_commercial_price_min": "",
        "artisan_commercial_price_max": "",
        "artisan_commercial_currency": "暂不确定",
        "artisan_commercial_moq": "",
        "artisan_commercial_lead_time": "",
        "artisan_commercial_customization": "",
        "artisan_commercial_logo": "暂不确定",
        "artisan_commercial_packaging": "",
        "artisan_commercial_dimensions": "",
        "artisan_commercial_materials": "",
        "artisan_commercial_domestic_shipping": "暂不确定",
        "artisan_commercial_international_shipping": "暂不确定",
        "artisan_commercial_capacity": "",
    }
    for key, value in stale_commercial_values.items():
        app.session_state[key] = value

    _button(app, "AI 协助整理并进入确认").click().run(timeout=30)
    assert app.session_state["artisan_stage"] == "review"
    return app


def _advance_to_submitted(app: AppTest) -> AppTest:
    _advance_to_review(app)
    _button(app, "确认并生成文化护照").click().run(timeout=30)
    assert app.session_state["artisan_stage"] == "passport"
    _button(app, "保存并提交审核").click().run(timeout=30)
    assert app.session_state["artisan_stage"] == "submitted"
    return app


def _open_recommendations() -> AppTest:
    app = _buyer_app().run(timeout=30)
    app.chat_input[0].set_value("送给海外合作伙伴的周年纪念礼物").run(timeout=30)
    if (
        "recommendation_response" not in app.session_state
        or app.session_state["recommendation_response"] is None
    ):
        _button(app, "先为我推荐").click().run(timeout=30)
    return app


def _render_submitted_review_state(
    monkeypatch: pytest.MonkeyPatch,
    *,
    env_gate: bool,
    query_gate: bool,
) -> AppTest:
    if env_gate:
        monkeypatch.setenv("AGENT_REVIEW_MODE_ENABLED", "true")
    else:
        monkeypatch.delenv("AGENT_REVIEW_MODE_ENABLED", raising=False)
    app = _artisan_app(review_mode=query_gate)
    draft = create_draft(
        "review-gate-session",
        {
            "product_name_zh": "审核门测试作品",
            "craft_name": "传统工艺",
            "region": "中国",
        },
    )
    draft, trace = enrich_draft(draft)
    draft = submit_for_review(draft, MemoryArtisanDraftRepository())
    app.session_state["artisan_draft"] = draft
    app.session_state["artisan_passport"] = None
    app.session_state["artisan_application_trace"] = (trace,)
    app.session_state["artisan_stage"] = "submitted"
    return app.run(timeout=30)


def test_buyer_side_hides_the_artisan_entry_and_keeps_one_chat_input() -> None:
    """Each side should read as its own site once a role has been chosen."""
    app = _buyer_app().run(timeout=30)
    labels = {button.label for button in app.button}

    assert not app.exception
    assert app.session_state["app_mode"] == "buyer"
    # The role choice belongs to the entry screen, and the way back is the
    # footer — neither should reappear as primary navigation.
    assert "我是手艺人" not in labels
    assert "切换身份" in labels
    assert len(app.chat_input) == 1


def test_artisan_query_mode_is_a_distinct_single_page_without_buyer_catalog() -> None:
    app = _artisan_app()
    text = _customer_text(app)

    assert not app.exception
    assert app.session_state["app_mode"] == "artisan"
    assert not app.chat_input
    assert "让你的作品被世界更好地理解" in text
    assert _button(app, "开始添加作品")
    assert not [item for item in app.expander if item.label == "浏览完整礼品目录"]
    assert not [item for item in app.selectbox if item.label == "按工艺筛选"]


def test_blank_optional_artisan_flow_submits_pending_without_touching_catalog_or_choices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    choice_database = tmp_path / "choice_analytics.sqlite3"
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")
    monkeypatch.setenv(
        "ANALYTICS_DATABASE_URL",
        f"sqlite:///{choice_database.as_posix()}",
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
    app = _advance_to_submitted(_artisan_app())

    draft = app.session_state["artisan_draft"]
    assert not app.exception
    assert draft.image_bytes is None
    assert draft.publication_status is PublicationStatus.PENDING_REVIEW
    assert "作品资料已保存并提交审核" in _customer_text(app)
    assert not choice_database.exists()

    bundle = load_data(ROOT / "data" / "demo")
    products = build_products(bundle)
    assert sum(product.catalog_role == "recommendation_demo" for product in products) == 23
    assert sum(product.catalog_role == "catalog_reference" for product in products) == 30


def test_no_ai_key_has_friendly_fallback_and_still_reaches_passport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
    app = _advance_to_review(_artisan_app())

    assert not app.exception
    assert app.session_state["artisan_ai_status"] == "fallback"
    assert "AI 双语辅助暂时不可用" in _customer_text(app)
    assert "API Key" not in _customer_text(app)

    _button(app, "确认并生成文化护照").click().run(timeout=30)
    assert not app.exception
    assert app.session_state["artisan_stage"] == "passport"
    assert "你的非遗文化护照" in _customer_text(app)


def test_buyer_recommendations_include_customer_safe_heritage_passports() -> None:
    app = _open_recommendations()
    text = _customer_text(app)

    assert not app.exception
    recommendations = app.session_state["recommendation_response"].recommendations
    assert recommendations
    assert len([item for item in app.expander if item.label == "文化护照"]) == len(recommendations)
    assert "HERITAGE PASSPORT · 非遗文化护照" in text
    for raw_token in (
        "pending_review",
        "reference_only",
        "recommendable",
        "artisan_provided",
        "merchant_confirmed",
        "public_source",
        "ai_inferred",
        "verification_status",
        "demo_assumption",
    ):
        assert raw_token not in text


def test_reference_only_category_hides_demo_commercial_terms() -> None:
    app = _buyer_app().run(timeout=30)
    _selectbox(app, "按工艺筛选").set_value("中国书法馆藏参考").run(timeout=30)
    text = _customer_text(app)

    assert not app.exception
    assert "当前显示 5 / 50 件" in text
    assert "馆藏探索参考 · 不参与推荐" in text
    assert "¥" not in text
    assert "目录起订" not in text
    assert "基础制作周期" not in text
    assert "Demo 商业参数" not in text
    assert "demo_assumption" not in text


def test_artisan_review_actions_require_environment_and_query_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_only = _render_submitted_review_state(
        monkeypatch,
        env_gate=False,
        query_gate=True,
    )
    assert not [button for button in query_only.button if button.label == "模拟审核通过"]
    assert "Agent 执行轨迹" not in _customer_text(query_only)

    env_only = _render_submitted_review_state(
        monkeypatch,
        env_gate=True,
        query_gate=False,
    )
    assert not [button for button in env_only.button if button.label == "模拟审核通过"]
    assert "Agent 执行轨迹" not in _customer_text(env_only)

    both = _render_submitted_review_state(
        monkeypatch,
        env_gate=True,
        query_gate=True,
    )
    assert _button(both, "模拟审核通过")
    assert "Agent 执行轨迹" in _customer_text(both)
    assert any(
        "Application Action：artisan_product_onboarding" in item.label for item in both.expander
    )
