from __future__ import annotations

import base64
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace

import pytest

from heritagelink.growth_models import EvidenceStatus, GroundedFact, GrowthProductContext
from heritagelink.heritage_passport_models import (
    FactSource,
    PublicationStatus,
    VerificationStatus,
)
from heritagelink.image_providers import (
    DemoImageProvider,
    ImageGenerationRequest,
    ImageNetworkError,
    OpenAIImageConfig,
    OpenAIImageProvider,
    ReferenceImageInput,
)
from heritagelink.story_models import StoryDecision
from heritagelink.story_service import create_story_project, decide_story_project
from heritagelink.story_visual_models import (
    ImageAssetOrigin,
    VisualPackageStatus,
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
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def _context() -> GrowthProductContext:
    facts = tuple(
        GroundedFact(
            field_name=field_name,
            value=value,
            evidence_status=EvidenceStatus.VERIFIED,
            source=FactSource.PUBLIC_SOURCE,
            verification_status=VerificationStatus.CONFIRMED,
            source_note="confirmed test source",
        )
        for field_name, value in (
            ("product_name", "迎客松铁画"),
            ("craft_name", "芜湖铁画"),
            ("region", "安徽芜湖"),
            ("materials", ("低碳钢", "木框")),
            ("craft_process", "锻打、焊接与整形"),
            ("occasion_tags", ("企业礼赠",)),
        )
    )
    return GrowthProductContext(
        artisan_id="artisan-001",
        product_id="iron-picture-001",
        product_name="迎客松铁画",
        product_name_en="Welcoming Pine Iron Picture",
        craft_name="芜湖铁画",
        publication_status=PublicationStatus.RECOMMENDABLE,
        verified_facts=facts,
        unverified_facts=(),
        unknown_fields=(),
    )


def _approved_project():  # type: ignore[no-untyped-def]
    project = create_story_project(_context(), now=NOW)
    return decide_story_project(project, StoryDecision.APPROVE, "artisan-001", now=NOW)


def _bible(project, **kwargs):  # type: ignore[no-untyped-def]
    return build_visual_bible(
        project,
        style="纪实电影摄影",
        palette="铁灰、木色、暖金",
        lighting="自然侧光",
        wardrobe="深色工作服",
        prohibited_elements=("塑料质感", "虚构证书"),
        now=NOW,
        **kwargs,
    )


def test_demo_provider_is_deterministic_and_vertical() -> None:
    request = ImageGenerationRequest(
        request_id="request-1",
        scene_id="scene-01-hook",
        prompt="Documentary macro of iron craft",
        aspect_ratio="9:16",
    )
    provider = DemoImageProvider()

    first = provider.generate(request)
    second = provider.generate(request)

    assert first == second
    assert first.provider_id == "demo"
    assert first.media_type == "image/svg+xml"
    assert (first.width, first.height) == (900, 1600)
    assert b"DETERMINISTIC DEMO VISUAL" in first.content


class _FakeImages:
    def __init__(self) -> None:
        self.generate_kwargs: dict[str, object] | None = None
        self.edit_kwargs: dict[str, object] | None = None

    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        self.generate_kwargs = kwargs
        return SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(b"generated-png").decode())]
        )

    def edit(self, **kwargs):  # type: ignore[no-untyped-def]
        self.edit_kwargs = kwargs
        return SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(b"edited-png").decode())]
        )


def test_openai_provider_uses_generation_without_references() -> None:
    images = _FakeImages()
    provider = OpenAIImageProvider(
        OpenAIImageConfig(api_key="test-key", model="gpt-image-2"),
        client=SimpleNamespace(images=images),
    )

    result = provider.generate(ImageGenerationRequest("request-1", "scene-1", "iron craft", "9:16"))

    assert result.content == b"generated-png"
    assert images.generate_kwargs is not None
    assert images.edit_kwargs is None
    assert images.generate_kwargs["size"] == "1152x2048"


def test_openai_provider_uses_edit_with_reference_images() -> None:
    images = _FakeImages()
    provider = OpenAIImageProvider(
        OpenAIImageConfig(api_key="test-key"),
        client=SimpleNamespace(images=images),
    )
    reference = ReferenceImageInput("ref-1", "artisan.png", "image/png", b"reference")

    result = provider.generate(
        ImageGenerationRequest("request-1", "scene-1", "iron craft", "9:16", (reference,))
    )

    assert result.content == b"edited-png"
    assert images.edit_kwargs is not None
    assert images.generate_kwargs is None
    assert images.edit_kwargs["image"] == [("artisan.png", b"reference", "image/png")]


def test_visual_generation_is_blocked_until_script_approval(tmp_path) -> None:  # type: ignore[no-untyped-def]
    project = create_story_project(_context(), now=NOW)
    bible = _bible(project)

    with pytest.raises(ValueError, match="human script approval"):
        create_visual_package(project, bible, now=NOW)


