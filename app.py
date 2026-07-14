"""Streamlit demonstration interface for HeritageLink AI."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import streamlit as st

from heritagelink.content import generate_bilingual_content
from heritagelink.data_loader import DataValidationError, build_products, load_data
from heritagelink.inquiry import (
    INQUIRY_DISCLAIMER_ZH,
    InquiryDetails,
    build_customization_inquiry,
    inquiry_to_json,
)
from heritagelink.models import DataBundle, GiftRequest, Product, Recommendation
from heritagelink.recommender import recommend

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data" / "demo"

CUSTOMER_TYPES = ("企业客户", "政府/高校/文化机构", "个人客户", "海外客户")
RECIPIENTS = {
    "商务伙伴": "business_partner",
    "机构客户": "institution",
    "员工": "employee",
    "长辈": "elder",
    "家人": "family",
    "朋友": "friend",
    "新婚夫妇": "newlywed",
    "教师": "teacher",
    "收藏者": "collector",
}
OCCASIONS = {
    "商务礼赠": "business_gift",
    "机构纪念": "commemoration",
    "婚礼": "wedding",
    "周年纪念": "anniversary",
    "乔迁": "housewarming",
    "生日": "birthday",
    "节庆": "festival",
    "毕业": "graduation",
    "感谢答谢": "appreciation",
    "收藏": "collection",
    "展览展示": "exhibition",
}
STYLES = {
    "传统": "traditional",
    "现代": "modern",
    "简约": "minimal",
    "大气": "grand",
    "典雅": "elegant",
    "喜庆": "festive",
    "温暖": "warm",
}
MEANINGS = {
    "文化传承": "heritage",
    "繁荣兴盛": "prosperity",
    "祝福": "blessing",
    "和谐": "harmony",
    "长久": "longevity",
    "坚韧": "resilience",
    "纪念": "remembrance",
    "感谢": "gratitude",
    "相伴结合": "union",
}
DESTINATIONS = (
    "中国大陆",
    "中国香港",
    "中国澳门",
    "中国台湾",
    "新加坡",
    "美国",
    "英国",
    "其他海外国家或地区",
)
DIMENSION_LABELS = {
    "budget": "预算匹配",
    "recipient": "赠礼对象",
    "occasion": "使用场景",
    "style": "风格偏好",
    "cultural_meaning": "文化寓意",
    "customization": "定制匹配",
    "quantity": "数量与产能",
    "lead_time": "交付时间",
}
TAG_LABELS = {
    **{value: key for key, value in RECIPIENTS.items()},
    **{value: key for key, value in OCCASIONS.items()},
    **{value: key for key, value in STYLES.items()},
    **{value: key for key, value in MEANINGS.items()},
    "customization:inscription": "定制：题字",
    "customization:packaging": "定制：包装",
    "customization:logo": "定制：Logo",
}


@st.cache_resource
def load_catalog() -> tuple[DataBundle, tuple[Product, ...]]:
    """Load validated local demo data once for the Streamlit process."""
    bundle = load_data(DATA_DIR)
    return bundle, build_products(bundle)


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.0f}"


def _recommendation_reasons(recommendation: Recommendation) -> tuple[str, ...]:
    ranked = sorted(
        recommendation.score_breakdown.values(),
        key=lambda dimension: (-dimension.score, -dimension.max_score, dimension.explanation),
    )
    return tuple(item.explanation for item in ranked[:3])


def _request_form() -> tuple[GiftRequest, InquiryDetails] | None:
    st.subheader("告诉我们这份礼物要送给谁")
    st.caption("结构化选项用于规则匹配；自由文字只进入需求单，不参与隐式推断。")
    with st.form("gift_request_form"):
        left, right = st.columns(2)
        with left:
            customer_type = st.selectbox("客户类型", CUSTOMER_TYPES)
            recipient_label = st.selectbox("赠礼对象", tuple(RECIPIENTS))
            budget_yuan = st.number_input(
                "绝对单件预算上限（人民币元）", min_value=100, max_value=100000, value=1200
            )
            quantity = st.number_input("采购数量", min_value=1, max_value=10000, value=10)
            occasion_label = st.selectbox("使用场景", tuple(OCCASIONS))
            style_label = st.selectbox("风格偏好", tuple(STYLES))
        with right:
            meaning_label = st.selectbox("文化寓意偏好", tuple(MEANINGS))
            customization_required = st.checkbox("需要定制")
            logo_required = st.checkbox("必须加入 Logo", disabled=not customization_required)
            destination = st.selectbox("目的国家或地区", DESTINATIONS)
            available_lead_days = st.number_input(
                "希望在多少天内交付", min_value=1, max_value=365, value=45
            )
            output_language = st.selectbox("输出语言", ("中英双语", "中文", "English"))

        customization_theme = ""
        inscription_text = ""
        packaging_requirement = ""
        if customization_required:
            st.markdown("#### 定制补充信息")
            custom_left, custom_right = st.columns(2)
            with custom_left:
                customization_theme = st.text_input(
                    "定制主题", max_chars=500, placeholder="例如：企业周年纪念"
                )
                inscription_text = st.text_input(
                    "题字内容", max_chars=500, placeholder="留空则标记为待商家确认"
                )
            with custom_right:
                packaging_requirement = st.text_area(
                    "包装要求", max_chars=500, placeholder="例如：商务礼盒；留空则待确认"
                )

        submitted = st.form_submit_button("生成礼品推荐", type="primary", width="stretch")
    if not submitted:
        return None

    required_types = {"inscription"} if inscription_text.strip() else set()
    preferred_types = {"packaging"} if packaging_requirement.strip() else set()
    request = GiftRequest(
        request_id=f"req_demo_{uuid4().hex[:12]}",
        unit_budget_max_fen=int(budget_yuan) * 100,
        quantity=int(quantity),
        recipient_tags=frozenset({RECIPIENTS[recipient_label]}),
        occasion_tags=frozenset({OCCASIONS[occasion_label]}),
        style_tags=frozenset({STYLES[style_label]}),
        meaning_tags=frozenset({MEANINGS[meaning_label]}),
        customization_required=customization_required,
        required_customization_types=frozenset(required_types),
        preferred_customization_types=frozenset(preferred_types),
        logo_required=logo_required,
        international_shipping_required=destination != "中国大陆",
        available_lead_days=int(available_lead_days),
    )
    details = InquiryDetails(
        customer_type=customer_type,
        customization_theme=customization_theme,
        inscription_text=inscription_text,
        packaging_requirement=packaging_requirement,
        destination=destination,
        output_language=output_language,
    )
    return request, details


def _render_inquiry(
    recommendation: Recommendation,
    request: GiftRequest,
    details: InquiryDetails,
    bundle: DataBundle,
) -> None:
    content = generate_bilingual_content(recommendation.product, bundle.product_texts)
    inquiry = build_customization_inquiry(request, recommendation, content, details)
    inquiry_json = inquiry_to_json(inquiry)
    st.success("已生成结构化定制需求单。所有未确认信息均已列入商家问题清单。")
    st.json(inquiry, expanded=False)
    st.download_button(
        "下载需求单 JSON",
        data=inquiry_json,
        file_name=f"{inquiry['inquiry_id']}.json",
        mime="application/json",
        key=f"download_{recommendation.product.product_id}",
    )


def _render_recommendation(
    rank: int,
    recommendation: Recommendation,
    request: GiftRequest,
    details: InquiryDetails,
    bundle: DataBundle,
) -> None:
    product = recommendation.product
    with st.container(border=True):
        st.markdown(f"### {rank}. {product.product_name_zh}")
        st.caption(product.product_name_en)
        metric_left, metric_mid, metric_right = st.columns(3)
        metric_left.metric("综合匹配分", f"{recommendation.total_score:.1f} / 100")
        metric_mid.metric(
            "演示单价", f"{_money(product.price_min_fen)}–{_money(product.price_max_fen)}"
        )
        metric_right.metric("演示制作周期", f"{product.lead_time_days} 天")

        st.markdown("#### 推荐理由")
        for reason in _recommendation_reasons(recommendation):
            st.markdown(f"- {reason}")

        with st.expander("查看各维度得分", expanded=True):
            score_rows = [
                {
                    "维度": DIMENSION_LABELS[key],
                    "得分": value.score,
                    "满分": value.max_score,
                    "解释": value.explanation,
                }
                for key, value in recommendation.score_breakdown.items()
            ]
            st.dataframe(score_rows, hide_index=True, width="stretch")

        matched = [TAG_LABELS.get(tag, tag) for tag in recommendation.matched_tags]
        st.markdown(f"**匹配标签：** {'、'.join(matched) if matched else '无精确标签命中'}")
        st.markdown("**风险与待确认事项：**")
        for risk in recommendation.risks:
            st.warning(risk)

        content = generate_bilingual_content(product, bundle.product_texts)
        st.markdown("#### 双语文化介绍")
        zh_tab, en_tab = st.tabs(("中文", "English"))
        with zh_tab:
            st.text(content.zh.text)
        with en_tab:
            st.text(content.en.text)

        if st.button(
            "生成定制需求单",
            key=f"inquiry_{product.product_id}",
            width="stretch",
        ):
            st.session_state["active_inquiry_product"] = product.product_id
        if st.session_state.get("active_inquiry_product") == product.product_id:
            _render_inquiry(recommendation, request, details, bundle)
        st.caption(product.demo_disclaimer)


def _render_results(bundle: DataBundle) -> None:
    response = st.session_state.get("recommendation_response")
    request = st.session_state.get("gift_request")
    details = st.session_state.get("inquiry_details")
    if response is None or request is None or details is None:
        return

    st.divider()
    st.header("推荐结果")
    if not response.has_eligible_products:
        st.error("没有合格产品，本次不会强行推荐。")
        st.markdown("#### 主要冲突原因")
        for conflict in response.primary_conflicts:
            st.markdown(f"- {conflict}")
        st.markdown("#### 可以调整的条件")
        for suggestion in response.adjustment_suggestions:
            st.markdown(f"- {suggestion}")
        return

    st.success(f"找到 {len(response.recommendations)} 件符合硬性条件的演示产品。")
    for rank, recommendation in enumerate(response.recommendations, start=1):
        _render_recommendation(rank, recommendation, request, details, bundle)


def main() -> None:
    st.set_page_config(page_title="HeritageLink AI｜非遗礼遇", page_icon="🎁", layout="wide")
    st.title("HeritageLink AI｜非遗礼遇")
    st.markdown("用可解释规则，把礼赠需求转化为非遗产品推荐和商家可执行的定制需求单。")
    st.error(INQUIRY_DISCLAIMER_ZH)
    st.info("当前为飞颐铁画单商家试点，但数据结构和核心模块支持未来接入多个商家与非遗品类。")

    try:
        bundle, products = load_catalog()
    except DataValidationError as exc:
        st.error(f"演示数据加载失败：{exc}")
        st.stop()

    form_result = _request_form()
    if form_result is not None:
        request, details = form_result
        st.session_state["gift_request"] = request
        st.session_state["inquiry_details"] = details
        st.session_state["recommendation_response"] = recommend(products, request)
        st.session_state.pop("active_inquiry_product", None)
    _render_results(bundle)


if __name__ == "__main__":
    main()
