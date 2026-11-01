"""Provider-neutral image generation adapters for Story Studio."""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass, field
from typing import Any, Protocol
from xml.sax.saxutils import escape as xml_escape

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2"
DEFAULT_OPENAI_IMAGE_SIZE = "1152x2048"
DEFAULT_OPENAI_IMAGE_QUALITY = "low"
OPENAI_IMAGE_KEY_PLACEHOLDER = "your_openai_api_key_here"


class ImageProviderError(RuntimeError):
    """Base class for sanitized, user-facing image provider failures."""


class MissingImageAPIKeyError(ImageProviderError):
    pass


class ImageAuthenticationError(ImageProviderError):
    pass


class ImageRateLimitError(ImageProviderError):
    pass


class ImageTimeoutError(ImageProviderError):
    pass


class ImageNetworkError(ImageProviderError):
    pass


class ImageSafetyError(ImageProviderError):
    pass


class ImageEmptyResponseError(ImageProviderError):
    pass


class ImageAPIError(ImageProviderError):
    pass


@dataclass(frozen=True, slots=True)
class ReferenceImageInput:
    reference_id: str
    file_name: str
    media_type: str
    content: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.reference_id, self.file_name, self.media_type)):
            raise ValueError("reference image input is missing metadata")
        if not self.media_type.startswith("image/") or not self.content:
            raise ValueError("reference image input requires non-empty image bytes")


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    request_id: str
    scene_id: str
    prompt: str
    aspect_ratio: str
    reference_images: tuple[ReferenceImageInput, ...] = ()

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.request_id, self.scene_id, self.prompt, self.aspect_ratio)
        ):
            raise ValueError("image request requires identity, prompt, and aspect ratio")


@dataclass(frozen=True, slots=True)
class ImageProviderResult:
    provider_id: str
    model: str
    content: bytes = field(repr=False)
    media_type: str = "image/png"
    width: int = 1152
    height: int = 2048

    def __post_init__(self) -> None:
        if not self.provider_id.strip() or not self.model.strip() or not self.content:
            raise ValueError("image provider returned an incomplete result")
        if not self.media_type.startswith("image/") or self.width < 1 or self.height < 1:
            raise ValueError("image provider returned invalid media metadata")


class ImageProvider(Protocol):
    provider_id: str

    def generate(self, request: ImageGenerationRequest) -> ImageProviderResult: ...


@dataclass(frozen=True, slots=True)
class OpenAIImageConfig:
    api_key: str = field(default="", repr=False)
    model: str = DEFAULT_OPENAI_IMAGE_MODEL
    size: str = DEFAULT_OPENAI_IMAGE_SIZE
    quality: str = DEFAULT_OPENAI_IMAGE_QUALITY
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.model, self.size, self.quality)):
            raise ValueError("OpenAI image configuration cannot contain blank values")
        if self.quality not in {"low", "medium", "high", "auto"}:
            raise ValueError("OpenAI image quality must be low, medium, high, or auto")
        if self.timeout_seconds <= 0:
            raise ValueError("OpenAI image timeout must be positive")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key != OPENAI_IMAGE_KEY_PLACEHOLDER)

    @classmethod
    def from_env(cls) -> OpenAIImageConfig:
        load_dotenv()
        return cls(
            api_key=(
                os.getenv("OPENAI_IMAGE_API_KEY", "").strip()
                or os.getenv("OPENAI_API_KEY", "").strip()
            ),
            model=os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_OPENAI_IMAGE_MODEL).strip()
            or DEFAULT_OPENAI_IMAGE_MODEL,
            size=os.getenv("OPENAI_IMAGE_SIZE", DEFAULT_OPENAI_IMAGE_SIZE).strip()
            or DEFAULT_OPENAI_IMAGE_SIZE,
            quality=os.getenv("OPENAI_IMAGE_QUALITY", DEFAULT_OPENAI_IMAGE_QUALITY).strip()
            or DEFAULT_OPENAI_IMAGE_QUALITY,
        )


class _ImagesClient(Protocol):
    def generate(self, **kwargs: Any) -> Any: ...

    def edit(self, **kwargs: Any) -> Any: ...


class _OpenAIImageClient(Protocol):
    images: _ImagesClient


class OpenAIImageProvider:
    """OpenAI Image API adapter; reference images switch generation to image edit."""

    provider_id = "openai"

    def __init__(
        self,
        config: OpenAIImageConfig,
        *,
        client: _OpenAIImageClient | None = None,
    ) -> None:
        if not config.is_configured and client is None:
            raise MissingImageAPIKeyError("未配置 OpenAI 图像 API Key。")
        self.config = config
        self._client = client or OpenAI(
            api_key=config.api_key,
            timeout=config.timeout_seconds,
            max_retries=1,
        )

    @classmethod
    def from_env(cls) -> OpenAIImageProvider:
        return cls(OpenAIImageConfig.from_env())

    def generate(self, request: ImageGenerationRequest) -> ImageProviderResult:
        try:
            common: dict[str, object] = {
                "model": self.config.model,
                "prompt": request.prompt,
                "size": self.config.size,
                "quality": self.config.quality,
                "output_format": "png",
            }
            if request.reference_images:
                images = [
                    (reference.file_name, reference.content, reference.media_type)
                    for reference in request.reference_images
                ]
                response = self._client.images.edit(image=images, **common)
            else:
                response = self._client.images.generate(**common)
            content = _decode_image_response(response)
            width, height = _parse_size(self.config.size)
            return ImageProviderResult(
                provider_id=self.provider_id,
                model=self.config.model,
                content=content,
                media_type="image/png",
                width=width,
                height=height,
            )
        except AuthenticationError as exc:
            raise ImageAuthenticationError("OpenAI 图像服务认证失败，请检查本地 API Key。") from exc
        except RateLimitError as exc:
            raise ImageRateLimitError("OpenAI 图像服务达到速率或额度限制。") from exc
        except APITimeoutError as exc:
            raise ImageTimeoutError("OpenAI 图像生成超时，请稍后重试。") from exc
        except APIConnectionError as exc:
            raise ImageNetworkError("OpenAI 图像服务网络连接失败。") from exc
        except BadRequestError as exc:
            if getattr(exc, "code", None) == "moderation_blocked":
                raise ImageSafetyError("图像请求未通过供应商安全检查，请调整画面描述。") from exc
            raise ImageAPIError("图像请求参数或内容需要调整。") from exc
        except APIStatusError as exc:
            raise ImageAPIError(f"图像服务暂时不可用（HTTP {exc.status_code}）。") from exc


