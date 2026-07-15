"""飞颐礼遇（HeritageLink AI）recommendation core."""

from heritagelink.config import DeepSeekConfig, deepseek_is_configured
from heritagelink.content import BilingualContent, generate_bilingual_content
from heritagelink.data_loader import DataValidationError, build_products, load_data
from heritagelink.inquiry import InquiryDetails, build_customization_inquiry
from heritagelink.models import GiftRequest, RecommendationResponse
from heritagelink.progressive_recommender import (
    ProgressiveRecommendationResult,
    RecommendationMode,
    recommend_progressively,
)
from heritagelink.recommender import recommend
from heritagelink.request_parser import ParsedCustomerRequest, parse_request

__all__ = [
    "BilingualContent",
    "DataValidationError",
    "DeepSeekConfig",
    "GiftRequest",
    "InquiryDetails",
    "ParsedCustomerRequest",
    "ProgressiveRecommendationResult",
    "RecommendationMode",
    "RecommendationResponse",
    "build_products",
    "build_customization_inquiry",
    "deepseek_is_configured",
    "generate_bilingual_content",
    "load_data",
    "parse_request",
    "recommend",
    "recommend_progressively",
]
