"""Application-level bilingual translation helpers."""

from __future__ import annotations

from collections.abc import MutableMapping
from enum import StrEnum
from typing import Any

from heritagelink.i18n.en_US import TRANSLATIONS as EN_US
from heritagelink.i18n.zh_CN import TRANSLATIONS as ZH_CN


class Language(StrEnum):
    ZH_CN = "zh-CN"
    EN_US = "en-US"


TRANSLATIONS = {
    Language.ZH_CN: ZH_CN,
    Language.EN_US: EN_US,
}
LANGUAGE_SESSION_KEY = "interface_language"
LOCALIZABLE_LITERAL_KEYS = {
    value: key
    for key, value in ZH_CN.items()
    if key.startswith("dialogue.")
    or key
    in {
        "buyer.recommend_now_prompt",
        "buyer.quick.overseas_text",
        "buyer.quick.professor_text",
        "buyer.quick.anniversary_text",
        "buyer.quick.explore_text",
    }
}


def normalize_language(value: object) -> Language:
    normalized = str(value or "").strip().casefold()
    if normalized in {"en", "en-us", "english"}:
        return Language.EN_US
    return Language.ZH_CN


def get_language(session_state: MutableMapping[str, Any] | None = None) -> Language:
    state = session_state
    if state is None:
        try:
            import streamlit as st

            state = st.session_state
        except Exception:
            state = None
    if state is None:
        return Language.ZH_CN
    return normalize_language(state.get(LANGUAGE_SESSION_KEY, Language.ZH_CN.value))


def set_language(value: object, session_state: MutableMapping[str, Any]) -> Language:
    language = normalize_language(value)
    session_state[LANGUAGE_SESSION_KEY] = language.value
    return language


def t(
    key: str,
    *,
    language: Language | str | None = None,
    default: str | None = None,
    **values: object,
) -> str:
    selected = normalize_language(language) if language is not None else get_language()
    template = TRANSLATIONS[selected].get(key)
    if template is None:
        fallback_language = Language.EN_US if selected == Language.ZH_CN else Language.ZH_CN
        template = TRANSLATIONS[fallback_language].get(key, default or key)
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return template


def all_translation_keys() -> frozenset[str]:
    return frozenset(set(ZH_CN) | set(EN_US))


def localize_literal(text: str, *, language: Language | str | None = None) -> str:
    """Translate a known deterministic user-facing literal without changing domain state."""
    key = LOCALIZABLE_LITERAL_KEYS.get(text)
    return t(key, language=language) if key else text


__all__ = [
    "LANGUAGE_SESSION_KEY",
    "Language",
    "all_translation_keys",
    "get_language",
    "localize_literal",
    "normalize_language",
    "set_language",
    "t",
]