class DemoImageProvider:
    """Deterministic SVG storyboard cards used when no external key is available."""

    provider_id = "demo"

    def generate(self, request: ImageGenerationRequest) -> ImageProviderResult:
        digest = hashlib.sha256(f"{request.scene_id}\n{request.prompt}".encode()).hexdigest()
        accent = f"#{digest[:6]}"
        secondary = f"#{digest[6:12]}"
        scene_label = xml_escape(request.scene_id.replace("scene-", "SCENE ").upper())
        prompt_excerpt = xml_escape(_shorten(request.prompt, 112))
        reference_note = (
            f"{len(request.reference_images)} REFERENCE IMAGE(S)"
            if request.reference_images
            else "NO REFERENCE IMAGE"
        )
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
 width="900" height="1600" viewBox="0 0 900 1600">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#17130f"/><stop offset="1" stop-color="{secondary}"/>
  </linearGradient>
  <filter id="shadow"><feDropShadow dx="0" dy="18" stdDeviation="25" flood-opacity="0.35"/></filter>
</defs>
<rect width="900" height="1600" fill="url(#bg)"/>
<circle cx="710" cy="250" r="250" fill="{accent}" opacity="0.22"/>
<path d="M130 1180 C260 940 390 1030 455 790 C520 560 680 610 770 390"
 fill="none" stroke="{accent}" stroke-width="18" opacity="0.7"/>
<g filter="url(#shadow)">
  <rect x="110" y="300" width="680" height="720" rx="40" fill="#efe6d5" opacity="0.96"/>
  <path d="M250 790 C350 570 555 570 650 790 C580 900 330 900 250 790Z"
   fill="none" stroke="#2d2924" stroke-width="16"/>
  <path d="M330 730 Q450 480 570 730" fill="none" stroke="{accent}" stroke-width="14"/>
  <circle cx="450" cy="650" r="34" fill="{accent}"/>
</g>
<text x="80" y="120" fill="#efe6d5" font-family="sans-serif" font-size="36"
 letter-spacing="5">HAHA STORY STUDIO</text>
<text x="80" y="190" fill="{accent}" font-family="sans-serif" font-size="52"
 font-weight="700">{scene_label}</text>
<text x="80" y="1250" fill="#efe6d5" font-family="sans-serif" font-size="28">
DETERMINISTIC DEMO VISUAL</text>
<text x="80" y="1305" fill="#c9bdab" font-family="sans-serif" font-size="20">
{xml_escape(reference_note)}</text>
<foreignObject x="80" y="1360" width="740" height="150">
  <div xmlns="http://www.w3.org/1999/xhtml"
   style="font:24px sans-serif;color:#efe6d5;line-height:1.45">{prompt_excerpt}</div>
</foreignObject>
</svg>"""
        return ImageProviderResult(
            provider_id=self.provider_id,
            model="deterministic-svg-v1",
            content=svg.encode("utf-8"),
            media_type="image/svg+xml",
            width=900,
            height=1600,
        )


def openai_image_is_configured() -> bool:
    return OpenAIImageConfig.from_env().is_configured


def image_provider_for(mode: str) -> ImageProvider:
    normalized = mode.strip().casefold()
    if normalized == "openai":
        return OpenAIImageProvider.from_env()
    if normalized == "demo":
        return DemoImageProvider()
    raise ValueError(f"unknown image provider: {mode}")


def _decode_image_response(response: Any) -> bytes:
    data = getattr(response, "data", None)
    encoded = getattr(data[0], "b64_json", None) if data else None
    if not isinstance(encoded, str) or not encoded.strip():
        raise ImageEmptyResponseError("图像供应商返回了空响应。")
    try:
        return base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ImageEmptyResponseError("图像供应商返回了无效图片数据。") from exc


def _parse_size(value: str) -> tuple[int, int]:
    try:
        width, height = value.casefold().split("x", maxsplit=1)
        return int(width), int(height)
    except (TypeError, ValueError):
        return 1152, 2048


def _shorten(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 1]}…"


__all__ = [
    "DEFAULT_OPENAI_IMAGE_MODEL",
    "DemoImageProvider",
    "ImageAPIError",
    "ImageAuthenticationError",
    "ImageEmptyResponseError",
    "ImageGenerationRequest",
    "ImageNetworkError",
    "ImageProvider",
    "ImageProviderError",
    "ImageProviderResult",
    "ImageRateLimitError",
    "ImageSafetyError",
    "ImageTimeoutError",
    "MissingImageAPIKeyError",
    "OpenAIImageConfig",
    "OpenAIImageProvider",
    "ReferenceImageInput",
    "image_provider_for",
    "openai_image_is_configured",
]
