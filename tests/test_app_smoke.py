from streamlit.testing.v1 import AppTest


def _button(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return next(button for button in app.button if button.label == label)


def test_detailed_form_submits_request_and_generates_inquiry() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)

    assert not app.exception
    assert any("仅用于MVP演示" in str(message.value) for message in app.error)

    _button(app, "开始推荐").click().run(timeout=30)

    assert not app.exception
    assert any("找到 3 件" in str(message.value) for message in app.success)
    inquiry_buttons = [button for button in app.button if button.label == "生成定制需求单"]
    assert len(inquiry_buttons) == 3

    inquiry_buttons[0].click().run(timeout=30)

    assert not app.exception
    assert any("结构化定制需求单" in str(message.value) for message in app.success)
    assert app.json
    assert app.get("download_button")


def test_detailed_form_does_not_force_recommendation_when_budget_is_too_low() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.number_input[0].set_value(100)
    _button(app, "开始推荐").click().run(timeout=30)

    assert not app.exception
    assert any("没有合格产品" in str(message.value) for message in app.error)
    assert not [button for button in app.button if button.label == "生成定制需求单"]


def test_smart_description_demo_flow_passes_apptest_smoke() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.radio[0].set_value("智能描述").run(timeout=30)
    app.radio[1].set_value("确定性演示解析").run(timeout=30)
    app.text_area[0].set_value(
        "给30位美国合作伙伴准备周年礼物，每件预算1000元，"
        "可以加公司Logo，30天内完成，需要中英文介绍。"
    )
    _button(app, "AI解析需求").click().run(timeout=30)

    assert not app.exception
    assert any("当前使用演示解析模式" in str(message.value) for message in app.warning)

    _button(app, "开始推荐").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["gift_request"].quantity == 30
    assert app.session_state["gift_request"].logo_required is True
    assert "recommendation_response" in app.session_state


def test_deepseek_failure_does_not_break_detailed_form() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.radio[0].set_value("智能描述").run(timeout=30)
    app.text_area[0].set_value("准备一批礼物")
    _button(app, "AI解析需求").click().run(timeout=30)
    assert not app.exception

    app.radio[0].set_value("详细表单").run(timeout=30)
    _button(app, "开始推荐").click().run(timeout=30)

    assert not app.exception
    assert "recommendation_response" in app.session_state
