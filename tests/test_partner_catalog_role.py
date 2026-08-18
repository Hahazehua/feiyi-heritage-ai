"""The partner role must be displayable without ever becoming recommendable.

Museum references and partner-supplied work are both non-recommendable, but for
different reasons: a museum object is not for sale at all, while a partner piece
is a real object whose commercial terms are simply not confirmed yet. The
catalogue needs to say which is which, and the recommendation gate needs to fail
closed for both.
"""

from __future__ import annotations

import pytest

from heritagelink.catalog_eligibility import is_recommendation_eligible
from heritagelink.data_loader import CATALOG_ROLE_VALUES, NON_RECOMMENDABLE_ROLES
from heritagelink.heritage_passport_models import PublicationStatus


class _Product:
    """Minimal stand-in carrying only what the eligibility gate reads."""

    def __init__(self, role: str, publication: PublicationStatus, status: str) -> None:
        self.catalog_role = role
        self.publication_status = publication
        self.status = status
        self.merchant_status = status
        self.heritage_status = status


def test_the_partner_role_exists() -> None:
    assert "partner_pending_verification" in CATALOG_ROLE_VALUES


def test_partner_work_is_never_recommendable() -> None:
    """Even with every other signal set to its most permissive value."""
    product = _Product(
        "partner_pending_verification",
        PublicationStatus.RECOMMENDABLE,
        "active",
    )

    assert not is_recommendation_eligible(product)  # type: ignore[arg-type]


@pytest.mark.parametrize("role", sorted(NON_RECOMMENDABLE_ROLES))
def test_non_recommendable_roles_fail_closed(role: str) -> None:
    product = _Product(role, PublicationStatus.RECOMMENDABLE, "active")

    assert not is_recommendation_eligible(product)  # type: ignore[arg-type]


def test_the_demo_role_still_qualifies() -> None:
    """The gate has to keep letting the twenty demo products through."""
    product = _Product("recommendation_demo", PublicationStatus.RECOMMENDABLE, "active")

    assert is_recommendation_eligible(product)  # type: ignore[arg-type]
