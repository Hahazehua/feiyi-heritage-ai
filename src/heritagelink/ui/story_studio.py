"""Streamlit presentation for HAHA Story Studio script and visual production."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from html import escape
from pathlib import Path

import streamlit as st

from heritagelink.growth_models import GrowthProductContext
from heritagelink.i18n import Language, get_language, t
from heritagelink.image_providers import (
    DemoImageProvider,
    ImageProvider,
    MissingImageAPIKeyError,
    image_provider_for,
    openai_image_is_configured,
)
from heritagelink.story_distribution_service import (
    build_distribution_package,
    export_distribution_package_zip,
)
from heritagelink.story_models import (
    NarrativeTemplate,
    StoryDecision,
    StoryPlatform,
    StoryProject,
    StoryProjectStatus,
)
from heritagelink.story_service import create_story_project, decide_story_project
from heritagelink.story_visual_models import (
    StoryVisualPackage,
    VisualPackageStatus,
    VisualReference,
    VisualReferenceKind,
)
from heritagelink.story_visual_service import (
    StoryMediaStorage,
    add_uploaded_scene_variant,
    approve_selected_scene_variant,
    build_visual_bible,
    create_visual_package,
    export_visual_package_zip,
    generate_missing_scene_variants,
    generate_scene_variant,
    select_scene_variant,
)
from heritagelink.ui.system import render_demo_badge, render_metric_strip, render_status_badge

_TEMPLATE_KEYS = {
    NarrativeTemplate.OBJECT_RECORD: "story.template.object_record",
    NarrativeTemplate.ARTISAN_LIFE: "story.template.artisan_life",
    NarrativeTemplate.TIME_DIALOGUE: "story.template.time_dialogue",
}
_STATUS_KEYS = {
    StoryProjectStatus.DRAFT: "story.status.draft",
    StoryProjectStatus.AWAITING_HUMAN_APPROVAL: "story.status.awaiting",
    StoryProjectStatus.NEEDS_REVISION: "story.status.revision",
    StoryProjectStatus.APPROVED: "story.status.approved",
    StoryProjectStatus.REJECTED: "story.status.rejected",
}
_DISTRIBUTION_PLATFORM_KEYS = {
    StoryPlatform.XIAOHONGSHU: "story.distribution.platform.xiaohongshu",
    StoryPlatform.TIKTOK: "story.distribution.platform.tiktok",
    StoryPlatform.INSTAGRAM_REELS: "story.distribution.platform.instagram_reels",
    StoryPlatform.YOUTUBE_SHORTS: "story.distribution.platform.youtube_shorts",
}
_VISUAL_STATUS_KEYS = {
    VisualPackageStatus.DRAFT: "story.visual.status.draft",
    VisualPackageStatus.IN_PROGRESS: "story.visual.status.progress",
    VisualPackageStatus.NEEDS_ATTENTION: "story.visual.status.attention",
    VisualPackageStatus.AWAITING_APPROVAL: "story.visual.status.awaiting",
    VisualPackageStatus.APPROVED: "story.visual.status.approved",
}
_REFERENCE_KINDS = (
    (VisualReferenceKind.ARTISAN, "story.visual.reference.artisan"),
    (VisualReferenceKind.PRODUCT, "story.visual.reference.product"),
    (VisualReferenceKind.WORKSHOP, "story.visual.reference.workshop"),
)
_DEFAULT_MEDIA_ROOT = Path(__file__).resolve().parents[3] / ".local" / "story-media"


def render_story_hero() -> None:
    st.markdown(
        f"""
        <section class="hl-hero hl-growth-hero">
          <div class="hl-eyebrow">{escape(t("story.eyebrow"))}</div>
          <h1 class="hl-brand">{escape(t("story.title"))}</h1>
          <p class="hl-copy">{escape(t("story.subtitle"))}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    render_demo_badge()
    st.caption(t("story.phase_note"))


