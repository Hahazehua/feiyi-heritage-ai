# Agent 定义与执行闭环

## 名称与目标

HAHA｜飞颐礼遇 AI 出海礼赠智能体 / HAHA Heritage Gifting Agent。

它把模糊礼赠意图逐步转成可核对的需求、可解释的候选礼品和可继续交给商家确认的最终方案。它不会替商家报价或承诺履约，也不会绕过预算、数量、交期、定制和运输等明确硬约束。

## 交互闭环

```text
自然语言或快捷入口
  → 识别已明确条件
  → 每轮追问一个高价值问题（最多 5 轮）
  → 显示“你已告诉我 / 我暂时推测”
  → 硬约束过滤与稳定排序
  → 同页展示最多 3 个方案
  → 用户选品
  → 文化说明与最终礼赠方案
```

以下任一条件成立即停止追问：方向已足够、用户要求直接推荐、用户跳过、达到 5 轮或剩余问题价值很低。已经进入推荐状态后不会因页面重跑而重新追问。

## 受控推断

Agent 仅可根据对象和场景推断风格、寓意、包装方向和输出语言等软偏好，并明确展示理由与置信度。用户明确值始终覆盖推断值。预算、数量、交期、运输、Logo、定制能力、商品价格和库存等商业事实禁止推断。完整规则见 `docs/INFERENCE_POLICY.md`。

## 决策边界与回退

- DeepSeek 缺失、超时或返回非法结构：使用本地确定性解析并给出顾客可理解的提示。
- 信息不足：只问一个最有价值的问题，不把未知值当作负面条件。
- 无商品满足全部硬约束：返回 0 个结果，说明冲突与调整方向。
- 文化字段缺失或未审核：标记待确认，不补写未知事实。
- 分析数据库不可用：忽略写入失败，不中断推荐和选品。
- 用户修改需求：清除旧推荐、旧选择和旧最终方案后重新计算。

## 主要代码入口

- 单页 UI 与流程：`app.py`
- 会话状态与追问策略：`conversation_state.py`、`dialogue_manager.py`
- 字段提取与回退：`request_parser.py`、`llm_client.py`
- 受控推断：`inference_policy.py`、`recommendation_context.py`
- 硬约束与排序：`progressive_recommender.py`、`recommender.py`
- 文化内容与最终需求单：`content.py`、`inquiry.py`
- 匿名授权选择记录：`analytics_service.py`、`analytics.py`、`repositories/`
- 匿名选择信号分析：`choice_analysis.py`、`skills/analyze-gift-choice-signals/scripts/analyze_choices.py`
