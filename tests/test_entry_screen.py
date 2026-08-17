"""The entry chooser and the role isolation it establishes."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _fresh_app() -> AppTest:
    """A first-time visitor: no deep link, no prior choice."""
    return AppTest.from_file("app.py")


def _labels(app: AppTest) -> set[str]:
    return {button.label for button in app.button}


def test_first_visit_asks_for_a_role_before_showing_either_side() -> None:
    app = _fresh_app().run(timeout=30)

    assert not app.exception
    assert app.session_state["entry_role"] is None
    assert {"进入买家端", "进入手艺人端"}.issubset(_labels(app))
    # Neither product surface may leak before the choice is made.
    assert not app.chat_input


def test_choosing_buyer_enters_the_buyer_side_and_records_the_choice() -> None:
    app = _fresh_app().run(timeout=30)
    [button for button in app.button if button.label == "进入买家端"][0].click().run(timeout=30)

    assert not app.exception
    assert app.session_state["entry_role"] == "buyer"
    assert app.session_state["app_mode"] == "buyer"
    assert app.chat_input


def test_choosing_artisan_enters_the_artisan_side() -> None:
    app = _fresh_app().run(timeout=30)
    [button for button in app.button if button.label == "进入手艺人端"][0].click().run(timeout=30)

    assert not app.exception
    assert app.session_state["entry_role"] == "artisan"
    assert app.session_state["app_mode"] == "artisan"


def test_mode_deep_link_skips_the_chooser() -> None:
    """Reviewers and the demo script arrive by URL and must not be stopped."""
    for mode in ("buyer", "artisan"):
        app = AppTest.from_file("app.py")
        app.query_params["mode"] = mode
        app.run(timeout=30)

        assert not app.exception
        assert app.session_state["entry_role"] == mode
        assert "进入买家端" not in _labels(app)


def test_footer_switch_returns_to_the_chooser() -> None:
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "artisan"
    app.run(timeout=30)
    [button for button in app.button if button.label == "切换身份"][0].click().run(timeout=30)

    assert not app.exception
    assert app.session_state["entry_role"] is None
    assert {"进入买家端", "进入手艺人端"}.issubset(_labels(app))
    # The deep link has to be cleared too, or the next rerun re-enters at once.
    assert "mode" not in app.query_params


def test_losing_the_mode_parameter_returns_to_the_chooser() -> None:
    """This is browser Back.

    Back rewrites the URL without telling the server, so the only signal the
    next rerun gets is the missing parameter. When session state decided which
    side to render, the address bar moved and the page did not.
    """
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "artisan"
    app.run(timeout=30)
    assert app.session_state["entry_role"] == "artisan"

    del app.query_params["mode"]
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["entry_role"] is None
    assert {"进入买家端", "进入手艺人端"}.issubset(_labels(app))


def test_leaving_the_about_page_restores_the_role_behind_it() -> None:
    """Back out of About and the side you were reading it from is still there."""
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "artisan"
    app.query_params["page"] = "about"
    app.run(timeout=30)
    assert app.session_state["app_page"] == "about"

    del app.query_params["page"]
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["app_page"] == "artisan"
    assert app.session_state["entry_role"] == "artisan"


def test_each_side_hides_the_other_sides_entry() -> None:
    buyer = AppTest.from_file("app.py")
    buyer.query_params["mode"] = "buyer"
    buyer.run(timeout=30)

    artisan = AppTest.from_file("app.py")
    artisan.query_params["mode"] = "artisan"
    artisan.run(timeout=30)

    assert "我是手艺人" not in _labels(buyer)
    assert "我是买家" not in _labels(artisan)
    # Only the footer offers a way across.
    assert "切换身份" in _labels(buyer)
    assert "切换身份" in _labels(artisan)
