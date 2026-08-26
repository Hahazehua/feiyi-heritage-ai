"""Visual production workflow for approved Story Studio scripts."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import asdict, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from heritagelink.image_providers import (
    ImageGenerationRequest,
    ImageProvider,
    ImageProviderError,
    ReferenceImageInput,
)
from heritagelink.story_models import StoryProject, StoryProjectStatus, StoryScene
from heritagelink.story_visual_models import (
    ImageArtifact,
    ImageAssetOrigin,
    SceneImageApproval,
    SceneImageState,
    StoryVisualPackage,
    VisualBible,
    VisualReference,
    VisualReferenceKind,
)

MAX_REFERENCE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


class StoryMediaStorage:
    """Constrained local storage for generated and explicitly uploaded story media."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def save_reference(
        self,
        *,
        project_id: str,
        kind: VisualReferenceKind,
        file_name: str,
        media_type: str,
        content: bytes,
        source_note: str,
    ) -> VisualReference:
        _validate_upload(media_type, content)
        digest = hashlib.sha256(content).hexdigest()
        extension = _extension_for(media_type)
        reference_id = f"ref-{kind.value}-{digest[:12]}"
        path = self._target(
            "references",
            project_id,
            f"{reference_id}-{_safe_segment(Path(file_name).stem)}{extension}",
        )
        _write_bytes(path, content)
        return VisualReference(
            reference_id=reference_id,
            kind=kind,
            file_name=Path(file_name).name,
            media_type=media_type,
            sha256=digest,
            local_path=str(path),
            source_note=source_note.strip() or "human-provided reference",
        )

    def save_artifact(
        self,
        *,
        project_id: str,
        scene_id: str,
        artifact_id: str,
        media_type: str,
        content: bytes,
    ) -> tuple[str, str]:
        if not media_type.startswith("image/") or not content:
            raise ValueError("story image artifact must contain image bytes")
        digest = hashlib.sha256(content).hexdigest()
        path = self._target(
            "artifacts",
            project_id,
            _safe_segment(scene_id),
            f"{_safe_segment(artifact_id)}{_extension_for(media_type)}",
        )
        _write_bytes(path, content)
        return str(path), digest

    def read(self, local_path: str) -> bytes:
        path = Path(local_path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("story media path is outside configured storage")
        return path.read_bytes()

    def _target(self, *parts: str) -> Path:
        target = self.root.joinpath(*(_safe_segment(part) for part in parts)).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("invalid story media storage target")
        return target


def build_visual_bible(
    project: StoryProject,
    *,
    style: str,
    palette: str,
    lighting: str,
    wardrobe: str,
    prohibited_elements: tuple[str, ...],
    references: tuple[VisualReference, ...] = (),
    rights_confirmed: bool = False,
    now: datetime | None = None,
) -> VisualBible:
    created_at = now or datetime.now(UTC)
    return VisualBible(
        bible_id=f"bible-{_safe_segment(project.project_id)}",
        story_project_id=project.project_id,
        style=style.strip(),
        palette=palette.strip(),
        lighting=lighting.strip(),
        wardrobe=wardrobe.strip(),
        prohibited_elements=tuple(item.strip() for item in prohibited_elements if item.strip()),
        references=references,
        rights_confirmed=rights_confirmed,
        created_at=created_at,
    )


def create_visual_package(
    project: StoryProject,
    visual_bible: VisualBible,
    *,
    now: datetime | None = None,
) -> StoryVisualPackage:
    if project.status is not StoryProjectStatus.APPROVED:
        raise ValueError("story images can be created only after human script approval")
    if visual_bible.story_project_id != project.project_id:
        raise ValueError("visual bible belongs to a different story project")
    created_at = now or datetime.now(UTC)
    return StoryVisualPackage(
        package_id=f"visual-{_safe_segment(project.project_id)}",
        story_project_id=project.project_id,
        story_script_id=project.script.script_id,
        visual_bible=visual_bible,
        scenes=tuple(SceneImageState(scene.scene_id) for scene in project.script.scenes),
        created_at=created_at,
        updated_at=created_at,
    )


def generate_scene_variant(
    project: StoryProject,
    package: StoryVisualPackage,
    provider: ImageProvider,
    storage: StoryMediaStorage,
    scene_id: str,
    *,
    now: datetime | None = None,
) -> StoryVisualPackage:
    """Generate one variant; provider failures become visible scene state, not crashes."""
    _assert_visual_access(project, package)
    scene = _story_scene(project, scene_id)
    scene_state = package.scenes_by_id[scene_id]
    variant_number = len(scene_state.variants) + 1
    prompt = compose_scene_image_prompt(scene, package.visual_bible)
    references = _reference_inputs(package.visual_bible, storage)
    request = ImageGenerationRequest(
        request_id=f"{package.package_id}-{scene_id}-v{variant_number}",
        scene_id=scene_id,
        prompt=prompt,
        aspect_ratio=project.script.aspect_ratio,
        reference_images=references,
    )
    updated_at = now or datetime.now(UTC)
    try:
        result = provider.generate(request)
    except ImageProviderError as exc:
        failed_state = replace(scene_state, last_error=str(exc))
        return _replace_scene(package, failed_state, updated_at)

    artifact_id = f"image-{_safe_segment(scene_id)}-v{variant_number}"
    local_path, digest = storage.save_artifact(
        project_id=project.project_id,
        scene_id=scene_id,
        artifact_id=artifact_id,
        media_type=result.media_type,
        content=result.content,
    )
    artifact = ImageArtifact(
        artifact_id=artifact_id,
        scene_id=scene_id,
        variant_number=variant_number,
        provider_id=result.provider_id,
        model=result.model,
        origin=(
            ImageAssetOrigin.DEMO_PLACEHOLDER
            if result.provider_id == "demo"
            else ImageAssetOrigin.AI_GENERATED
        ),
        prompt=prompt,
        media_type=result.media_type,
        local_path=local_path,
        sha256=digest,
        width=result.width,
        height=result.height,
        created_at=updated_at,
    )
    ready_state = replace(
        scene_state,
        variants=(*scene_state.variants, artifact),
        selected_artifact_id=artifact.artifact_id,
        approval=None,
        last_error=None,
    )
    return _replace_scene(package, ready_state, updated_at)


def generate_missing_scene_variants(
    project: StoryProject,
    package: StoryVisualPackage,
    provider: ImageProvider,
    storage: StoryMediaStorage,
    *,
    now: datetime | None = None,
) -> StoryVisualPackage:
    updated = package
    for scene in project.script.scenes:
        if not updated.scenes_by_id[scene.scene_id].variants:
            updated = generate_scene_variant(
                project,
                updated,
                provider,
                storage,
                scene.scene_id,
                now=now,
            )
    return updated


def add_uploaded_scene_variant(
    project: StoryProject,
    package: StoryVisualPackage,
    storage: StoryMediaStorage,
    scene_id: str,
    *,
    file_name: str,
    media_type: str,
    content: bytes,
    rights_confirmed: bool,
    now: datetime | None = None,
) -> StoryVisualPackage:
    _assert_visual_access(project, package)
    if not rights_confirmed:
        raise ValueError("uploaded replacement images require rights confirmation")
    _validate_upload(media_type, content)
    scene_state = package.scenes_by_id[scene_id]
    variant_number = len(scene_state.variants) + 1
    artifact_id = f"image-{_safe_segment(scene_id)}-v{variant_number}"
    local_path, digest = storage.save_artifact(
        project_id=project.project_id,
        scene_id=scene_id,
        artifact_id=artifact_id,
        media_type=media_type,
        content=content,
    )
    updated_at = now or datetime.now(UTC)
    artifact = ImageArtifact(
        artifact_id=artifact_id,
        scene_id=scene_id,
        variant_number=variant_number,
        provider_id="human-upload",
        model="original-file",
        origin=ImageAssetOrigin.HUMAN_UPLOAD,
        prompt=f"Human replacement upload: {Path(file_name).name}",
        media_type=media_type,
        local_path=local_path,
        sha256=digest,
        width=None,
        height=None,
        created_at=updated_at,
    )
    updated_state = replace(
        scene_state,
        variants=(*scene_state.variants, artifact),
        selected_artifact_id=artifact.artifact_id,
        approval=None,
        last_error=None,
    )
    return _replace_scene(package, updated_state, updated_at)


def select_scene_variant(
    package: StoryVisualPackage,
    scene_id: str,
    artifact_id: str,
    *,
    now: datetime | None = None,
) -> StoryVisualPackage:
    scene_state = package.scenes_by_id[scene_id]
    if artifact_id not in {artifact.artifact_id for artifact in scene_state.variants}:
        raise ValueError("selected artifact does not belong to this scene")
    updated_state = replace(
        scene_state,
        selected_artifact_id=artifact_id,
        approval=(
            scene_state.approval
            if scene_state.approval and scene_state.approval.artifact_id == artifact_id
            else None
        ),
    )
    return _replace_scene(package, updated_state, now or datetime.now(UTC))


def approve_selected_scene_variant(
    package: StoryVisualPackage,
    scene_id: str,
    actor_id: str,
    *,
    now: datetime | None = None,
) -> StoryVisualPackage:
    scene_state = package.scenes_by_id[scene_id]
    if scene_state.selected_artifact_id is None:
        raise ValueError("select an image variant before approval")
    approved_at = now or datetime.now(UTC)
    updated_state = replace(
        scene_state,
        approval=SceneImageApproval(
            artifact_id=scene_state.selected_artifact_id,
            actor_id=actor_id,
            approved_at=approved_at,
        ),
    )
    return _replace_scene(package, updated_state, approved_at)


def compose_scene_image_prompt(scene: StoryScene, visual_bible: VisualBible) -> str:
    prohibited = ", ".join(visual_bible.prohibited_elements) or "none supplied"
    references = (
        "Use the supplied artisan, product, and workshop images only as continuity references."
        if visual_bible.references
        else "No identity reference images are supplied; avoid a recognizable close-up face."
    )
    return "\n".join(
        (
            scene.image_prompt,
            f"Continuity style: {visual_bible.style}.",
            f"Palette: {visual_bible.palette}.",
            f"Lighting: {visual_bible.lighting}.",
            f"Wardrobe and appearance: {visual_bible.wardrobe}.",
            f"Exclude: {prohibited}.",
            references,
            "Vertical 9:16 composition. Do not render captions, logos, signatures, or watermarks.",
            "Keep the craft object physically plausible and preserve visible handmade texture.",
        )
    )


def export_visual_package_zip(
    project: StoryProject,
    package: StoryVisualPackage,
    storage: StoryMediaStorage,
) -> bytes:
    """Export manifest, selected images, and consented references as one review package."""
    _assert_visual_access(project, package)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "story-project.json",
            _json_bytes(_without_local_paths(asdict(project))),
        )
        archive.writestr(
            "visual-package.json",
            _json_bytes(_without_local_paths(asdict(package))),
        )
        for scene_state in package.scenes:
            artifact = scene_state.selected_artifact
            if artifact is None:
                continue
            extension = _extension_for(artifact.media_type)
            archive.writestr(
                f"selected/{_safe_segment(scene_state.scene_id)}{extension}",
                storage.read(artifact.local_path),
            )
        if package.visual_bible.rights_confirmed:
            for reference in package.visual_bible.references:
                archive.writestr(
                    f"references/{_safe_segment(reference.reference_id)}"
                    f"{_extension_for(reference.media_type)}",
                    storage.read(reference.local_path),
                )
    return output.getvalue()