def render_story_studio_app(contexts: Mapping[str, GrowthProductContext]) -> None:
    """Render product selection, generation, evidence review, and human approval."""
    render_story_hero()
    if not contexts:
        st.info(t("story.no_products"))
        return

    product_ids = tuple(contexts)
    selected_id = st.selectbox(
        t("story.select_product"),
        product_ids,
        format_func=lambda value: _product_label(contexts[value]),
        key="story_selected_product_id",
    )
    context = contexts[selected_id]
    _render_context_boundary(context)
    _render_generator(context)

    project = st.session_state.get("story_project")
    project_context_id = st.session_state.get("story_context_id")
    if isinstance(project, StoryProject) and project_context_id == context.product_id:
        _render_project(project, context)


def _render_context_boundary(context: GrowthProductContext) -> None:
    render_metric_strip(
        (
            (t("story.verified_facts"), str(len(context.verified_facts)), None),
            (t("story.pending_facts"), str(len(context.unverified_facts)), t("story.not_public")),
            (t("story.unknown_facts"), str(len(context.unknown_fields)), t("story.not_public")),
        )
    )
    if context.requires_draft_label:
        st.warning(t("story.draft_warning"))


def _render_generator(context: GrowthProductContext) -> None:
    with st.form("story_generation_form", border=True):
        st.markdown(f"### {t('story.generator_title')}")
        template = st.selectbox(
            t("story.template"),
            tuple(NarrativeTemplate),
            format_func=lambda value: t(_TEMPLATE_KEYS[value]),
        )
        language = st.selectbox(
            t("story.output_language"),
            ("Chinese", "English"),
            format_func=lambda value: t(f"story.language.{value.casefold()}"),
        )
        submitted = st.form_submit_button(t("story.generate"), type="primary")
    if not submitted:
        return
    try:
        project = create_story_project(context, template, language)
    except ValueError as exc:
        st.error(f"{t('story.generation_blocked')} {exc}")
        return
    st.session_state["story_project"] = project
    st.session_state["story_context_id"] = context.product_id
    st.session_state["story_visual_package"] = None
    st.rerun()


def _render_project(project: StoryProject, context: GrowthProductContext) -> None:
    script = project.script
    st.divider()
    st.markdown(f"## {escape(script.title)}")
    render_status_badge(project.status, label=t(_STATUS_KEYS[project.status]))
    render_metric_strip(
        (
            (
                t("story.platform"),
                t("story.distribution.platform.xiaohongshu"),
                script.aspect_ratio,
            ),
            (t("story.duration"), f"{script.total_duration_seconds}s", None),
            (t("story.scenes"), str(len(script.scenes)), None),
            (t("story.fact_refs"), str(len(script.fact_references)), None),
        )
    )
    st.markdown(f"### {t('story.storyboard')}")
    references = script.fact_references_by_id
    for scene in script.scenes:
        label = t(
            "story.scene_label",
            sequence=scene.sequence,
            title=scene.title,
            seconds=scene.duration_seconds,
        )
        with st.expander(label, expanded=scene.sequence == 1):
            st.markdown(f"**{t('story.voiceover')}**  \n{escape(scene.voiceover)}")
            st.markdown(f"**{t('story.on_screen')}**  \n{escape(scene.on_screen_text)}")
            st.markdown(f"**{t('story.visual')}**  \n{escape(scene.visual_description)}")
            st.markdown(f"**{t('story.camera')}**  \n{escape(scene.camera_direction)}")
            if scene.fact_reference_ids:
                st.markdown(f"**{t('story.evidence')}**")
                for reference_id in scene.fact_reference_ids:
                    reference = references[reference_id]
                    source = (
                        f"[{escape(reference.source_note)}]({reference.source_url})"
                        if reference.source_url
                        else escape(reference.source_note)
                    )
                    st.markdown(
                        f"- `{reference.reference_id}` · {escape(reference.field_name)}: "
                        f"{escape(reference.display_value)} · {source}"
                    )
            else:
                st.caption(t("story.artistic_scene"))
            st.markdown(f"**{t('story.provider_prompts')}**")
            st.code(scene.image_prompt, language="text")
            st.code(scene.video_prompt, language="text")

    _render_guardian(project)
    _render_decision(project, context)
    st.download_button(
        t("story.export_json"),
        data=_export_json(project),
        file_name=f"{project.project_id}.json",
        mime="application/json",
        key="story_export_json",
    )
    _render_distribution_stage(project)
    _render_visual_stage(project, context)


