# Conversational Heritage Gift Matching and Customization Workflow

中文名称：对话式非遗礼品匹配与定制工作流

## Workflow 目标

该 Workflow 将用户对礼赠场景的自然语言描述或详细表单，依次转换为可核对的结构化需求、符合明确硬约束的渐进式推荐、有事实边界的中英文文化内容，以及商家可继续确认和报价的定制需求单。

它是 OPC 2026 Youth S3 第二轮 Wave 2 的唯一 Submitted Workflow。报名并提交截止为2026年7月20日，社区交叉评测为2026年7月21日，晋级结果公布为2026年7月22日。

## 输入与最终输出

输入可以是：

- 一段不超过 3000 字符的自然语言礼赠需求；或
- Streamlit 详细表单中的预算、数量、对象、场景、交期、目的地、定制和内容语言等字段。

最终输出包括：

- 经过本地校验并由用户确认的 `ParsedCustomerRequest`；
- `ProgressiveRecommendationResult`，其中包含推荐模式、信息覆盖度、置信度、0–3 件符合全部明确硬约束的目录 MVP 演示方案、过滤失败和独立替代建议；
- `BilingualContent`，其中包含中文、英文、来源说明、审核状态和待确认标记；
- 通过 `validate_inquiry` 校验、可下载为 UTF-8 JSON 的商家定制需求单。

## 五阶段主路径

| 阶段 | 用户或系统行为 | 主要代码 | 关键边界 |
|---|---|---|---|
| 1. 描述需求 | 用户输入自然语言，选择示例，或切换到详细表单。 | `app.py::_render_describe`；`dialogue_manager.process_turn`；`conversation_state.new_conversation`；`ui/requirements.py` | DeepSeek 仅为可选字段提取器；无 Key 或失败时回退到确定性演示解析。 |
| 2. 核对并补充需求 | 页面展示对话历史、已识别、缺失和不确定字段；用户可以继续输入新一轮信息、合并字段或直接修改表单。 | `app.py::_render_confirm`；`dialogue_manager.process_turn/merge_requests`；`request_parser.validate_parsed_payload`；`parsed_from_widgets` | 模型输出必须经过本地类型、枚举、金额和字段校验；本地累计状态和用户修改优先。 |
| 3. 匹配产品 | 系统根据当前已知字段选择探索、引导或约束模式，执行硬过滤、评分和稳定排序。 | `progressive_recommender.recommend_progressively`；`recommender.recommend`；`app.py::_render_recommend` | 未知字段不记负分；明确预算、数量、Logo、交期、定制和运输要求不能被绕过；最多 3 件。 |
| 4. 查看文化内容 | 用户查看中文、英文、工艺依据、来源状态和定制建议。 | `content.generate_bilingual_content`；`app.py::_render_culture` | 只组织本地已有字段；40 条文化资料当前均为 `draft`，需要商家审核。 |
| 5. 生成需求单 | 用户选择一件符合条件的目录 MVP 演示方案，预览、复制并下载商家需求单 JSON。 | `inquiry.build_customization_inquiry`、`validate_inquiry`、`inquiry_to_json`；`app.py::_render_inquiry` | 保存选择时方案快照和待确认项；不构成订单、报价或履约承诺。 |

```text
自然语言描述或详细表单
→ 结构化理解与用户确认
→ 可选多轮补充与本地字段合并
→ 渐进式推荐模式
→ 明确硬约束过滤与已知维度评分
→ 0–3 件符合全部明确硬约束的目录 MVP 演示方案
→ 有事实边界的双语文化内容
→ 商家可执行的定制需求单
```

## 失败与回退路径

### 无 DeepSeek API Key 或 API 失败

`request_parser.parse_request` 捕获安全映射后的模型错误，改用 `demo_parse_request`，并在 `parser_mode` 和 `parser_notice` 中保留回退状态。该回退只改变需求解析方式，不改变后续硬过滤、评分、内容模板和需求单逻辑。

自动化测试不会尝试访问真实 DeepSeek API：`tests/conftest.py` 使用自动 fixture 设置占位 Key，并将真实 completion 调用替换为抛出断言错误的守卫。

### 无满足全部明确硬约束的商品

页面明确显示“当前没有满足全部明确条件的现有产品，我们不会强行推荐”，展示主要冲突、可调整方向和与条件有冲突的参考方案。这里的“现有产品”是当前 UI 对目录中 MVP 演示方案的简称；冲突方案不能标记为合格推荐。

用户可以选择生成独立的定制需求概念。`customization_concept.build_customization_concept` 强制使用 `is_existing_product=false`，且不生成虚构产品 ID 或名称；该概念不代表现有产品、正式报价、产能或交付承诺。

### 文化资料缺失或未审核

缺失字段显示“待商家确认 / Pending merchant confirmation”。`draft` 内容可以作为明确标注的 MVP 演示文案展示，但不能表述为商家已审核事实，也不会在运行时调用机器翻译或模型补写事实。

### 需求单校验失败

`validate_inquiry` 检查需求单顶层契约、恰好一个选中商品及双语文化内容。未通过校验时不应输出部分 JSON；页面仍可保留已有需求和商品选择，供用户修正或重试。

## 代码和测试证据

| Workflow 能力 | 代码入口 | 自动化测试 |
|---|---|---|
| 自然语言解析、本地校验、无 Key 回退 | `src/heritagelink/request_parser.py`、`llm_client.py` | `tests/test_request_parser.py`、`tests/test_llm_client.py` |
| 多轮状态、字段合并和签名 | `conversation_state.py`、`dialogue_manager.py`、`app.py::_render_confirm` | `tests/test_dialogue_manager.py`、`tests/test_app_smoke.py::test_confirmation_supports_a_second_conversation_turn` |
| 渐进式推荐、硬过滤、稳定排序 | `progressive_recommender.py`、`recommender.py` | `tests/test_progressive_recommender.py`、`tests/test_recommender.py` |
| 无结果时不虚构商品 | `customization_concept.py` | `tests/test_customization_concept.py` |
| 有事实边界的双语内容 | `content.py` | `tests/test_content.py` |
| 商家需求单及 JSON 校验 | `inquiry.py` | `tests/test_inquiry.py` |
| 五阶段 Streamlit 主路径 | `app.py` | `tests/test_app_smoke.py::test_product_culture_and_inquiry_complete_five_stage_flow` |
| 无满足条件时不强推 | `app.py::_render_recommend` | `tests/test_app_smoke.py::test_precise_form_no_result_does_not_force_recommendation` |

## 如何运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m streamlit run app.py
```

无需 DeepSeek API Key即可完成主路径。选择“确定性演示模式”，再使用“体验企业海外礼赠案例”。详细步骤见 [`DEMO_CASE.md`](DEMO_CASE.md)。最终命令验证结果见 [`EVALUATION.md`](EVALUATION.md)。

## 当前 Prototype 边界

当前页面在首轮输入后保存 `ConversationState`，确认阶段在展开区用 Markdown 展示历史，并通过 `st.text_input` 和“合并这条补充”按钮再次调用 `process_turn`。用户可以多轮补充或修正需求，再进入结构化确认和推荐。该能力仅存在于当前 Streamlit session：不提供 `st.chat_input` 式连续输入体验、账号、跨设备同步、长期历史、并发会话治理或生产级审计平台。
