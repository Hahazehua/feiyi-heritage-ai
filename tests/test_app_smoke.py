from streamlit.testing.v1 import AppTest


def test_app_submits_request_and_generates_inquiry() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)

    assert not app.exception
    assert any("仅用于MVP演示" in str(message.value) for message in app.error)

    app.button[0].click().run(timeout=30)

    assert not app.exception
    assert any("找到 3 件" in str(message.value) for message in app.success)
    assert len([button for button in app.button if button.label == "生成定制需求单"]) == 3

    app.button[1].click().run(timeout=30)

    assert not app.exception
    assert any("结构化定制需求单" in str(message.value) for message in app.success)
    assert app.json
    assert app.get("download_button")


def test_app_does_not_force_recommendation_when_budget_is_too_low() -> None:
    app = AppTest.from_file("app.py").run(timeout=30)
    app.number_input[0].set_value(100)
    app.button[0].click().run(timeout=30)

    assert not app.exception
    assert any("没有合格产品" in str(message.value) for message in app.error)
    assert not [button for button in app.button if button.label == "生成定制需求单"]