def _assert_visual_access(project: StoryProject, package: StoryVisualPackage) -> None:
    if project.status is not StoryProjectStatus.APPROVED:
        raise ValueError("story images can be created only after human script approval")
    if (
        package.story_project_id != project.project_id
        or package.story_script_id != project.script.script_id
    ):
        raise ValueError("visual package does not match the approved story")


def _story_scene(project: StoryProject, scene_id: str) -> StoryScene:
    try:
        return next(scene for scene in project.script.scenes if scene.scene_id == scene_id)
    except StopIteration as exc:
        raise ValueError("unknown story scene") from exc


def _reference_inputs(
    visual_bible: VisualBible,
    storage: StoryMediaStorage,
) -> tuple[ReferenceImageInput, ...]:
    return tuple(
        ReferenceImageInput(
            reference_id=reference.reference_id,
            file_name=reference.file_name,
            media_type=reference.media_type,
            content=storage.read(reference.local_path),
        )
        for reference in visual_bible.references
    )


def _replace_scene(
    package: StoryVisualPackage,
    replacement: SceneImageState,
    updated_at: datetime,
) -> StoryVisualPackage:
    if replacement.scene_id not in package.scenes_by_id:
        raise ValueError("unknown visual package scene")
    return replace(
        package,
        scenes=tuple(
            replacement if scene.scene_id == replacement.scene_id else scene
            for scene in package.scenes
        ),
        updated_at=updated_at,
    )


def _validate_upload(media_type: str, content: bytes) -> None:
    if media_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("only PNG, JPEG, and WebP images are supported")
    if not content or len(content) > MAX_REFERENCE_BYTES:
        raise ValueError("image upload must be between 1 byte and 10 MB")


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _extension_for(media_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }.get(media_type, ".img")


def _safe_segment(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip(".-")
    return normalized or "item"


def _without_local_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                Path(item).name
                if key == "local_path" and isinstance(item, str)
                else _without_local_paths(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_without_local_paths(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_without_local_paths(item) for item in value)
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        default=_json_default,
    ).encode("utf-8")


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported visual export value: {type(value).__name__}")


__all__ = [
    "ALLOWED_IMAGE_TYPES",
    "MAX_REFERENCE_BYTES",
    "StoryMediaStorage",
    "add_uploaded_scene_variant",
    "approve_selected_scene_variant",
    "build_visual_bible",
    "compose_scene_image_prompt",
    "create_visual_package",
    "export_visual_package_zip",
    "generate_missing_scene_variants",
    "generate_scene_variant",
    "select_scene_variant",
]
