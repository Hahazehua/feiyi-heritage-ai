"""Environment-only configuration for the optional DeepSeek parser."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_TOKENS = 1800
API_KEY_PLACEHOLDER = "your_deepseek_api_key_here"


@dataclass(frozen=True, slots=True)
class DeepSeekConfig:
    """DeepSeek settings; callers must never render ``api_key``."""

    api_key: str = field(default="", repr=False)
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    model: str = DEFAULT_DEEPSEEK_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_tokens: int = DEFAULT_MAX_TOKENS

    @property
    def is_configured(self) -> bool:
        """Return whether a non-placeholder API key is available."""
        return bool(self.api_key and self.api_key != API_KEY_PLACEHOLDER)

    @classmethod
    def from_env(cls) -> DeepSeekConfig:
        """Load ``.env`` then read configuration from process environment."""
        load_dotenv()
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).strip()
            or DEFAULT_DEEPSEEK_BASE_URL,
            model=os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL).strip()
            or DEFAULT_DEEPSEEK_MODEL,
        )


def deepseek_is_configured() -> bool:
    """Check API availability without exposing the configured value."""
    return DeepSeekConfig.from_env().is_configured
