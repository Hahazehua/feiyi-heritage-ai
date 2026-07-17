# Conversational Gift Request Understanding

中文名称：对话式礼赠需求理解

## 提交信息

- Submitted Skill：1 / 4
- 当前阶段：OPC 2026 Youth S3 第二轮 Wave 2
- 报名并提交截止：2026年7月20日
- 社区交叉评测：2026年7月21日
- 晋级结果公布：2026年7月22日
- 当前实现状态：自然语言首轮解析、详细表单、结构化核对、确定性回退、多轮历史展示和补充字段合并已接入 Streamlit；会话只保存在当前 session

## 解决的问题

礼赠用户通常用不完整、口语化的方式表达预算、数量、对象、场景、交期、目的地和定制要求。本 Skill 把用户明确表达的信息转换为统一、可校验、可修改的结构化需求，同时保留缺失和不确定字段，避免模型猜测未提供的商业条件。

它不负责选择商品、修改推荐分数、生成文化事实或作出商家履约承诺。

## 在主 Workflow 中的位置

```text
自然语言描述或详细表单
→ [本 Skill：结构化理解与用户确认]
→ Progressive Heritage Gift Recommendation
```

本 Skill 的输出只有在经过本地校验和用户确认后，才进入后续推荐规则。

## 输入契约

### Streamlit 输入

- 自然语言文本：非空，最多 3000 字符；或
- 详细表单：预算、数量、客户类型、赠礼对象、场景、风格、文化寓意、定制、Logo、目的地、国际运输、交付天数、输出语言、主题、题字、包装和其他说明。

### Python 入口

```python
parse_request(
    text: str,
    *,
    mode: Literal["auto", "deepseek", "deterministic_demo"] = "auto",
    client: DeepSeekClient | None = None,
) -> ParsedCustomerRequest
```

当前 Streamlit 首轮和后续补充使用的多轮入口为：

```python
process_turn(
    state: ConversationState,
    user_message: str,
    *,
    mode: Literal["auto", "deepseek", "deterministic_demo"] = "auto",
    client: DialogueClient | None = None,
) -> DialogueTurnResult
```

## 输出契约

主要输出 `ParsedCustomerRequest`。字段分组如下：

| 分组 | 字段 |
|---|---|
| 采购条件 | `budget_type`、`total_budget`、`budget_per_item`、`quantity`、`required_delivery_days` |
| 对象与场景 | `customer_type`、`recipient`、`scene`、`destination`、`international_shipping_required` |
| 偏好 | `style_preferences`、`symbolism_preferences`、`output_language` |
| 定制 | `customization_required`、`customization_types`、`logo_required`、`requested_theme`、`requested_text`、`packaging_requirement` |
| 追溯与状态 | `raw_user_text`、`parser_mode`、`parser_notice`、`missing_fields`、`uncertain_fields`、`clarification_questions`、`additional_notes` |

输出原则：

- 所有模型输出在进入业务逻辑前执行字段白名单、类型、枚举、数值范围和交叉字段校验；
- 总预算除以数量由本地确定性代码计算，不由模型决定；
- 未表达字段保持 `None` 或空集合，不自动补全；
- 模糊字段进入 `uncertain_fields`；
- 用户在确认表单中的修改优先于初始解析结果；
- `parser_mode` 明确区分 `deepseek` 与 `deterministic_demo`。

## 如何运行

### Prototype 路径

1. 运行 `python -m streamlit run app.py`。
2. 选择“AI 描述需求”或“精准填写需求”。
3. 无 Key 评审请选择“确定性演示模式”。
4. 输入需求或点击“体验企业海外礼赠案例”。
5. 在“AI 已理解您的礼赠需求”页面查看连续对话记录；可输入新一轮信息并点击“合并这条补充”。
6. 核对、修改并确认累计字段。

### 确定性 Python 示例

```python
from heritagelink.request_parser import parse_request

parsed = parse_request(
    "为20位美国合作伙伴准备每件300元、支持Logo的礼物",
    mode="deterministic_demo",
)
```

该示例不调用真实外部 API。

## 实际代码映射

| 职责 | 文件与入口 |
|---|---|
| Streamlit 自然语言输入 | `app.py::_render_describe` |
| 结构化摘要和用户确认 | `app.py::_render_confirm`、`src/heritagelink/ui/requirements.py` |
| 解析和确定性回退 | `src/heritagelink/request_parser.py::parse_request`、`demo_parse_request` |
| 不可信 JSON 校验 | `request_parser.py::validate_parsed_payload` |
| 转换为推荐与需求单输入 | `request_parser.py::to_business_request`、`to_inquiry_details` |
| DeepSeek 客户端与安全错误 | `src/heritagelink/llm_client.py`、`config.py` |
| 提取约束 | `src/heritagelink/dialogue_prompt.py` |
| 多轮状态和本地合并模块 | `conversation_state.py`、`dialogue_manager.py::process_turn/merge_requests` |

## AI 职责边界

DeepSeek 可以：

