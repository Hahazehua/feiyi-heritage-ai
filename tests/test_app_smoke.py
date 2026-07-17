from streamlit.testing.v1 import AppTest


def _button(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return [button for button in app.button if button.label == label][-1]


def _text_input(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return [item for item in app.text_input if item.label == label][-1]


def _open_app() -> AppTest:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.radio[1].set_value("确定性演示模式").run(timeout=30)
    return app


def _open_demo_confirmation() -> AppTest:
    app = _open_app()
    _button(app, "体验企业海外礼赠案例").click().run(timeout=30)
    return app


def _open_recommendations() -> AppTest:
    app = _open_demo_confirmation()
    _button(app, "确认并查看推荐").click().run(timeout=30)
    return app


def test_home_explains_value_and_demo_case_reaches_confirmation() -> None:
    app = _open_app()

    assert not app.exception
    assert any("飞颐礼遇" in str(item.value) for item in app.markdown)
    assert any("让中国非遗礼赠需求" in str(item.value) for item in app.markdown)
    assert any("MVP 演示数据 / MVP demo data" in str(item.value) for item in app.caption)
    assert _button(app, "开始智能选礼")

    _button(app, "体验企业海外礼赠案例").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "confirm"
    parsed = app.session_state["pending_request"]
    assert parsed.quantity == 20
    assert parsed.budget_per_item == 300
    assert parsed.logo_required is True
    assert parsed.destination == "United States"


def test_confirmation_is_required_before_recommendations() -> None:
    app = _open_demo_confirmation()

    assert "recommendation_response" not in app.session_state
    assert any("AI 已理解您的礼赠需求" in str(item.value) for item in app.markdown)
    assert _button(app, "返回修改需求")

    _button(app, "确认并查看推荐").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "recommend"
    assert "recommendation_response" in app.session_state
    response = app.session_state["recommendation_response"]
    assert 1 <= len(response.recommendations) <= 3
    assert len([button for button in app.button if button.label == "选择此方案"]) <= 3
    assert len(app.get("image")) == len(response.recommendations)


def test_confirmation_does_not_invent_unstated_select_fields() -> None:
    app = _open_app()
    app.text_area[0].set_value("想给朋友挑一件有文化故事的礼物")
    _button(app, "开始智能选礼").click().run(timeout=30)

    assert app.session_state["pending_request"].customer_type is None
    assert app.session_state["pending_request"].output_language is None
    _button(app, "确认并查看推荐").click().run(timeout=30)

    confirmed = app.session_state["confirmed_customer_request"]
    assert confirmed.customer_type is None
    assert confirmed.output_language is None
    assert any("预算待补充" in str(item.value) for item in app.markdown)
    assert any("数量待补充" in str(item.value) for item in app.markdown)


def test_confirmation_supports_a_second_conversation_turn() -> None:
    app = _open_app()
    app.text_area[0].set_value("送给合作伙伴的周年礼物")
    _button(app, "开始智能选礼").click().run(timeout=30)

    _text_input(app, "继续补充或修正需求").set_value("30件，每件预算1000元")
    _button(app, "合并这条补充").click().run(timeout=30)

    assert not app.exception
    parsed = app.session_state["pending_request"]
    assert parsed.recipient == "business_partner"
    assert parsed.scene == "anniversary"
    assert parsed.quantity == 30
    assert parsed.budget_per_item == 1000
    assert len(app.session_state["conversation_state"].raw_user_texts) == 2

    _button(app, "确认并查看推荐").click().run(timeout=30)

    assert not app.exception
    confirmed = app.session_state["confirmed_customer_request"]
    assert confirmed.quantity == 30
    assert confirmed.budget_per_item == 1000


def test_confirmation_preserves_pattern_customization_as_a_hard_requirement() -> None:
    app = _open_app()
    app.text_area[0].set_value("为20位合作伙伴准备周年礼物，每件预算500元，需要图案定制")
    _button(app, "开始智能选礼").click().run(timeout=30)

    assert "pattern" in app.session_state["pending_request"].customization_types
    _button(app, "确认并查看推荐").click().run(timeout=30)

    assert not app.exception
    confirmed = app.session_state["confirmed_customer_request"]
    assert confirmed.customization_required is True
    assert "pattern" in confirmed.customization_types


def test_exploratory_flow_keeps_unknown_inquiry_facts_pending() -> None:
    app = _open_app()
    app.text_area[0].set_value("想给朋友挑一件有文化故事的礼物")
    _button(app, "开始智能选礼").click().run(timeout=30)
    _button(app, "确认并查看推荐").click().run(timeout=30)
    _button(app, "选择此方案").click().run(timeout=30)
    _button(app, "继续生成商家需求单").click().run(timeout=30)

    assert not app.exception
    inquiry = app.session_state["customization_inquiry"]
    assert inquiry["request_snapshot"]["unit_budget_max_fen"] is None
    assert inquiry["request_snapshot"]["quantity"] is None
    assert inquiry["customization_brief"]["logo_required"] is None
    assert inquiry["delivery"]["international_shipping_required"] is None
    assert any("MVP 演示需求单" in str(item.value) for item in app.warning)


def test_product_culture_and_inquiry_complete_five_stage_flow() -> None:
    app = _open_recommendations()

    _button(app, "查看文化故事").click().run(timeout=30)
    assert not app.exception
    assert app.session_state["ui_stage"] == "culture"
    assert {tab.label for tab in app.tabs} == {
        "中文文化介绍",
        "English Cultural Story",
        "工艺与依据",
        "定制建议",
    }

    _button(app, "选择此方案并生成需求单").click().run(timeout=30)
    assert not app.exception
    assert app.session_state["ui_stage"] == "inquiry"
    assert app.get("download_button")
    assert any(item.label == "可复制的需求摘要" for item in app.text_area)
    assert _button(app, "返回查看其他方案")
    assert _button(app, "重新开始")


def test_reconfirming_request_invalidates_and_rebuilds_inquiry() -> None:
    app = _open_recommendations()
    _button(app, "选择此方案").click().run(timeout=30)
    _button(app, "继续生成商家需求单").click().run(timeout=30)

    assert app.session_state["customization_inquiry"]["request_snapshot"]["quantity"] == 20

    _button(app, "返回查看其他方案").click().run(timeout=30)
    _button(app, "重新调整需求").click().run(timeout=30)
    _text_input(app, "采购数量").set_value("30")
    _button(app, "确认并查看推荐").click().run(timeout=30)

    assert "customization_inquiry" not in app.session_state
    _button(app, "选择此方案").click().run(timeout=30)
    _button(app, "继续生成商家需求单").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["customization_inquiry"]["request_snapshot"]["quantity"] == 30


def test_precise_form_no_result_does_not_force_recommendation() -> None:
    app = _open_app()
    app.radio[0].set_value("精准填写需求").run(timeout=30)
    _text_input(app, "单件预算（元）").set_value("100")
    _text_input(app, "采购数量").set_value("1")
    _button(app, "确认这些需求").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "confirm"
    _button(app, "确认并查看推荐").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "recommend"
    assert not app.session_state["recommendation_response"].recommendations
    assert any("不会强行推荐" in str(item.value) for item in app.error)
    assert not [button for button in app.button if button.label == "选择此方案"]


def test_precise_form_does_not_preselect_unstated_customer_facts() -> None:
    app = _open_app()
    app.radio[0].set_value("精准填写需求").run(timeout=30)
    _text_input(app, "单件预算（元）").set_value("1000")
    _text_input(app, "采购数量").set_value("10")
    _button(app, "确认这些需求").click().run(timeout=30)

    assert not app.exception
    parsed = app.session_state["pending_request"]
    assert parsed.customer_type is None
    assert parsed.recipient is None
    assert parsed.scene is None
    assert parsed.output_language is None
    assert parsed.international_shipping_required is None


def test_restart_returns_to_clean_home() -> None:
    app = _open_recommendations()
    _button(app, "选择此方案").click().run(timeout=30)
    _button(app, "继续生成商家需求单").click().run(timeout=30)
    _button(app, "重新开始").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["ui_stage"] == "describe"
    assert "recommendation_response" not in app.session_state
    assert app.session_state["hero_request_text"] == ""
