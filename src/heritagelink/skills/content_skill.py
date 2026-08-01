"""Skill 4 wrapper: compose content solely from the approved catalog text."""

import pandas as pd

from heritagelink.content import BilingualContent, generate_bilingual_content
from heritagelink.models import Product


def execute(product: Product, product_texts: pd.DataFrame) -> BilingualContent:
    return generate_bilingual_content(product, product_texts)
