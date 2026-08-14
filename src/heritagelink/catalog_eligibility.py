"""Central recommendation qualification gate shared by catalog consumers."""

from __future__ import annotations

from heritagelink.heritage_passport_models import PublicationStatus
from heritagelink.models import Product


def is_recommendation_eligible(product: Product) -> bool:
    """Return whether a canonical product may enter the formal Skill 3 candidate set.

    Artisan drafts use a separate repository and are never converted to ``Product``
    automatically.  This gate additionally fails closed for reference-only products
    even if a malformed fixture marks their operational status active.
    """
    return (
        product.publication_status is PublicationStatus.RECOMMENDABLE
        and product.catalog_role == "recommendation_demo"
        and all(
            status == "active"
            for status in (product.status, product.merchant_status, product.heritage_status)
        )
    )


def eligible_products(products: tuple[Product, ...]) -> tuple[Product, ...]:
    """Keep only formally qualified products without changing their source order."""
    return tuple(product for product in products if is_recommendation_eligible(product))
