from dataclasses import replace

import pytest

from heritagelink.inference_policy import (
    FORBIDDEN_INFERENCE_FIELDS,
    INFERABLE_FIELDS,
    build_recommendation_context,
)
from heritagelink.request_parser import demo_parse_request


def test_business_anniversary_infers_only_soft_direction() -> None:
    parsed = demo_parse_request("送给合作伙伴的周年礼物")
    context = build_recommendation_context(parsed)

    assert {"elegant", "grand"}.issubset(context.effective_request.style_preferences)
    assert "heritage" in context.effective_request.symbolism_preferences
    assert context.inferred_fields["style_preferences"].reason
    assert context.inferred_fields["style_preferences"].confidence > 0
    assert context.inferred_fields["style_preferences"].source == "local_scenario_policy"


def test_teacher_direction_is_elegant_and_culturally_grounded() -> None:
    parsed = demo_parse_request("送给教授的感谢礼物")
    context = build_recommendation_context(parsed)

    assert "elegant" in context.effective_request.style_preferences
    assert "gratitude" in context.effective_request.symbolism_preferences


def test_wedding_direction_is_festive_and_blessing_oriented() -> None:
    parsed = demo_parse_request("送给新人的婚礼礼物")
    context = build_recommendation_context(parsed)

    assert "festive" in context.effective_request.style_preferences
    assert "union" in context.effective_request.symbolism_preferences


def test_user_soft_preferences_override_inference() -> None:
    parsed = demo_parse_request("送给合作伙伴的周年礼物，希望简约")
    context = build_recommendation_context(parsed)

    assert context.effective_request.style_preferences == ("minimal",)
    assert "style_preferences" not in context.inferred_fields


@pytest.mark.parametrize(
    "field_name",
    sorted(FORBIDDEN_INFERENCE_FIELDS),
)
def test_policy_never_infers_commercial_or_product_facts(field_name: str) -> None:
    parsed = demo_parse_request("送给海外合作伙伴的周年礼物")
    context = build_recommendation_context(parsed)

    assert field_name not in context.inferred_fields
    assert getattr(context.effective_request, field_name) == getattr(parsed, field_name)


def test_allowlist_and_forbidden_fields_do_not_overlap() -> None:
    assert not INFERABLE_FIELDS & FORBIDDEN_INFERENCE_FIELDS


def test_adjusted_preference_is_treated_as_user_provided() -> None:
    inferred = build_recommendation_context(demo_parse_request("送给合作伙伴的周年礼物"))
    adjusted = replace(inferred.effective_request, style_preferences=("modern",))
    context = build_recommendation_context(adjusted)

    assert context.effective_request.style_preferences == ("modern",)
    assert "style_preferences" in context.user_provided_fields
    assert "style_preferences" not in context.inferred_fields
