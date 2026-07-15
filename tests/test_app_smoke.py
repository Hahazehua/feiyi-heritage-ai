from streamlit.testing.v1 import AppTest


def _button(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return next(button for button in app.button if button.label == label)


def _open_advisor() -> AppTest:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.radio[1].set_value("确定性演示模式").run(timeout=30)
    return app


def _open_detailed_form() -> AppTest:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.radio[0].set_value("详细表单").run(timeout=30)
    return app


def test_detailed_form_submits_request_and_generates_inquiry() -> None:
    app = _open_detailed_form()

    assert not app.exception
    assert not app.error
    assert any("为每一次赠礼" in str(item.value) for item in app.markdown)
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


def test_detailed_form_no_result_can_generate_customization_concept() -> None:
    app = _open_detailed_form()
    app.number_input[0].set_value(100)
    _button(app, "开始推荐").click().run(timeout=30)

    assert not app.exception
    assert any("没有满足全部明确条件" in str(message.value) for message in app.error)
    assert not [button for button in app.button if button.label == "生成定制需求单"]
    _button(app, "生成定制方案").click().run(timeout=30)
    assert not app.exception
    assert any("不代表现有产品" in str(item.value) for item in app.warning)


def test_complete_conversation_auto_recommends_and_preserves_history() -> None:
    app = _open_advisor()
    app.chat_input[0].set_value(
        "企业给30位美国合作伙伴准备周年礼物，每件预算1000元，"
        "需要加公司Logo，30天内完成，需要中英文介绍。"
    ).run(timeout=30)

    assert not app.exception
    assert "recommendation_response" in app.session_state
    assert app.session_state["gift_request"].quantity == 30
    assert app.session_state["gift_request"].logo_required is True
    state = app.session_state["conversation_state"]
    assert len(state.messages) == 2
    app.run(timeout=30)
    assert len(app.session_state["conversation_state"].messages) == 2


def test_incomplete_conversation_asks_one_question_then_merges_answer() -> None:
    app = _open_advisor()
    app.chat_input[0].set_value("送给合作伙伴，用于周年纪念").run(timeout=30)

    assert not app.exception
    assert "recommendation_response" in app.session_state
    assert app.session_state["recommendation_response"].recommendations
    state = app.session_state["conversation_state"]
    assert state.clarification_rounds == 1
    assert len(state.clarification_questions) == 1
    assert state.information_coverage > 0

    app.chat_input[0].set_value("30件，每件预算1000元").run(timeout=30)
    assert not app.exception
    assert "recommendation_response" in app.session_state
    assert app.session_state["gift_request"].quantity == 30


def test_restart_clears_conversation_and_recommendation() -> None:
    app = _open_advisor()
    app.chat_input[0].set_value("送给30位合作伙伴的周年礼物，每件预算1000元").run(timeout=30)
    assert "recommendation_response" in app.session_state

    _button(app, "重新开始").click().run(timeout=30)
    assert not app.exception
    assert not app.session_state["conversation_state"].messages
    assert "recommendation_response" not in app.session_state


def test_conversation_can_switch_back_to_detailed_form() -> None:
    app = _open_advisor()
    _button(app, "切换详细表单").click().run(timeout=30)
    assert not app.exception
    assert app.radio[0].value == "详细表单"
    _button(app, "开始推荐").click().run(timeout=30)
    assert "recommendation_response" in app.session_state