def test_six_scene_demo_generation_approval_and_export(tmp_path) -> None:  # type: ignore[no-untyped-def]
    project = _approved_project()
    storage = StoryMediaStorage(tmp_path / "media")
    package = create_visual_package(project, _bible(project), now=NOW)

    package = generate_missing_scene_variants(
        project,
        package,
        DemoImageProvider(),
        storage,
        now=NOW,
    )

    assert package.selected_count == 6
    assert package.status is VisualPackageStatus.AWAITING_APPROVAL
    assert all(scene.selected_artifact is not None for scene in package.scenes)
    assert all(
        scene.selected_artifact.origin is ImageAssetOrigin.DEMO_PLACEHOLDER
        for scene in package.scenes
        if scene.selected_artifact
    )

    for scene in package.scenes:
        package = approve_selected_scene_variant(
            package,
            scene.scene_id,
            "artisan-001",
            now=NOW,
        )

    assert package.approved_count == 6
    assert package.status is VisualPackageStatus.APPROVED

    archive_bytes = export_visual_package_zip(project, package, storage)
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        assert {"story-project.json", "visual-package.json"} <= names
        assert len([name for name in names if name.startswith("selected/")]) == 6
        assert str(tmp_path) not in archive.read("visual-package.json").decode()


def test_regeneration_selects_new_variant_and_clears_old_approval(tmp_path) -> None:  # type: ignore[no-untyped-def]
    project = _approved_project()
    storage = StoryMediaStorage(tmp_path / "media")
    package = create_visual_package(project, _bible(project), now=NOW)
    scene_id = project.script.scenes[0].scene_id
    package = generate_scene_variant(
        project, package, DemoImageProvider(), storage, scene_id, now=NOW
    )
    package = approve_selected_scene_variant(package, scene_id, "artisan-001", now=NOW)

    regenerated = generate_scene_variant(
        project, package, DemoImageProvider(), storage, scene_id, now=NOW
    )
    state = regenerated.scenes_by_id[scene_id]

    assert len(state.variants) == 2
    assert state.selected_artifact_id == state.variants[1].artifact_id
    assert state.approval is None


class _FailingProvider:
    provider_id = "failing"

    def generate(self, request):  # type: ignore[no-untyped-def]
        raise ImageNetworkError("provider unavailable")


def test_provider_failure_becomes_recoverable_scene_state(tmp_path) -> None:  # type: ignore[no-untyped-def]
    project = _approved_project()
    storage = StoryMediaStorage(tmp_path / "media")
    package = create_visual_package(project, _bible(project), now=NOW)
    scene_id = project.script.scenes[0].scene_id

    failed = generate_scene_variant(project, package, _FailingProvider(), storage, scene_id)

    assert failed.status is VisualPackageStatus.NEEDS_ATTENTION
    assert failed.scenes_by_id[scene_id].last_error == "provider unavailable"
    assert not failed.scenes_by_id[scene_id].variants


def test_references_require_rights_and_are_sent_to_provider(tmp_path) -> None:  # type: ignore[no-untyped-def]
    project = _approved_project()
    storage = StoryMediaStorage(tmp_path / "media")
    reference = storage.save_reference(
        project_id=project.project_id,
        kind=VisualReferenceKind.ARTISAN,
        file_name="artisan.png",
        media_type="image/png",
        content=b"reference-image",
        source_note="手艺人本人提供",
    )

    with pytest.raises(ValueError, match="rights confirmation"):
        _bible(project, references=(reference,), rights_confirmed=False)

    bible = _bible(project, references=(reference,), rights_confirmed=True)
    package = create_visual_package(project, bible, now=NOW)
    request = DemoImageProvider().generate(
        ImageGenerationRequest(
            "request-1",
            "scene-1",
            "test",
            "9:16",
            (ReferenceImageInput("ref", "artisan.png", "image/png", b"reference"),),
        )
    )
    assert b"1 REFERENCE IMAGE" in request.content
    assert package.visual_bible.references == (reference,)


def test_human_replacement_requires_rights_confirmation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    project = _approved_project()
    storage = StoryMediaStorage(tmp_path / "media")
    package = create_visual_package(project, _bible(project), now=NOW)
    scene_id = project.script.scenes[0].scene_id

    with pytest.raises(ValueError, match="rights confirmation"):
        add_uploaded_scene_variant(
            project,
            package,
            storage,
            scene_id,
            file_name="replacement.jpg",
            media_type="image/jpeg",
            content=b"replacement",
            rights_confirmed=False,
            now=NOW,
        )

    updated = add_uploaded_scene_variant(
        project,
        package,
        storage,
        scene_id,
        file_name="replacement.jpg",
        media_type="image/jpeg",
        content=b"replacement",
        rights_confirmed=True,
        now=NOW,
    )

    assert updated.scenes_by_id[scene_id].selected_artifact is not None
    assert updated.scenes_by_id[scene_id].selected_artifact.origin is ImageAssetOrigin.HUMAN_UPLOAD
