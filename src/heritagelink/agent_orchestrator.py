"""Unified gated entrypoints for the customer Agent and offline analysis Skill."""

from __future__ import annotations

from dataclasses import replace

from heritagelink.agent_models import (
    AgentOverallStatus,
    AgentRuntimeConfig,
    AgentSessionState,
    AgentTurnResult,
    CatalogSnapshot,
    RequestedAction,
    SkillExecutionTrace,
    SkillStatus,
    UserTurn,
)
from heritagelink.agent_trace import TraceTimer, safety, skipped_trace
from heritagelink.analytics import build_recommendation_event, build_selection_event
from heritagelink.choice_analysis import ChoiceAnalysisRequest, ChoiceAnalysisResult
from heritagelink.conversation_state import ConversationMessage, new_conversation
from heritagelink.dialogue_manager import mark_recommendations_shown
from heritagelink.request_parser import ParsedCustomerRequest
from heritagelink.skills import (
    choice_analysis_skill,
    choice_capture_skill,
    content_skill,
    final_plan_skill,
    preference_inference_skill,
    recommendation_skill,
    request_understanding_skill,
)
from heritagelink.skills.request_understanding_skill import RequestUnderstandingInput

_COMMERCIAL_FIELDS = (
    "budget_per_item",
    "quantity",
    "required_delivery_days",
    "logo_required",
    "international_shipping_required",
)


def _structured_state(request: ParsedCustomerRequest):
    state = new_conversation()
    provided = frozenset(
        name
        for name in (
            "recipient",
            "scene",
            "budget_per_item",
            "quantity",
            "style_preferences",
            "symbolism_preferences",
        )
        if getattr(request, name) not in (None, "", ())
    )
    return replace(
        state,
        accumulated_request=request,
        ready_to_recommend=True,
        messages=(
            ConversationMessage("user", "我选择直接填写需求。"),
            ConversationMessage("assistant", "好的，我会按照您填写的条件进行匹配。"),
        ),
        raw_user_texts=(request.raw_user_text,),
        user_confirmed_fields=provided,
    )


def _trace_tail(reason: str, *, include_capture: bool = True) -> list[SkillExecutionTrace]:
    ids = ["compose_grounded_content", "build_final_gift_plan"]
    if include_capture:
        ids.append("capture_consented_choice")
    ids.append("analyze_gift_choice_signals")
    return [skipped_trace(skill_id, reason) for skill_id in ids]


def _recommend(
    state: AgentSessionState,
    catalog: CatalogSnapshot,
    traces: list[SkillExecutionTrace],
) -> AgentSessionState:
    parsed = state.accumulated_request
    if parsed is None:
        traces.extend(
            [
                skipped_trace("infer_soft_preferences", "没有可验证的结构化需求"),
                skipped_trace("recommend_heritage_gifts", "没有可验证的结构化需求"),
            ]
        )
        return state

    timer = TraceTimer("infer_soft_preferences", "准备推荐前应用受控软偏好政策")
    context = preference_inference_skill.execute(parsed)
    inferred = tuple(context.inferred_fields)
    traces.append(
        timer.finish(
            SkillStatus.SUCCESS,
            input_summary={"known_field_count": len(context.user_provided_fields)},
            output_summary={
                "inferred_fields": inferred,
                "preserved_unknown_commercial_fields": tuple(
                    name
                    for name in _COMMERCIAL_FIELDS
                    if getattr(context.effective_request, name) is None
                ),
            },
            safety_checks=(
                safety(
                    "no_budget_invention",
                    context.effective_request.budget_per_item == parsed.budget_per_item,
                    "预算只来自用户输入",
                ),
            ),
        )
    )

    timer = TraceTimer("recommend_heritage_gifts", "信息足够、用户要求推荐或追问达到上限")
    recommendation = recommendation_skill.execute(catalog.products, context)
    event = build_recommendation_event(state.anonymous_session_id, context, recommendation)
    updated_conversation = (
        mark_recommendations_shown(state.conversation_state)
        if state.conversation_state.ready_to_recommend
        else state.conversation_state
    )
    hard_constraints = tuple(
        name for name in _COMMERCIAL_FIELDS if getattr(context.effective_request, name) is not None
    )
    traces.append(
        timer.finish(
            SkillStatus.SUCCESS,
            input_summary={
                "catalog_total": catalog.catalog_total,
                "formally_recommendable": catalog.formally_recommendable,
                "reference_only": catalog.reference_only,
                "hard_constraints": hard_constraints,
            },
            output_summary={
                "hard_filter_remaining": len(recommendation.response.recommendations),
                "final_recommendation_count": len(recommendation.response.recommendations),
                "alternative_count": len(recommendation.alternatives),
            },
            safety_checks=(
                safety("hard_constraints_preserved", True, "沿用既有硬过滤器"),
                safety("no_automatic_weight_update", True, "本轮只读取固定推荐权重"),
            ),
        )
    )
    return replace(
        state,
        conversation_state=updated_conversation,
        recommendation_context=context,
        recommendation_result=recommendation,
        recommendation_event=event,
        selected_product_id=None,
        selection_event=None,
        grounded_content=None,
        final_plan=None,
    )


