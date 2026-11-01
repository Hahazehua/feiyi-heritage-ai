"""Typed contracts for Story Studio's provider-neutral visual production stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class VisualReferenceKind(StrEnum):
    ARTISAN = "artisan"
    PRODUCT = "product"
    WORKSHOP = "workshop"
    OTHER = "other"


class ImageAssetOrigin(StrEnum):
    AI_GENERATED = "ai_generated"
    DEMO_PLACEHOLDER = "demo_placeholder"
    HUMAN_UPLOAD = "human_upload"


class VisualPackageStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    NEEDS_ATTENTION = "needs_attention"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class VisualReference:
    """One rights-confirmed input image used to keep people and objects consistent."""

    reference_id: str
    kind: VisualReferenceKind
    file_name: str
    media_type: str
    sha256: str
    local_path: str
    source_note: str

    def __post_init__(self) -> None:
        required = (
            self.reference_id,
            self.file_name,
            self.media_type,
            self.sha256,
            self.local_path,
            self.source_note,
        )
        if not all(value.strip() for value in required):
            raise ValueError("visual references require identity, storage, and source metadata")
        if not self.media_type.startswith("image/"):
            raise ValueError("visual references must be images")
        if len(self.sha256) != 64:
            raise ValueError("visual reference sha256 must be a complete hex digest")


@dataclass(frozen=True, slots=True)
class VisualBible:
    """Human-authored continuity constraints shared by every generated scene."""

    bible_id: str
    story_project_id: str
    style: str
    palette: str
    lighting: str
    wardrobe: str
    prohibited_elements: tuple[str, ...]
    references: tuple[VisualReference, ...] = ()
    rights_confirmed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        required = (
            self.bible_id,
            self.story_project_id,
            self.style,
            self.palette,
            self.lighting,
            self.wardrobe,
        )
        if not all(value.strip() for value in required):
            raise ValueError("visual bible is missing required continuity guidance")
        if self.created_at.tzinfo is None:
            raise ValueError("visual bible timestamp must include timezone")
        reference_ids = [reference.reference_id for reference in self.references]
        if len(set(reference_ids)) != len(reference_ids):
            raise ValueError("visual reference ids must be unique")
        if self.references and not self.rights_confirmed:
            raise ValueError("reference images require explicit rights confirmation")


@dataclass(frozen=True, slots=True)
class ImageArtifact:
    """One generated or uploaded candidate for a storyboard scene."""

    artifact_id: str
    scene_id: str
    variant_number: int
    provider_id: str
    model: str
    origin: ImageAssetOrigin
    prompt: str
    media_type: str
    local_path: str
    sha256: str
    width: int | None
    height: int | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        required = (
            self.artifact_id,
            self.scene_id,
            self.provider_id,
            self.model,
            self.prompt,
            self.media_type,
            self.local_path,
            self.sha256,
        )
        if not all(value.strip() for value in required):
            raise ValueError("image artifact is missing required generation metadata")
        if self.variant_number < 1:
            raise ValueError("image artifact variant number must be positive")
        if (self.width is None) != (self.height is None):
            raise ValueError("image artifact dimensions must both be known or unknown")
        if self.width is not None and (self.width < 1 or (self.height or 0) < 1):
            raise ValueError("known image artifact dimensions must be positive")
        if not self.media_type.startswith("image/") or len(self.sha256) != 64:
            raise ValueError("image artifact requires an image MIME type and sha256")
        if self.created_at.tzinfo is None:
            raise ValueError("image artifact timestamp must include timezone")


@dataclass(frozen=True, slots=True)
class SceneImageApproval:
    artifact_id: str
    actor_id: str
    approved_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.actor_id.strip():
            raise ValueError("scene image approval requires an artifact and actor")
        if self.approved_at.tzinfo is None:
            raise ValueError("scene image approval timestamp must include timezone")


@dataclass(frozen=True, slots=True)
class SceneImageState:
    scene_id: str
    variants: tuple[ImageArtifact, ...] = ()
    selected_artifact_id: str | None = None
    approval: SceneImageApproval | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.scene_id.strip():
            raise ValueError("scene image state requires a scene id")
        artifact_ids = [artifact.artifact_id for artifact in self.variants]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("scene image artifact ids must be unique")
        if any(artifact.scene_id != self.scene_id for artifact in self.variants):
            raise ValueError("scene image variants must belong to their scene")
        if self.selected_artifact_id is not None and self.selected_artifact_id not in artifact_ids:
            raise ValueError("selected image artifact must belong to the scene")
        if self.approval is not None and self.approval.artifact_id != self.selected_artifact_id:
            raise ValueError("scene approval must refer to the selected artifact")

    @property
    def selected_artifact(self) -> ImageArtifact | None:
        return next(
            (
                artifact
                for artifact in self.variants
                if artifact.artifact_id == self.selected_artifact_id
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class StoryVisualPackage:
    """All visual variants and approvals for one immutable approved story script."""

    package_id: str
    story_project_id: str
    story_script_id: str
    visual_bible: VisualBible
    scenes: tuple[SceneImageState, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        required = (self.package_id, self.story_project_id, self.story_script_id)
        if not all(value.strip() for value in required) or not self.scenes:
            raise ValueError("visual package requires identity and scene states")
        if self.visual_bible.story_project_id != self.story_project_id:
            raise ValueError("visual bible and package must belong to the same story")
        scene_ids = [scene.scene_id for scene in self.scenes]
        if len(set(scene_ids)) != len(scene_ids):
            raise ValueError("visual package scene ids must be unique")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("visual package timestamps must include timezone")

    @property
    def scenes_by_id(self) -> dict[str, SceneImageState]:
        return {scene.scene_id: scene for scene in self.scenes}

    @property
    def selected_count(self) -> int:
        return sum(scene.selected_artifact_id is not None for scene in self.scenes)

    @property
    def approved_count(self) -> int:
        return sum(scene.approval is not None for scene in self.scenes)

    @property
    def status(self) -> VisualPackageStatus:
        if self.approved_count == len(self.scenes):
            return VisualPackageStatus.APPROVED
        if any(scene.last_error for scene in self.scenes):
            return VisualPackageStatus.NEEDS_ATTENTION
        if self.selected_count == len(self.scenes):
            return VisualPackageStatus.AWAITING_APPROVAL
        if any(scene.variants for scene in self.scenes):
            return VisualPackageStatus.IN_PROGRESS
        return VisualPackageStatus.DRAFT


__all__ = [
    "ImageArtifact",
    "ImageAssetOrigin",
    "SceneImageApproval",
    "SceneImageState",
    "StoryVisualPackage",
    "VisualBible",
    "VisualPackageStatus",
    "VisualReference",
    "VisualReferenceKind",
]