- 从本轮用户文本提出结构化字段；
- 标记可能缺失或不确定的信息；
- 在对话模块中提出候选回复或候选问题。

DeepSeek 不可以：

- 直接决定是否进入推荐；
- 绕过字段校验或明确硬约束；
- 负责权威的累计需求合并；
- 修改推荐权重或结果；
- 读取商品目录并挑选商品；
- 补写未提供的预算、数量、交期、运输或文化事实。

`dialogue_manager.merge_requests`、本地就绪判断、问题优先级、需求签名和用户确认才是权威状态。当前 Streamlit 首轮通过 `process_turn(new_conversation(), ...)` 建立状态，后续补充继续调用 `process_turn`，并在展开区用 Markdown 展示历史。该接线不改变模型仅提供候选字段、本地代码拥有权威状态的边界。

## 失败与回退

| 失败情况 | 当前行为 |
|---|---|
| 没有 API Key | 使用明确标记的确定性演示解析 |
| 认证、余额、超时或网络错误 | 映射为安全提示并回退，不显示 Key、堆栈或模型推理 |
| 空响应或非法 JSON | 受控重试或拒绝后回退 |
| 模型输出未知字段、非法类型或非法枚举 | 本地校验拒绝并回退 |
| 输入为空或超过 3000 字符 | 阻止解析并显示可操作错误 |
| 字段缺失 | 保持未知并允许用户确认后进入渐进式推荐；非必要字段不阻塞 |

回退只改变需求解析方式，不改变后续推荐、文化内容或需求单规则。

## 测试与验收

| 验收要求 | 对应测试 |
|---|---|
| 预算、数量、交期和目的地可解析 | `tests/test_request_parser.py::test_chinese_demo_parser_extracts_budget_quantity_and_delivery` |
| 总预算确定性换算并保留原值 | `test_total_budget_is_converted_to_per_item_and_preserved` |
| 未表达字段不编造 | `test_unstated_fields_are_not_invented`、AppTest 的 `test_confirmation_does_not_invent_unstated_select_fields` |
| 详细表单不预选未表达事实 | AppTest 的 `test_precise_form_does_not_preselect_unstated_customer_facts` |
| 模糊预算进入不确定字段并提出问题 | `test_approximate_budget_is_uncertain_and_asks_question` |
| 不确定字段不能直接进入已确认业务请求 | `test_uncertain_fields_cannot_enter_confirmed_business_request` |
| 无 Key 和超时安全回退 | `test_no_api_key_uses_demo_mode`、`test_timeout_safely_falls_back_to_demo_mode` |
| 模型结果不能绕过硬过滤 | `test_parsed_request_cannot_bypass_global_hard_filters`、`test_parsed_logo_and_shipping_requirements_remain_hard_filters` |
| 本地合并第二轮字段 | `tests/test_dialogue_manager.py::test_second_turn_merges_new_fields_instead_of_restarting` |
| Streamlit 支持第二轮补充 | `tests/test_app_smoke.py::test_confirmation_supports_a_second_conversation_turn` |
| 每轮最多一个高价值问题且不阻塞推荐 | `test_budget_and_quantity_are_asked_in_one_high_value_question`、`test_optional_preferences_do_not_block_recommendation` |
| 相同签名不重复推荐 | `test_same_signature_does_not_repeat_recommendation` |
| 自动化测试阻断真实 API | `tests/conftest.py::block_real_deepseek` |

建议执行：

```powershell
python -m pytest tests/test_request_parser.py tests/test_dialogue_manager.py tests/test_llm_client.py
```

2026年7月17日全量 pytest 实测为 `106 passed in 12.01s`；完整环境与命令记录见 `docs/wave2/EVALUATION.md`。

当前 `tests/test_app_smoke.py` 已操作“合并这条补充”，并检查第二轮数量、预算、对象、场景和会话原文数量。2026年7月21日交叉评测前仍应记录该 UI 路径的实际执行结果和人工观察。

## 当前限制与非目标

- 当前确定性演示解析只覆盖有限正则和关键词，不等同于通用自然语言理解。
- 当前 Streamlit 提供 session 内多轮补充和历史展示，但使用 `st.text_input` 加显式合并按钮，不是带账号、长期历史和生产级治理的完整聊天平台。
- 不保存账号、跨设备记录或长期对话历史。
- 不收集完成推荐不需要的姓名、电话或邮箱。
- 本 Skill 不实现 RAG、知识检索、商品推荐、文化事实生成或订单处理。

## Specs 映射

- `docs/PRODUCT_SPEC.md`：§4 中需求解析和对话补充相关内容、§7 用户输入、§10 AI 边界、§12 对话与问题、§13.1 回退、§16.1 需求解析。
- `docs/DATA_SCHEMA.md`：§7 `parsed_customer_request`、§8 `conversation_state`。
- `docs/ARCHITECTURE.md`：§3 端到端数据流、§4 对话理解与本地权威状态、§9 测试架构。
- `docs/WAVE2_SKILLS.md`：Skill 1 摘要；本文件为本轮详细提交契约。