def _render_guardian(project: StoryProject) -> None:
    review = project.guardian_review
    st.markdown(f"### {t('story.guardian_title')}")
    if review.approved:
        st.success(t("story.guardian_passed", count=len(review.verified_reference_ids)))
    else:
        st.error(t("story.guardian_failed", count=len(review.issues)))
        for issue in review.issues:
            st.markdown(
                f"- **{escape(issue.scene_id)} · {escape(issue.issue_type)}**: "
                f"{escape(issue.reason)} — {escape(issue.recommended_action)}"
            )


def _render_decision(project: StoryProject, context: GrowthProductContext) -> None:
    st.markdown(f"### {t('story.human_review_title')}")
    if project.status is StoryProjectStatus.APPROVED:
        st.success(t("story.human_approved"))
        return
    if project.status is StoryProjectStatus.REJECTED:
        st.error(t("story.human_rejected"))
        return
    note = st.text_area(t("story.decision_note"), key="story_decision_note")
    approve_column, revise_column, reject_column = st.columns(3)
    approve_disabled = project.status is not StoryProjectStatus.AWAITING_HUMAN_APPROVAL
    if approve_column.button(
        t("story.approve"),
        type="primary",
        disabled=approve_disabled,
        key="story_approve",
        width="stretch",
    ):
        _apply_decision(project, StoryDecision.APPROVE, context.artisan_id, note)
    if revise_column.button(
        t("story.request_revision"),
        key="story_request_revision",
        width="stretch",
    ):
        _apply_decision(project, StoryDecision.REQUEST_REVISION, context.artisan_id, note)
    if reject_column.button(
        t("story.reject"),
        key="story_reject",
        width="stretch",
    ):
        _apply_decision(project, StoryDecision.REJECT, context.artisan_id, note)