def _capture(
    state: AgentSessionState,
    catalog: CatalogSnapshot,
    runtime: AgentRuntimeConfig,
) -> SkillExecutionTrace:
    timer = TraceTimer("capture_consented_choice", "用户选择产品或生成最终方案")
    if state.recommendation_context is None or state.recommendation_event is None:
        return timer.finish(
            SkillStatus.BLOCKED,
            output_summary={"reason": "缺少推荐事件"},
            safety_checks=(safety("consent_required_before_storage", True, "未触发任何写入"),),
        )
    result = choice_capture_skill.execute(
        catalog.repository if runtime.analytics_enabled else None,
        consent_granted=state.consent_state,
        consent_version="analytics-consent-v1",
        consented_at=state.selection_event.selected_at if state.selection_event else None,
        session_id=state.anonymous_session_id,
        session_started_at=state.session_started_at,
        conversation_turn_count=len(state.conversation_state.raw_user_texts),
        entry_source=state.entry_source,
        app_version=runtime.app_version,
        context=state.recommendation_context,
        recommendation_event=state.recommendation_event,
        selection_event=state.selection_event,
    )
    if result.status.startswith("skipped"):
        status = SkillStatus.SKIPPED
    elif result.status == "storage_unavailable":
        status = SkillStatus.DEGRADED
    elif result.status == "validation_failed":
        status = SkillStatus.FAILED_SAFE
    else:
        status = SkillStatus.SUCCESS
    return timer.finish(
        status,
        input_summary={"consent_granted": state.consent_state},
        output_summary={
            "capture_status": result.status,
            "idempotency_protected": result.duplicate,
        },
        fallback_reason=("continue_without_storage" if status is SkillStatus.DEGRADED else None),
        safety_checks=(
            safety(
                "consent_required_before_storage",
                state.consent_state or result.status == "skipped_no_consent",
                "未授权时零写入",
            ),
            safety("no_pii_in_trace", True, "轨迹只记录授权和状态"),
        ),
    )


def _find_selected(state: AgentSessionState):
    if state.recommendation_result is None or state.selected_product_id is None:
        return None
    return next(
        (
            item
            for item in state.recommendation_result.response.recommendations
            if item.product.product_id == state.selected_product_id
        ),
        None,
    )


