"""Deterministic, evidence-limited story generation and approval workflow."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from heritagelink.growth_models import EvidenceStatus, GrowthProductContext, GuardianRiskLevel
from heritagelink.story_models import (
    ANCHOR_BEAT_ID,
    ClaimUse,
    LedgerEntry,
    NarrativeBeat,
    NarrativeTemplate,
    StoryCore,
    StoryDecision,
    StoryFactReference,
    StoryGuardianReview,
    StoryHumanDecision,
    StoryPlatform,
    StoryProject,
    StoryProjectStatus,
    StoryReviewIssue,
    StoryScene,
    StorySceneKind,
    StoryScript,
)
from heritagelink.story_phrases import story_phrases_for

XIAOHONGSHU_DURATION_SECONDS = 60
XIAOHONGSHU_ASPECT_RATIO = "9:16"
_SCENE_DURATIONS = (5, 12, 12, 12, 12, 7)
_ANCHOR_FIELDS = (
    "cultural_background",
    "craft_name",
    "heritage_item",
    "region",
    "product_name",
)
_DANGEROUS_CLAIMS: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (
        re.compile(r"国家级大师|national(?:-level)?\s+master", re.IGNORECASE),
        frozenset({"master_status", "artisan_credentials"}),
    ),
    (
        re.compile(r"官方认证|officially\s+certified", re.IGNORECASE),
        frozenset({"certification", "heritage_item"}),
    ),
    (
        re.compile(r"保证(?:全球|国际)配送|guaranteed\s+(?:global|international)\s+shipping", re.I),
        frozenset({"international_shipping"}),
    ),
    (
        re.compile(r"千年传承|thousand-year(?:-old)?\s+(?:legacy|tradition)", re.IGNORECASE),
        frozenset({"cultural_history_age"}),
    ),
)


def build_story_core(
    context: GrowthProductContext,
    template: NarrativeTemplate = NarrativeTemplate.OBJECT_RECORD,
    language: str = "Chinese",
    *,
    now: datetime | None = None,
) -> StoryCore:
    """Turn verified context into a four-beat Story Core without using pending facts."""
    phrases = story_phrases_for(language)
    verified = context.verified_by_name
    anchor_fact = next((verified[name] for name in _ANCHOR_FIELDS if name in verified), None)
    if anchor_fact is None:
        raise ValueError("Story Studio needs at least one verified cultural or identity fact")

    anchor = LedgerEntry(
        entry_id="claim-anchor",
        beat_id=ANCHOR_BEAT_ID,
        claim_text=phrases.anchor_claim.format(
            value=_display_value(anchor_fact.value, phrases.list_separator)
        ),
        use=ClaimUse.GROUNDED,
        field_name=anchor_fact.field_name,
        evidence_status=EvidenceStatus.VERIFIED,
        source_note=anchor_fact.source_note or anchor_fact.source.value,
        source_url=anchor_fact.source_url,
    )
    beats: list[NarrativeBeat] = []
    ledger: list[LedgerEntry] = []
    for ordinal, blueprint in enumerate(phrases.blueprints(template), start=1):
        fact = next((verified[name] for name in blueprint.fields if name in verified), None)
        if fact is None:
            claim_text = blueprint.without_fact
            entry = LedgerEntry(
                entry_id=f"claim-{blueprint.beat_id}",
                beat_id=blueprint.beat_id,
                claim_text=claim_text,
                use=ClaimUse.ARTISTIC,
                source_note=phrases.artistic_note,
            )
        else:
            claim_text = blueprint.with_fact.format(
                value=_display_value(fact.value, phrases.list_separator)
            )
            entry = LedgerEntry(
                entry_id=f"claim-{blueprint.beat_id}",
                beat_id=blueprint.beat_id,
                claim_text=claim_text,
                use=ClaimUse.GROUNDED,
                field_name=fact.field_name,
                evidence_status=EvidenceStatus.VERIFIED,
                source_note=fact.source_note or fact.source.value,
                source_url=fact.source_url,
            )
        beats.append(
            NarrativeBeat(
                beat_id=blueprint.beat_id,
                ordinal=ordinal,
                title=blueprint.title,
                intent=blueprint.intent,
                summary=claim_text,
                emotion=blueprint.emotion,
            )
        )
        ledger.append(entry)

    product = _story_product_name(context, language) or phrases.product_fallback
    return StoryCore(
        story_id=f"story-{_safe_id(context.product_id)}-{template.value}",
        artisan_id=context.artisan_id,
        product_id=context.product_id,
        template=template,
        premise=phrases.premise.format(product=product, craft=context.craft_name),
        cultural_anchor=anchor,
        beats=tuple(beats),
        ledger=tuple(ledger),
        language=language,
        created_at=now or datetime.now(UTC),
    )


def build_xiaohongshu_story(
    context: GrowthProductContext,
    template: NarrativeTemplate = NarrativeTemplate.OBJECT_RECORD,
    language: str = "Chinese",
    *,
    now: datetime | None = None,
) -> StoryScript:
    """Build the Phase-1, 60-second vertical script and storyboard."""
    created_at = now or datetime.now(UTC)
    core = build_story_core(context, template, language, now=created_at)
    references = _fact_references(core, context)
    reference_by_field = {reference.field_name: reference for reference in references}
    chinese = story_phrases_for(language) is story_phrases_for("Chinese")
    product_name = _story_product_name(context, language)

    anchor_reference = reference_by_field[core.cultural_anchor.field_name or ""]
    scenes: list[StoryScene] = [
        _hook_scene(core, anchor_reference, product_name, chinese),
    ]
    for sequence, (beat, entry) in enumerate(zip(core.beats, core.ledger, strict=True), start=2):
        reference_ids = ()
        if entry.use is ClaimUse.GROUNDED and entry.field_name is not None:
            reference_ids = (reference_by_field[entry.field_name].reference_id,)
        scenes.append(
            _beat_scene(
                beat,
                entry,
                sequence=sequence,
                duration_seconds=_SCENE_DURATIONS[sequence - 1],
                reference_ids=reference_ids,
                chinese=chinese,
            )
        )
    scenes.append(_cta_scene(sequence=6, product_name=product_name, chinese=chinese))

    title = (
        f"60 秒看懂：{product_name}背后的手上功夫"
        if chinese
        else f"The hand skill behind {product_name} in 60 seconds"
    )
    return StoryScript(
        script_id=f"script-{_safe_id(context.product_id)}-{template.value}-xhs",
        story_core=core,
        title=title,
        platform=StoryPlatform.XIAOHONGSHU,
        aspect_ratio=XIAOHONGSHU_ASPECT_RATIO,
        target_duration_seconds=XIAOHONGSHU_DURATION_SECONDS,
        scenes=tuple(scenes),
        fact_references=references,
        created_at=created_at,
    )


def review_story_script(
    script: StoryScript,
    context: GrowthProductContext,
    *,
    now: datetime | None = None,
) -> StoryGuardianReview:
    """Check provenance, unsupported promises, and the Xiaohongshu export contract."""
    issues: list[StoryReviewIssue] = []
    verified = context.verified_by_name
    verified_reference_ids: list[str] = []

    if script.story_core.product_id != context.product_id:
        issues.append(
            _issue("script", "context_mismatch", "脚本与当前产品不匹配", "重新选择产品并生成脚本")
        )
    if script.platform is not StoryPlatform.XIAOHONGSHU:
        issues.append(_issue("script", "platform", "当前阶段仅支持小红书", "选择小红书模板"))
    if script.aspect_ratio != XIAOHONGSHU_ASPECT_RATIO:
        issues.append(_issue("script", "aspect_ratio", "小红书脚本应为 9:16", "改为 9:16 竖屏"))
    if script.total_duration_seconds != XIAOHONGSHU_DURATION_SECONDS:
        issues.append(_issue("script", "duration", "脚本不是 60 秒", "调整镜头时长至 60 秒"))

    for reference in script.fact_references:
        fact = verified.get(reference.field_name)
        expected_id = _reference_id(context.product_id, reference.field_name)
        if (
            fact is None
            or reference.reference_id != expected_id
            or reference.display_value != _display_value(fact.value, "、")
        ):
            issues.append(
                _issue(
                    "script",
                    "unverified_reference",
                    f"事实引用 {reference.reference_id} 无法与已确认资料对应",
                    "移除该表达，或先在 Heritage Passport 中核实",
                )
            )
        else:
            verified_reference_ids.append(reference.reference_id)

    reference_map = script.fact_references_by_id
    for scene in script.scenes:
        scene_text = _scene_text(scene)
        for reference_id in scene.fact_reference_ids:
            reference = reference_map[reference_id]
            if reference.display_value.casefold() not in scene_text.casefold():
                issues.append(
                    _issue(
                        scene.scene_id,
                        "dangling_reference",
                        f"镜头引用了 {reference_id}，但画面与旁白中没有对应事实",
                        "补充事实表达或移除引用",
                    )
                )
        _find_unverified_values(scene, scene_text, context, issues)
        _find_dangerous_claims(scene, scene_text, set(verified), issues)

    approved = not issues
    return StoryGuardianReview(
        approved=approved,
        risk_level=_risk_level(issues),
        issues=tuple(issues),
        reviewed_scene_ids=tuple(scene.scene_id for scene in script.scenes),
        verified_reference_ids=tuple(sorted(set(verified_reference_ids))),
        reviewed_at=now or datetime.now(UTC),
    )


def create_story_project(
    context: GrowthProductContext,
    template: NarrativeTemplate = NarrativeTemplate.OBJECT_RECORD,
    language: str = "Chinese",
    *,
    now: datetime | None = None,
) -> StoryProject:
    """Generate and review a story package, stopping before human approval."""
    updated_at = now or datetime.now(UTC)
    script = build_xiaohongshu_story(context, template, language, now=updated_at)
    review = review_story_script(script, context, now=updated_at)
    status = (
        StoryProjectStatus.AWAITING_HUMAN_APPROVAL
        if review.approved
        else StoryProjectStatus.NEEDS_REVISION
    )
    return StoryProject(
        project_id=f"project-{_safe_id(context.product_id)}-{template.value}",
        script=script,
        guardian_review=review,
        status=status,
        updated_at=updated_at,
    )


def decide_story_project(
    project: StoryProject,
    decision: StoryDecision,
    actor_id: str,
    note: str = "",
    *,
    now: datetime | None = None,
) -> StoryProject:
    """Apply an explicit human decision; Guardian failures cannot be approved."""
    decided_at = now or datetime.now(UTC)
    if project.status in {StoryProjectStatus.APPROVED, StoryProjectStatus.REJECTED}:
        raise ValueError("a final story decision cannot be overwritten")
    if decision is StoryDecision.APPROVE:
        if (
            project.status is not StoryProjectStatus.AWAITING_HUMAN_APPROVAL
            or not project.guardian_review.approved
        ):
            raise ValueError("a story can be approved only after a clean Guardian review")
        status = StoryProjectStatus.APPROVED
    elif decision is StoryDecision.REQUEST_REVISION:
        status = StoryProjectStatus.NEEDS_REVISION
    else:
        status = StoryProjectStatus.REJECTED
    human_decision = StoryHumanDecision(
        decision=decision,
        actor_id=actor_id,
        note=note.strip(),
        decided_at=decided_at,
    )
    return replace(
        project,
        status=status,
        human_decision=human_decision,
        revision_count=(
            project.revision_count + 1
            if decision is StoryDecision.REQUEST_REVISION
            else project.revision_count
        ),
        updated_at=decided_at,
    )


def replace_story_script(
    project: StoryProject,
    script: StoryScript,
    context: GrowthProductContext,
    *,
    now: datetime | None = None,
) -> StoryProject:
    """Re-review a revised script and clear the previous human decision."""
    updated_at = now or datetime.now(UTC)
    review = review_story_script(script, context, now=updated_at)
    return replace(
        project,
        script=script,
        guardian_review=review,
        status=(
            StoryProjectStatus.AWAITING_HUMAN_APPROVAL
            if review.approved
            else StoryProjectStatus.NEEDS_REVISION
        ),
        human_decision=None,
        updated_at=updated_at,
    )


def _fact_references(
    core: StoryCore,
    context: GrowthProductContext,
) -> tuple[StoryFactReference, ...]:
    references: list[StoryFactReference] = []
    seen: set[str] = set()
    for entry in core.all_entries:
        if entry.use is not ClaimUse.GROUNDED or entry.field_name is None:
            continue
        if entry.field_name in seen:
            continue
        seen.add(entry.field_name)
        fact = context.verified_by_name[entry.field_name]
        references.append(
            StoryFactReference(
                reference_id=_reference_id(context.product_id, fact.field_name),
                field_name=fact.field_name,
                display_value=_display_value(fact.value, "、"),
                source_note=fact.source_note or fact.source.value,
                source_url=fact.source_url,
            )
        )
    return tuple(references)


def _hook_scene(
    core: StoryCore,
    anchor: StoryFactReference,
    product_name: str,
    chinese: bool,
) -> StoryScene:
    if chinese:
        voiceover = f"先别急着看成品。故事要从{anchor.display_value}讲起。"
        visual = f"黑场中出现一束侧光，缓慢照亮作品局部；文化线索：{anchor.display_value}。"
        camera = "微距特写，慢速推近，保留铁质纹理与手工痕迹。"
        on_screen = f"{product_name}，从哪里来？"
        image_prompt = f"9:16 纪实摄影，手工艺器物微距，文化线索 {anchor.display_value}，暖暗调。"
        video_prompt = "从黑场淡入，镜头缓慢推近器物纹理，真实自然光，5 秒。"
    else:
        voiceover = f"Before the finished piece, the story begins with {anchor.display_value}."
        visual = f"A side light slowly reveals the object and its link to {anchor.display_value}."
        camera = "Macro close-up, slow push-in, retaining the marks of handwork."
        on_screen = f"Where does {product_name} begin?"
        image_prompt = (
            f"9:16 documentary macro of a handmade object, {anchor.display_value}, warm low key."
        )
        video_prompt = (
            "Fade in from black and slowly push toward the handmade texture for 5 seconds."
        )
    return StoryScene(
        scene_id="scene-01-hook",
        sequence=1,
        duration_seconds=_SCENE_DURATIONS[0],
        kind=StorySceneKind.HOOK,
        title="钩子" if chinese else "Hook",
        visual_description=visual,
        camera_direction=camera,
        voiceover=voiceover,
        on_screen_text=on_screen,
        image_prompt=image_prompt,
        video_prompt=video_prompt,
        fact_reference_ids=(anchor.reference_id,),
    )


def _beat_scene(
    beat: NarrativeBeat,
    entry: LedgerEntry,
    *,
    sequence: int,
    duration_seconds: int,
    reference_ids: tuple[str, ...],
    chinese: bool,
) -> StoryScene:
    visual = (
        f"围绕“{beat.intent}”拍摄真实手工过程；旁白事实：{entry.spoken_text}"
        if chinese
        else f"Document the real handwork to {beat.intent}; narrated fact: {entry.spoken_text}"
    )
    camera = (
        "手部近景与材料特写交替，动作连续，不夸张演绎。"
        if chinese
        else "Alternate close shots of hands and material; continuous, understated movement."
    )
    image_prompt = (
        f"9:16 纪实手工艺摄影，{visual}，自然光，真实工作台，无文字无水印。"
        if chinese
        else f"9:16 documentary craft photography, {visual}, natural light, real workshop, no text."
    )
    video_prompt = (
        f"以{beat.emotion}的节奏展示手工动作，缓慢横移与固定特写结合，{duration_seconds} 秒。"
        if chinese
        else (
            f"Show the handwork with a {beat.emotion} pace, slow lateral move and locked "
            f"close-ups, {duration_seconds} seconds."
        )
    )
    return StoryScene(
        scene_id=f"scene-{sequence:02d}-{beat.beat_id}",
        sequence=sequence,
        duration_seconds=duration_seconds,
        kind=StorySceneKind.NARRATIVE,
        title=beat.title,
        visual_description=visual,
        camera_direction=camera,
        voiceover=entry.spoken_text,
        on_screen_text=beat.title,
        image_prompt=image_prompt,
        video_prompt=video_prompt,
        fact_reference_ids=reference_ids,
    )


def _cta_scene(*, sequence: int, product_name: str, chinese: bool) -> StoryScene:
    if chinese:
        voiceover = "如果你愿意，下一集让手艺人亲口讲完这双手的故事。"
        visual = "手艺人与作品同框，工作台保持原貌，画面停在安静的注视。"
        camera = "中景固定镜头，结尾轻微拉远并停留。"
        on_screen = "关注 · 看见手艺背后的人"
        image_prompt = f"9:16 纪实肖像，手艺人与{product_name}同框，真实工坊，自然光，无文字。"
        video_prompt = "中景固定，手艺人看向作品，轻微拉远后定格，7 秒。"
    else:
        voiceover = "Next time, let the maker tell the rest of the story in their own words."
        visual = "The maker and object share the frame at the unchanged workbench."
        camera = "Locked medium shot, a gentle pull-back and a quiet hold."
        on_screen = "Follow the hands behind the object"
        image_prompt = (
            f"9:16 documentary portrait of maker and {product_name}, real workshop, natural light."
        )
        video_prompt = (
            "Locked medium shot, maker looks to the object, gentle pull-back and hold "
            "for 7 seconds."
        )
    return StoryScene(
        scene_id="scene-06-cta",
        sequence=sequence,
        duration_seconds=_SCENE_DURATIONS[-1],
        kind=StorySceneKind.CTA,
        title="结尾" if chinese else "Close",
        visual_description=visual,
        camera_direction=camera,
        voiceover=voiceover,
        on_screen_text=on_screen,
        image_prompt=image_prompt,
        video_prompt=video_prompt,
    )


def _find_unverified_values(
    scene: StoryScene,
    scene_text: str,
    context: GrowthProductContext,
    issues: list[StoryReviewIssue],
) -> None:
    for fact in context.unverified_facts:
        value = _display_value(fact.value, "、").strip()
        if len(value) >= 4 and value.casefold() in scene_text.casefold():
            issues.append(
                _issue(
                    scene.scene_id,
                    "pending_fact_used",
                    f"镜头使用了待确认字段 {fact.field_name}",
                    "先核实该字段，或从公开脚本中移除",
                )
            )


def _find_dangerous_claims(
    scene: StoryScene,
    scene_text: str,
    verified_fields: set[str],
    issues: list[StoryReviewIssue],
) -> None:
    for pattern, supporting_fields in _DANGEROUS_CLAIMS:
        if pattern.search(scene_text) and not supporting_fields & verified_fields:
            issues.append(
                _issue(
                    scene.scene_id,
                    "unsupported_claim",
                    f"发现无依据的资质、历史或履约表达：{pattern.pattern}",
                    "删除该表达，或补充并核实对应证据",
                )
            )


def _scene_text(scene: StoryScene) -> str:
    return "\n".join(
        (
            scene.visual_description,
            scene.camera_direction,
            scene.voiceover,
            scene.on_screen_text,
            scene.image_prompt,
            scene.video_prompt,
        )
    )


def _issue(scene_id: str, issue_type: str, reason: str, action: str) -> StoryReviewIssue:
    return StoryReviewIssue(scene_id, issue_type, reason, action)


def _risk_level(issues: list[StoryReviewIssue]) -> GuardianRiskLevel:
    if not issues:
        return GuardianRiskLevel.NONE
    if any(
        issue.issue_type in {"unverified_reference", "pending_fact_used", "unsupported_claim"}
        for issue in issues
    ):
        return GuardianRiskLevel.HIGH
    return GuardianRiskLevel.MEDIUM


def _reference_id(product_id: str, field_name: str) -> str:
    return f"fact-{_safe_id(product_id)}-{_safe_id(field_name)}"


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.strip().casefold()).strip("-") or "item"


def _display_value(value: Any, separator: str) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (tuple, list, set, frozenset)):
        return separator.join(str(item) for item in value)
    return str(value).strip()


def _story_product_name(context: GrowthProductContext, language: str) -> str:
    chinese = story_phrases_for(language) is story_phrases_for("Chinese")
    return context.product_name if chinese else (context.product_name_en or context.product_name)


__all__ = [
    "XIAOHONGSHU_ASPECT_RATIO",
    "XIAOHONGSHU_DURATION_SECONDS",
    "build_story_core",
    "build_xiaohongshu_story",
    "create_story_project",
    "decide_story_project",
    "replace_story_script",
    "review_story_script",
]