def _apply_decision(
    project: StoryProject,
    decision: StoryDecision,
    actor_id: str,
    note: str,
) -> None:
    try:
        st.session_state["story_project"] = decide_story_project(
            project,
            decision,
            actor_id,
            note,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    st.rerun()


def _render_distribution_stage(project: StoryProject) -> None:
    st.divider()
    st.markdown(f"## {t('story.distribution.title')}")
    st.caption(t("story.distribution.subtitle"))
    if project.status is not StoryProjectStatus.APPROVED:
        st.info(t("story.distribution.approval_gate"))
        return

    package = build_distribution_package(project, now=project.updated_at)
    render_metric_strip(
        (
            (t("story.distribution.platforms"), str(len(package.assets)), "9:16"),
            (
                t("story.distribution.source_approval"),
                package.approved_by,
                package.approved_at.strftime("%Y-%m-%d"),
            ),
            (
                t("story.fact_refs"),
                str(len(package.fact_reference_ids)),
                t("story.distribution.fact_safe"),
            ),
        )
    )
    selected_platform = st.selectbox(
        t("story.distribution.preview"),
        tuple(_DISTRIBUTION_PLATFORM_KEYS),
        format_func=lambda value: t(_DISTRIBUTION_PLATFORM_KEYS[value]),
        key="story_distribution_platform",
    )
    asset = package.assets_by_platform[selected_platform]
    st.markdown(f"### {escape(asset.platform_label)}")
    st.markdown(f"**{t('story.distribution.post_title')}**  \n{escape(asset.title)}")
    st.markdown(f"**{t('story.distribution.hook')}**  \n{escape(asset.hook)}")
    st.markdown(f"**{t('story.distribution.caption')}**")
    st.code(asset.caption, language="text")
    st.markdown(f"**{t('story.distribution.cta')}**  \n{escape(asset.call_to_action)}")
    st.markdown(f"**{t('story.distribution.hashtags')}**  \n{escape(asset.hashtag_line)}")
    st.success(t("story.distribution.package_ready"))
    st.download_button(
        t("story.distribution.export_zip"),
        data=export_distribution_package_zip(package),
        file_name=f"{package.package_id}.zip",
        mime="application/zip",
        key="story_distribution_export_zip",
    )


def _render_visual_stage(project: StoryProject, context: GrowthProductContext) -> None:
    st.divider()
    st.markdown(f"## {t('story.visual.title')}")
    st.caption(t("story.visual.subtitle"))
    if project.status is not StoryProjectStatus.APPROVED:
        st.info(t("story.visual.approval_gate"))
        return

    package = st.session_state.get("story_visual_package")
    if (
        not isinstance(package, StoryVisualPackage)
        or package.story_project_id != project.project_id
    ):
        _render_visual_setup(project)
        return
    _render_visual_workspace(project, context, package)


def _render_visual_setup(project: StoryProject) -> None:
    st.markdown(f"### {t('story.visual.bible_title')}")
    with st.form("story_visual_bible_form", border=True):
        style = st.text_input(
            t("story.visual.style"),
            value=t("story.visual.style_default"),
        )
        palette = st.text_input(
            t("story.visual.palette"),
            value=t("story.visual.palette_default"),
        )
        lighting = st.text_input(
            t("story.visual.lighting"),
            value=t("story.visual.lighting_default"),
        )
        wardrobe = st.text_input(
            t("story.visual.wardrobe"),
            value=t("story.visual.wardrobe_default"),
        )
        prohibited = st.text_area(
            t("story.visual.prohibited"),
            value=t("story.visual.prohibited_default"),
        )
        source_note = st.text_input(
            t("story.visual.reference_source"),
            value=t("story.visual.reference_source_default"),
        )
        uploads: dict[VisualReferenceKind, list[object]] = {}
        for kind, label_key in _REFERENCE_KINDS:
            uploads[kind] = list(
                st.file_uploader(
                    t(label_key),
                    type=("png", "jpg", "jpeg", "webp"),
                    accept_multiple_files=True,
                    key=f"story_visual_reference_{kind.value}",
                )
                or ()
            )
        rights_confirmed = st.checkbox(t("story.visual.rights_confirm"))
        submitted = st.form_submit_button(t("story.visual.save_bible"), type="primary")
    if not submitted:
        return

    has_uploads = any(uploads.values())
    if has_uploads and not rights_confirmed:
        st.error(t("story.visual.rights_required"))
        return
    storage = _story_storage()
    try:
        references = _save_visual_references(
            project,
            storage,
            uploads,
            source_note,
        )
        bible = build_visual_bible(
            project,
            style=style,
            palette=palette,
            lighting=lighting,
            wardrobe=wardrobe,
            prohibited_elements=_split_guidance(prohibited),
            references=references,
            rights_confirmed=rights_confirmed,
        )
        package = create_visual_package(project, bible)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.session_state["story_visual_package"] = package
    st.rerun()


def _render_visual_workspace(
    project: StoryProject,
    context: GrowthProductContext,
    package: StoryVisualPackage,
) -> None:
    render_status_badge(package.status, label=t(_VISUAL_STATUS_KEYS[package.status]))
    render_metric_strip(
        (
            (t("story.visual.generated"), str(package.selected_count), f"/{len(package.scenes)}"),
            (t("story.visual.approved"), str(package.approved_count), f"/{len(package.scenes)}"),
            (
                t("story.visual.references"),
                str(len(package.visual_bible.references)),
                t("story.visual.rights_ok")
                if package.visual_bible.rights_confirmed
                else t("story.visual.no_references"),
            ),
        )
    )
    if package.visual_bible.references:
        st.caption(
            t(
                "story.visual.references_ready",
                count=len(package.visual_bible.references),
            )
        )
    if st.button(t("story.visual.reset_bible"), key="story_visual_reset_bible"):
        st.session_state["story_visual_package"] = None
        st.rerun()

    provider_mode = st.selectbox(
        t("story.visual.provider"),
        ("demo", "openai"),
        format_func=lambda value: t(f"story.visual.provider.{value}"),
        key="story_visual_provider_mode",
    )
    if provider_mode == "openai" and not openai_image_is_configured():
        st.warning(t("story.visual.openai_fallback"))
    provider = _resolve_provider(provider_mode)
    if st.button(
        t("story.visual.generate_missing"),
        type="primary",
        key="story_visual_generate_missing",
    ):
        with st.spinner(t("story.visual.generating")):
            updated = generate_missing_scene_variants(
                project,
                package,
                provider,
                _story_storage(),
            )
        st.session_state["story_visual_package"] = updated
        st.rerun()

    _render_contact_sheet(project, package)
    updated_package = _render_scene_image_controls(project, context, package, provider)
    if updated_package is not package:
        st.session_state["story_visual_package"] = updated_package

    package = updated_package
    can_approve_all = package.selected_count == len(
        package.scenes
    ) and package.approved_count < len(package.scenes)
    if st.button(
        t("story.visual.approve_all"),
        key="story_visual_approve_all",
        type="primary",
        disabled=not can_approve_all,
    ):
        approved = package
        for scene_state in approved.scenes:
            approved = approve_selected_scene_variant(
                approved,
                scene_state.scene_id,
                context.artisan_id,
            )
        st.session_state["story_visual_package"] = approved
        st.rerun()

    if package.status is VisualPackageStatus.APPROVED:
        st.success(t("story.visual.package_ready"))
        archive = export_visual_package_zip(project, package, _story_storage())
        st.download_button(
            t("story.visual.export_zip"),
            data=archive,
            file_name=f"{package.package_id}.zip",
            mime="application/zip",
            key="story_visual_export_zip",
        )


def _render_contact_sheet(project: StoryProject, package: StoryVisualPackage) -> None:
    if not package.selected_count:
        return
    st.markdown(f"### {t('story.visual.contact_sheet')}")
    columns = st.columns(3)
    for index, scene in enumerate(project.script.scenes):
        artifact = package.scenes_by_id[scene.scene_id].selected_artifact
        if artifact is None:
            continue
        with columns[index % 3]:
            st.image(artifact.local_path, caption=f"{scene.sequence}. {scene.title}")


def _render_scene_image_controls(
    project: StoryProject,
    context: GrowthProductContext,
    package: StoryVisualPackage,
    provider: ImageProvider,
) -> StoryVisualPackage:
    updated = package
    st.markdown(f"### {t('story.visual.variants_title')}")
    for scene in project.script.scenes:
        scene_state = updated.scenes_by_id[scene.scene_id]
        with st.expander(
            t("story.visual.scene", sequence=scene.sequence, title=scene.title),
            expanded=bool(scene_state.last_error),
        ):
            if scene_state.last_error:
                st.error(scene_state.last_error)
            if scene_state.variants:
                selected_id = st.selectbox(
                    t("story.visual.choose_variant"),
                    tuple(artifact.artifact_id for artifact in scene_state.variants),
                    index=max(
                        0,
                        next(
                            (
                                index
                                for index, artifact in enumerate(scene_state.variants)
                                if artifact.artifact_id == scene_state.selected_artifact_id
                            ),
                            0,
                        ),
                    ),
                    format_func=lambda artifact_id, state=scene_state: _variant_label(
                        state,
                        artifact_id,
                    ),
                    key=f"story_visual_variant_{scene.scene_id}",
                )
                artifact = next(
                    item for item in scene_state.variants if item.artifact_id == selected_id
                )
                st.image(artifact.local_path)
                st.caption(
                    f"{artifact.provider_id} · {artifact.model} · {artifact.origin.value} · "
                    f"SHA-256 {artifact.sha256[:12]}"
                )
                select_column, approve_column, regenerate_column = st.columns(3)
                if select_column.button(
                    t("story.visual.use_variant"),
                    key=f"story_visual_select_{scene.scene_id}",
                    width="stretch",
                ):
                    updated = select_scene_variant(updated, scene.scene_id, selected_id)
                    st.session_state["story_visual_package"] = updated
                    st.rerun()
                if approve_column.button(
                    t("story.visual.approve_scene"),
                    key=f"story_visual_approve_{scene.scene_id}",
                    width="stretch",
                ):
                    if scene_state.selected_artifact_id != selected_id:
                        updated = select_scene_variant(updated, scene.scene_id, selected_id)
                    updated = approve_selected_scene_variant(
                        updated,
                        scene.scene_id,
                        context.artisan_id,
                    )
                    st.session_state["story_visual_package"] = updated
                    st.rerun()
                if regenerate_column.button(
                    t("story.visual.regenerate"),
                    key=f"story_visual_regenerate_{scene.scene_id}",
                    width="stretch",
                ):
                    updated = generate_scene_variant(
                        project,
                        updated,
                        provider,
                        _story_storage(),
                        scene.scene_id,
                    )
                    st.session_state["story_visual_package"] = updated
                    st.rerun()
                if scene_state.approval:
                    st.success(t("story.visual.scene_approved"))
            else:
                if st.button(
                    t("story.visual.generate_scene"),
                    key=f"story_visual_generate_{scene.scene_id}",
                ):
                    updated = generate_scene_variant(
                        project,
                        updated,
                        provider,
                        _story_storage(),
                        scene.scene_id,
                    )
                    st.session_state["story_visual_package"] = updated
                    st.rerun()

            replacement = st.file_uploader(
                t("story.visual.upload_replacement"),
                type=("png", "jpg", "jpeg", "webp"),
                key=f"story_visual_replacement_{scene.scene_id}",
            )
            replacement_rights = st.checkbox(
                t("story.visual.upload_rights"),
                key=f"story_visual_replacement_rights_{scene.scene_id}",
            )
            if st.button(
                t("story.visual.add_replacement"),
                key=f"story_visual_add_replacement_{scene.scene_id}",
                disabled=replacement is None,
            ):
                try:
                    updated = add_uploaded_scene_variant(
                        project,
                        updated,
                        _story_storage(),
                        scene.scene_id,
                        file_name=replacement.name,
                        media_type=replacement.type,
                        content=replacement.getvalue(),
                        rights_confirmed=replacement_rights,
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["story_visual_package"] = updated
                    st.rerun()
    return updated


def _save_visual_references(
    project: StoryProject,
    storage: StoryMediaStorage,
    uploads: dict[VisualReferenceKind, list[object]],
    source_note: str,
) -> tuple[VisualReference, ...]:
    references: list[VisualReference] = []
    for kind, files in uploads.items():
        for uploaded in files:
            references.append(
                storage.save_reference(
                    project_id=project.project_id,
                    kind=kind,
                    file_name=uploaded.name,
                    media_type=uploaded.type,
                    content=uploaded.getvalue(),
                    source_note=source_note,
                )
            )
    return tuple(references)


def _resolve_provider(mode: str) -> ImageProvider:
    override = st.session_state.get("_story_image_provider_override")
    if override is not None:
        return override
    try:
        return image_provider_for(mode)
    except MissingImageAPIKeyError:
        return DemoImageProvider()


def _story_storage() -> StoryMediaStorage:
    override = st.session_state.get("_story_media_storage_override")
    if isinstance(override, StoryMediaStorage):
        return override
    return StoryMediaStorage(_DEFAULT_MEDIA_ROOT)


def _variant_label(scene_state: object, artifact_id: str) -> str:
    artifact = next(
        artifact for artifact in scene_state.variants if artifact.artifact_id == artifact_id
    )
    return t(
        "story.visual.variant_label",
        number=artifact.variant_number,
        provider=artifact.provider_id,
    )


def _split_guidance(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.replace("；", ";").split(";") if item.strip())


def _product_label(context: GrowthProductContext) -> str:
    name = (
        context.product_name_en
        if get_language() is Language.EN_US and context.product_name_en
        else context.product_name
    )
    return f"{name} · {context.craft_name}"


def _export_json(project: StoryProject) -> str:
    return json.dumps(
        asdict(project),
        ensure_ascii=False,
        indent=2,
        default=lambda value: (
            value.isoformat() if isinstance(value, datetime) else _enum_value(value)
        ),
    )


def _enum_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported export value: {type(value).__name__}")


__all__ = ["render_story_hero", "render_story_studio_app"]
