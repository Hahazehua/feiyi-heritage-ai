"""A teleprompter for whoever is driving the five-minute demo.

The competition mode used to be a progress strip: it named the stage you were
in but never the click that would get you out of it, and it only advanced from
three places, so a presenter who wandered off the path was stranded.

This turns it into something a teammate who has not used the product can follow
live — the next action spelled out, manual navigation so nobody gets stuck, and
a time budget per step.  The talking points stay collapsed on purpose: judges
can see the screen, and a visible script reads as a crib sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from heritagelink.i18n import t


@dataclass(frozen=True, slots=True)
class TourStep:
    key: str
    seconds: int
    # Two of the five carry the differentiation. Presenters need to know where
    # to slow down, or they spend equal time on the parts that are table stakes.
    pivotal: bool = False

    @property
    def title(self) -> str:
        return t(f"demo.{self.key}")

    @property
    def action(self) -> str:
        return t(f"demo.{self.key}.action")

    @property
    def script(self) -> str:
        return t(f"demo.{self.key}.script")


TOUR_STEPS: tuple[TourStep, ...] = (
    TourStep("discover", 60),
    TourStep("recommend", 75, pivotal=True),
    TourStep("artisan", 45),
    TourStep("growth", 90, pivotal=True),
    TourStep("guardian", 60),
)
TOTAL_SECONDS = sum(step.seconds for step in TOUR_STEPS)


def clamp_step(step: int) -> int:
    return max(1, min(step, len(TOUR_STEPS)))


def render_demo_tour(step: int) -> int | None:
    """Render the tour and return the step to move to, or None to stay."""
    current = clamp_step(step)
    active = TOUR_STEPS[current - 1]

    st.markdown(_header_markup(current, active), unsafe_allow_html=True)

    with st.expander(t("demo.script_label")):
        st.write(active.script)

    back, forward, restart = st.columns([1, 1, 1])
    if back.button(
        t("demo.prev"),
        key="demo_tour_prev",
        width="stretch",
        disabled=current == 1,
    ):
        return current - 1
    if forward.button(
        t("demo.next"),
        key="demo_tour_next",
        type="primary",
        width="stretch",
        disabled=current == len(TOUR_STEPS),
    ):
        return current + 1
    if restart.button(t("demo.restart"), key="demo_tour_restart", width="stretch"):
        return 1
    return None


def _header_markup(current: int, active: TourStep) -> str:
    items = "".join(
        '<li class="hl-demo-step '
        + ("active" if index == current else "done" if index < current else "")
        + (" pivotal" if step.pivotal else "")
        + '"'
        + (' aria-current="step"' if index == current else "")
        + '><span aria-hidden="true">'
        + str(index)
        + "</span><strong>"
        + escape(step.title)
        + "</strong></li>"
        for index, step in enumerate(TOUR_STEPS, start=1)
    )
    progress = t("demo.step", current=current, total=len(TOUR_STEPS))
    budget = t("demo.budget", seconds=active.seconds)
    total = t("demo.total", minutes=TOTAL_SECONDS // 60, seconds=TOTAL_SECONDS % 60)
    pivotal_mark = (
        f'<span class="hl-demo-pivotal">{escape(t("demo.pivotal"))}</span>'
        if active.pivotal
        else ""
    )
    return (
        f'<nav class="hl-demo-guide" aria-label="{escape(t("demo.tour_title"))}">'
        '<div class="hl-demo-guide-title">'
        f"<span>{escape(t('demo.tour_title'))}</span>"
        f"<span>{escape(progress)} · {escape(budget)} · {escape(total)}</span>"
        "</div>"
        f'<ol class="hl-demo-steps">{items}</ol>'
        '<div class="hl-demo-now">'
        f'<span class="hl-demo-now-label">{escape(t("demo.now_label"))}{pivotal_mark}</span>'
        f"<p>{escape(active.action)}</p>"
        "</div>"
        "</nav>"
    )


__all__ = ["TOTAL_SECONDS", "TOUR_STEPS", "TourStep", "clamp_step", "render_demo_tour"]
