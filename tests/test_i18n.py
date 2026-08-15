"""Tests for application-level language selection and translation safety."""

from __future__ import annotations

from heritagelink.i18n import (
    LANGUAGE_SESSION_KEY,
    Language,
    get_language,
    localize_literal,
    normalize_language,
    set_language,
    t,
)
from heritagelink.i18n.en_US import TRANSLATIONS as EN_US
from heritagelink.i18n.zh_CN import TRANSLATIONS as ZH_CN


def test_chinese_and_english_keys_render_native_copy() -> None:
    assert t("nav.buyer", language=Language.ZH_CN) == "我是买家"
    assert t("nav.buyer", language=Language.EN_US) == "I'm a Buyer"
    assert t("demo.step", language="en", current=2, total=5) == "Demo step 2/5"


def test_translation_resources_have_matching_keys() -> None:
    assert set(ZH_CN) == set(EN_US)


def test_missing_key_uses_safe_fallback() -> None:
    assert t("missing.example", language="en-US") == "missing.example"
    assert t("missing.example", language="zh-CN", default="Fallback") == "Fallback"


def test_known_dialogue_literals_localize_without_changing_unknown_text() -> None:
    assert localize_literal("主要赠送给哪类对象？", language="en") == (
        "Who is the primary recipient?"
    )
    assert localize_literal("Model-authored text", language="en") == "Model-authored text"


def test_language_normalization_and_session_persistence() -> None:
    state: dict[str, object] = {}

    assert set_language("English", state) is Language.EN_US
    assert state[LANGUAGE_SESSION_KEY] == Language.EN_US.value
    assert get_language(state) is Language.EN_US
    assert normalize_language("unsupported") is Language.ZH_CN
