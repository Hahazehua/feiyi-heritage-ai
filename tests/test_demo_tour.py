"""The presenter-facing demo tour."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from heritagelink.i18n import Language, set_language
from heritagelink.i18n.en_US import TRANSLATIONS as EN
from heritagelink.i18n.zh_CN import TRANSLATIONS as ZH
from heritagelink.ui import demo_tour


def _demo_app() -> AppTest:
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "buyer"
    app.query_params["demo"] = "1"
    return app


def test_every_step_tells_the_presenter_what_to_click() -> None:
    """A stage name is not an instruction.

    The strip this replaced named the stage and left a teammate who had never
    used the product with nothing to act on.
    """
    for step in demo_tour.TOUR_STEPS:
        for catalogue in (ZH, EN):
            assert catalogue[f"demo.{step.key}.action"].strip()
            assert catalogue[f"demo.{step.key}.script"].strip()


def test_the_tour_fits_the_five_minute_slot() -> None:
    assert 240 <= demo_tour.TOTAL_SECONDS <= 360, "a five-minute demo, give or take"
    assert all(step.seconds > 0 for step in demo_tour.TOUR_STEPS)


def test_the_two_differentiating_steps_are_marked() -> None:
    """Presenters spend equal time everywhere unless told where to linger."""
    pivotal = [step.key for step in demo_tour.TOUR_STEPS if step.pivotal]

    assert pivotal == ["recommend", "growth"]


def test_navigation_is_clamped_to_the_real_steps() -> None:
    assert demo_tour.clamp_step(0) == 1
    assert demo_tour.clamp_step(99) == len(demo_tour.TOUR_STEPS)
    assert demo_tour.clamp_step(3) == 3


def test_the_tour_appears_only_in_demo_mode() -> None:
    plain = AppTest.from_file("app.py")
    plain.query_params["mode"] = "buyer"
    plain.run(timeout=30)

    assert not any(button.label == "下一步 ▸" for button in plain.button)

    demo = _demo_app().run(timeout=30)

    assert not demo.exception
    assert any(button.label == "下一步 ▸" for button in demo.button)


def test_the_presenter_can_walk_forward_and_back() -> None:
    """Auto-advance fires from three places; a presenter who steps off the
    path needs a way back that does not depend on it."""
    app = _demo_app().run(timeout=30)
    assert app.session_state["competition_demo_step"] == 1

    [b for b in app.button if b.label == "下一步 ▸"][0].click().run(timeout=30)
    assert app.session_state["competition_demo_step"] == 2

    [b for b in app.button if b.label == "◂ 上一步"][0].click().run(timeout=30)
    assert app.session_state["competition_demo_step"] == 1


def test_restart_returns_to_the_opening_step() -> None:
    app = _demo_app().run(timeout=30)
    [b for b in app.button if b.label == "下一步 ▸"][0].click().run(timeout=30)
    [b for b in app.button if b.label == "↺ 重新开始"][0].click().run(timeout=30)

    assert app.session_state["competition_demo_step"] == 1


def test_talking_points_stay_collapsed() -> None:
    """Judges can see the screen; an open script reads as a crib sheet."""
    app = _demo_app().run(timeout=30)
    scripts = [item for item in app.expander if item.label == "讲解要点"]

    assert scripts, "the talking points need somewhere to live"
    assert not scripts[0].proto.expanded


def test_tour_copy_is_bilingual() -> None:
    set_language(Language.EN_US, {})
    try:
        keys = [
            f"demo.{step.key}.{part}"
            for step in demo_tour.TOUR_STEPS
            for part in ("action", "script")
        ]
        for key in [*keys, "demo.now_label", "demo.script_label", "demo.pivotal"]:
            assert ZH[key] != EN[key], f"{key} was never translated"
    finally:
        set_language(Language.ZH_CN, {})
