"""Streamlit intake and review UI for artisan oral-history sources."""

from __future__ import annotations

from html import escape

import streamlit as st

from heritagelink.growth_models import GrowthProductContext
from heritagelink.i18n import t
from heritagelink.oral_story_models import (
    OralClaimCategory,
    OralClaimStatus,
    OralSourceKind,
    OralStorySession,
    OralStoryStatus,
)
from heritagelink.oral_story_service import (
    confirm_publishable_oral_claims,
    create_oral_story_session,
    create_project_from_oral_story,
    export_oral_story_session,
    media_sha256,
    review_oral_story_claims,
)
from heritagelink.ui.system import render_metric_strip

_CATEGORY_KEYS = {category: f"oral.category.{category.value}" for category in OralClaimCategory}
_STATUS_KEYS = {status: f"oral.claim_status.{status.value}" for status in OralClaimStatus}


def render_oral_story_studio(context: GrowthProductContext) -> None:
    """Render transcript intake and hand an approved source to Story Studio."""
    st.markdown(f"## {t('oral.title')}")
    st.caption(t("oral.subtitle"))
    with st.form("oral_story_intake", border=True):
        media = st.file_uploader(
            t("oral.media"),
            type=("mp3", "wav", "m4a", "mp4", "mov", "webm"),
            help=t("oral.media_help"),
            key="oral_story_media",
        )
        transcript = st.text_area(
            t("oral.transcript"),
            placeholder=t("oral.transcript_placeholder"),
            height=190,
            key="oral_story_transcript",
        )
        st.caption(t("oral.timestamp_hint"))
        submitted = st.form_submit_button(t("oral.extract"), type="primary")

    if submitted:
        if not transcript.strip():
            st.info(t("oral.transcript_required"))
        else:
            source_kind = OralSourceKind.PASTED_TEXT
            source_name = "pasted-transcript.txt"
            source_hash = None
            if media is not None:
                payload = media.getvalue()
                source_hash = media_sha256(payload)
                source_name = media.name
                suffix = media.name.rsplit(".", 1)[-1].casefold()
                source_kind = (
                    OralSourceKind.VIDEO
                    if (media.type or "").startswith("video/") or suffix in {"mp4", "mov", "webm"}
                    else OralSourceKind.AUDIO
                )
            try:
                session = create_oral_story_session(
                    context,
                    transcript,
                    source_kind=source_kind,
                    source_name=source_name,
                    media_sha256=source_hash,
                )
            except ValueError as exc:
                st.info(str(exc))
            else:
                _clear_review_widget_state(session.session_id)
                st.session_state["oral_story_session"] = session
                st.session_state["oral_story_context_id"] = context.product_id
                st.session_state["story_project"] = None
                st.session_state["story_visual_package"] = None
                st.rerun()

    session = st.session_state.get("oral_story_session")
    session_context_id = st.session_state.get("oral_story_context_id")
    if not isinstance(session, OralStorySession) or session_context_id != context.product_id:
        st.info(t("oral.empty"))
        return
    _render_oral_review(context, session)


def _render_oral_review(context: GrowthProductContext, session: OralStorySession) -> None:
    st.markdown(f"### {t('oral.review_title')}")
    render_metric_strip(
        (
            (t("oral.metric.segments"), str(len(session.segments)), session.source_name),
            (t("oral.metric.claims"), str(len(session.claims)), None),
            (t("oral.metric.confirmed"), str(session.confirmed_count), None),
            (t("oral.metric.blocked"), str(session.blocked_count), t("oral.needs_evidence")),
        )
    )
    st.warning(t("oral.risk_notice"))

    if st.button(
        t("oral.confirm_publishable"),
        key=f"oral_confirm_publishable_{session.session_id}",
        type="primary",
    ):
        _clear_review_widget_state(session.session_id)
        st.session_state["oral_story_session"] = confirm_publishable_oral_claims(
            session,
            actor_id=context.artisan_id,
        )
        st.rerun()

    decisions: dict[str, OralClaimStatus] = {}
    edits: dict[str, str] = {}
    with st.form(f"oral_claim_review_{session.session_id}", border=True):
        for claim in session.claims:
            st.markdown(
                f"**{escape(t(_CATEGORY_KEYS[claim.category]))} · {escape(claim.source_locator)}**"
            )
            st.caption(f"{t('oral.source_quote')}：{claim.source_quote}")
            edits[claim.claim_id] = st.text_area(
                t("oral.public_statement"),
                value=claim.statement,
                height=76,
                key=f"oral_statement_{session.session_id}_{claim.claim_id}",
                label_visibility="collapsed",
            )
            options = (
                (OralClaimStatus.NEEDS_EVIDENCE, OralClaimStatus.EXCLUDED)
                if claim.requires_external_evidence
                else (
                    OralClaimStatus.PENDING,
                    OralClaimStatus.CONFIRMED,
                    OralClaimStatus.EXCLUDED,
                )
            )
            current = claim.status if claim.status in options else options[0]
            decisions[claim.claim_id] = st.selectbox(
                t("oral.decision"),
                options,
                index=options.index(current),
                format_func=lambda value: t(_STATUS_KEYS[value]),
                key=f"oral_decision_{session.session_id}_{claim.claim_id}",
            )
            st.divider()
        save = st.form_submit_button(t("oral.save_review"))
    if save:
        try:
            reviewed = review_oral_story_claims(
                session,
                decisions,
                actor_id=context.artisan_id,
                edited_statements=edits,
            )
        except ValueError as exc:
            st.info(str(exc))
        else:
            st.session_state["oral_story_session"] = reviewed
            st.rerun()

    st.download_button(
        t("oral.export_source"),
        data=export_oral_story_session(session),
        file_name=f"{session.session_id}.json",
        mime="application/json",
        key=f"oral_export_{session.session_id}",
    )

    if session.status is not OralStoryStatus.READY_FOR_SCRIPT:
        st.info(t("oral.ready_gate"))
        return
    st.success(t("oral.ready"))
    language = st.selectbox(
        t("story.output_language"),
        ("Chinese", "English"),
        format_func=lambda value: t(f"story.language.{value.casefold()}"),
        key="oral_story_language",
    )
    st.caption(t("oral.language_note"))
    if st.button(t("oral.generate_script"), type="primary", key="oral_generate_script"):
        try:
            project = create_project_from_oral_story(context, session, language=language)
        except ValueError as exc:
            st.info(str(exc))
            return
        st.session_state["story_project"] = project
        st.session_state["story_context_id"] = context.product_id
        st.session_state["story_visual_package"] = None
        st.rerun()


def _clear_review_widget_state(session_id: str) -> None:
    prefixes = (
        f"oral_statement_{session_id}_",
        f"oral_decision_{session_id}_",
    )
    for key in tuple(st.session_state):
        if str(key).startswith(prefixes):
            del st.session_state[key]


__all__ = ["render_oral_story_studio"]