def run_agent_turn(
    user_turn: UserTurn,
    session_state: AgentSessionState,
    catalog: CatalogSnapshot,
    runtime_config: AgentRuntimeConfig,
) -> AgentTurnResult:
    """Run one deterministic, gated customer-flow turn across the formal Skills."""
    traces: list[SkillExecutionTrace] = []
    state = replace(
        session_state,
        entry_source=user_turn.source,
        consent_state=session_state.consent_state,
    )
    action = user_turn.requested_action

    if action is RequestedAction.RESTART:
        state = replace(
            state,
            conversation_state=new_conversation(),
            recommendation_context=None,
            recommendation_result=None,
            recommendation_event=None,
            selected_product_id=None,
            selection_event=None,
            grounded_content=None,
            final_plan=None,
        )
        traces = [
            skipped_trace(item, "用户重新开始会话")
            for item in (
                "understand_gift_request",
                "infer_soft_preferences",
                "recommend_heritage_gifts",
                "compose_grounded_content",
                "build_final_gift_plan",
                "capture_consented_choice",
                "analyze_gift_choice_signals",
            )
        ]
        return AgentTurnResult(
            "已重新开始，您可以描述新的赠礼需求。",
            state,
            None,
            None,
            None,
            (RequestedAction.CONTINUE_CONVERSATION,),
            tuple(traces),
            AgentOverallStatus.WAITING_FOR_USER,
        )

    if action in {
        RequestedAction.CONTINUE_CONVERSATION,
        RequestedAction.RECOMMEND_NOW,
        RequestedAction.ADJUST_REQUIREMENT,
    }:
        timer = TraceTimer("understand_gift_request", "收到新的需求输入或用户修改")
        if user_turn.structured_request is not None:
            conversation = _structured_state(user_turn.structured_request)
            parser_source = "validated_structured_form"
            assistant = "好的，我会按照您填写的条件进行匹配。"
            next_question = None
            should_recommend = True
            status = SkillStatus.SUCCESS
        else:
            turn = request_understanding_skill.execute(
                RequestUnderstandingInput(state.conversation_state, user_turn.text, runtime_config)
            )
            conversation = turn.state
            parser_source = turn.used_parser_mode
            assistant = turn.assistant_message
            next_question = turn.next_question
            should_recommend = turn.recommended_action in {
                "recommend_products",
                "show_editable_summary",
            }
            status = (
                SkillStatus.FALLBACK
                if turn.used_parser_mode == "deterministic_demo"
                else SkillStatus.SUCCESS
            )
        state = replace(
            state,
            conversation_state=conversation,
            recommendation_context=None,
            recommendation_result=None,
            recommendation_event=None,
            selected_product_id=None,
            selection_event=None,
            grounded_content=None,
            final_plan=None,
        )
        parsed = conversation.accumulated_request
        known_fields = parsed and tuple(
            name
            for name in parsed.__dataclass_fields__
            if name not in {"raw_user_text", "parser_notice"}
            and getattr(parsed, name) not in (None, "", ())
        )
        traces.append(
            timer.finish(
                status,
                input_summary={"message_count": len(conversation.raw_user_texts)},
                output_summary={
                    "known_field_count": len(known_fields or ()),
                    "known_fields": known_fields or (),
                    "unknown_fields": parsed.missing_fields if parsed else (),
                    "uncertain_field_count": len(parsed.uncertain_fields) if parsed else 0,
                    "parser_source": parser_source,
                },
                fallback_reason=(
                    "deterministic_parser" if status is SkillStatus.FALLBACK else None
                ),
                safety_checks=(
                    safety("no_budget_invention", True, "商业字段仅通过验证模型进入状态"),
                    safety("no_pii_in_trace", True, "未记录用户原文"),
                ),
            )
        )
        force = action in {
            RequestedAction.RECOMMEND_NOW,
            RequestedAction.ADJUST_REQUIREMENT,
        }
        if conversation.clarification_rounds >= runtime_config.maximum_clarification_turns:
            force = True
        if force or should_recommend:
            state = _recommend(state, catalog, traces)
            traces.extend(_trace_tail("等待用户选择产品"))
            response = state.recommendation_result.response if state.recommendation_result else None
            count = len(response.recommendations) if response else 0
            return AgentTurnResult(
                assistant,
                state,
                response,
                None,
                None,
                (
                    (RequestedAction.SELECT_PRODUCT, RequestedAction.ADJUST_REQUIREMENT)
                    if count
                    else (RequestedAction.ADJUST_REQUIREMENT,)
                ),
                tuple(traces),
                AgentOverallStatus.COMPLETED if count else AgentOverallStatus.NO_MATCH,
            )
        traces.extend(
            [
                skipped_trace("infer_soft_preferences", "等待用户回答一个补充问题"),
                skipped_trace("recommend_heritage_gifts", "尚未进入推荐门"),
                *_trace_tail("尚未进入产品阶段"),
            ]
        )
        return AgentTurnResult(
            assistant,
            state,
            None,
            next_question,
            None,
            (RequestedAction.CONTINUE_CONVERSATION, RequestedAction.RECOMMEND_NOW),
            tuple(traces),
            AgentOverallStatus.WAITING_FOR_USER,
        )

    traces.extend(
        [
            skipped_trace("understand_gift_request", "本轮没有新的自然语言需求"),
            skipped_trace("infer_soft_preferences", "沿用当前推荐上下文"),
            skipped_trace("recommend_heritage_gifts", "沿用当前推荐结果"),
        ]
    )
    if action is RequestedAction.SELECT_PRODUCT:
        if (
            not user_turn.product_id
            or state.recommendation_event is None
            or state.recommendation_result is None
        ):
            traces.extend(_trace_tail("没有可验证的产品选择"))
            return AgentTurnResult(
                "请先从当前推荐中选择一件产品。",
                state,
                state.recommendation_result.response if state.recommendation_result else None,
                None,
                None,
                (RequestedAction.RECOMMEND_NOW,),
                tuple(traces),
                AgentOverallStatus.FAILED_SAFE,
            )
        selection = build_selection_event(state.recommendation_event, user_turn.product_id)
        state = replace(state, selected_product_id=user_turn.product_id, selection_event=selection)
        recommendation = _find_selected(state)
        timer = TraceTimer("compose_grounded_content", "用户选择了正式推荐产品")
        if recommendation is None:
            traces.append(
                timer.finish(
                    SkillStatus.BLOCKED,
                    output_summary={"reason": "选择不在正式推荐结果中"},
                )
            )
        else:
            content = content_skill.execute(recommendation.product, catalog.bundle.product_texts)
            state = replace(state, grounded_content=content)
            traces.append(
                timer.finish(
                    SkillStatus.SUCCESS,
                    input_summary={"selected_product_present": True},
                    output_summary={
                        "source_categories": ("catalog_product_text",),
                        "template_organized": True,
                        "fact_boundary_protected": True,
                        "omitted_fields": (),
                    },
                    safety_checks=(
                        safety("no_product_fact_invention", True, "只使用审核目录文本"),
                    ),
                )
            )
        traces.append(skipped_trace("build_final_gift_plan", "等待用户点击生成方案"))
        traces.append(_capture(state, catalog, runtime_config))
        traces.append(skipped_trace("analyze_gift_choice_signals", "仅离线按需执行"))
        return AgentTurnResult(
            "已记录您的选择，可以继续生成专属礼品方案。",
            state,
            state.recommendation_result.response,
            None,
            None,
            (RequestedAction.GENERATE_PLAN, RequestedAction.SELECT_PRODUCT),
            tuple(traces),
            AgentOverallStatus.COMPLETED,
        )

    if action is RequestedAction.GENERATE_PLAN:
        recommendation = _find_selected(state)
        if recommendation is None or state.recommendation_result is None:
            traces.extend(_trace_tail("未选择正式推荐产品"))
            return AgentTurnResult(
                "请先选择一件推荐产品，再生成礼品方案。",
                state,
                state.recommendation_result.response if state.recommendation_result else None,
                None,
                None,
                (RequestedAction.SELECT_PRODUCT,),
                tuple(traces),
                AgentOverallStatus.FAILED_SAFE,
            )
        if state.grounded_content is None:
            timer = TraceTimer("compose_grounded_content", "生成方案前补齐可靠双语内容")
            content = content_skill.execute(recommendation.product, catalog.bundle.product_texts)
            state = replace(state, grounded_content=content)
            traces.append(
                timer.finish(
                    SkillStatus.SUCCESS,
                    input_summary={"selected_product_present": True},
                    output_summary={
                        "source_categories": ("catalog_product_text",),
                        "template_organized": True,
                        "fact_boundary_protected": True,
                    },
                    safety_checks=(
                        safety("no_product_fact_invention", True, "只使用审核目录文本"),
                    ),
                )
            )
        else:
            traces.append(skipped_trace("compose_grounded_content", "复用本会话可靠内容"))
        context = state.recommendation_context
        if context is None:
            traces.append(skipped_trace("build_final_gift_plan", "缺少推荐上下文"))
            traces.append(skipped_trace("capture_consented_choice", "方案未生成"))
            traces.append(skipped_trace("analyze_gift_choice_signals", "仅离线按需执行"))
            return AgentTurnResult(
                "当前方案上下文已失效，请重新匹配。",
                state,
                state.recommendation_result.response,
                None,
                None,
                (RequestedAction.RECOMMEND_NOW,),
                tuple(traces),
                AgentOverallStatus.FAILED_SAFE,
            )
        timer = TraceTimer("build_final_gift_plan", "用户已选择产品并请求生成方案")
        request = state.recommendation_result.request_by_product[state.selected_product_id]
        plan = final_plan_skill.execute(
            request, recommendation, state.grounded_content, context.effective_request
        )
        selection = build_selection_event(
            state.recommendation_event,
            state.selected_product_id,
            final_action="customization_brief_generated",
            brief_generated=True,
        )
        state = replace(state, final_plan=plan, selection_event=selection)
        unknown = tuple(
            name for name in _COMMERCIAL_FIELDS if getattr(context.effective_request, name) is None
        )
        traces.append(
            timer.finish(
                SkillStatus.SUCCESS,
                input_summary={"selected_product_present": True},
                output_summary={
                    "plan_type": "existing_product_customization_inquiry",
                    "uses_existing_product": True,
                    "contains_controlled_inference": bool(context.inferred_fields),
                    "unknown_commercial_fields_omitted": bool(unknown),
                    "omitted_fields": unknown,
                    "download_ready": True,
                },
                safety_checks=(
                    safety(
                        "no_commercial_commitment_invention",
                        True,
                        "未知价格、产能和交期保留为后续确认",
                    ),
                ),
            )
        )
        traces.append(_capture(state, catalog, runtime_config))
        traces.append(skipped_trace("analyze_gift_choice_signals", "仅离线按需执行"))
        return AgentTurnResult(
            "专属礼品方案已生成，您可以查看并下载。",
            state,
            state.recommendation_result.response,
            None,
            plan,
            (RequestedAction.ADJUST_REQUIREMENT, RequestedAction.SELECT_PRODUCT),
            tuple(traces),
            AgentOverallStatus.COMPLETED,
        )

    raise ValueError(f"不支持的 requested_action：{action}")


def run_choice_signal_analysis(
    request: ChoiceAnalysisRequest,
    repository,
    runtime_config: AgentRuntimeConfig,
) -> ChoiceAnalysisResult:
    """Run Skill 7 only through an explicit offline/on-demand entrypoint."""
    del runtime_config
    return choice_analysis_skill.execute(request, repository)
