# 飞颐礼遇 MVP 架构设计

## 1. 架构原则

采用一个本地可运行的 Streamlit 单体应用。UI 只负责收集和展示；数据校验、推荐、文案和需求单生成均放在纯 Python 模块中。所有决策由版本化规则和结构化数据产生，结果可复现、可单测、可逐项解释。

## 2. 推荐目录结构

```text
feiyi-heritage-ai/
├── AGENTS.md
├── app.py                         # Streamlit 详细表单与对话顾问入口
├── pyproject.toml                 # 依赖、ruff、pytest 配置（阶段 1 创建）
├── README.md                      # 安装、运行与项目边界说明
├── CONTRIBUTING.md                # 比赛原始文件，不修改
├── SUBMISSIONS.md                 # 自动维护，不手动修改
├── submissions.json               # 自动维护，不手动修改
├── .forgejo/                      # 比赛工作流，不修改
├── data/
│   └── demo/
│       ├── merchants.csv
│       ├── heritage_items.csv
│       ├── products.csv
│       ├── product_texts.csv
│       └── customization_options.csv
├── src/
│   └── heritagelink/
│       ├── __init__.py
│       ├── config.py              # DeepSeek 环境配置，不含业务逻辑
│       ├── conversation_state.py  # 不可变多轮会话状态
│       ├── dialogue_prompt.py     # 对话 JSON 提取约束
│       ├── dialogue_manager.py    # 合并、澄清、就绪与签名策略
│       ├── llm_client.py          # OpenAI-compatible 客户端与安全错误映射
│       ├── request_parser.py      # 解析、确定性回退、本地校验与需求转换
│       ├── models.py              # TypedDict/dataclass 与枚举
│       ├── data_loader.py         # pandas 加载、规范化、校验
│       ├── recommender.py         # 硬过滤、评分、排序、解释
│       ├── content.py             # 中英文模板化文化内容
│       ├── inquiry.py             # 定制需求单构造与校验
│       └── customization_concept.py # 无产品结果的定制概念
├── tests/
│   ├── fixtures/
│   │   ├── golden_requests.json
│   │   └── invalid_data/
│   ├── test_data_loader.py
│   ├── test_recommender.py
│   ├── test_content.py
│   ├── test_inquiry.py
│   ├── test_dialogue_manager.py
│   ├── test_customization_concept.py
│   └── test_app_smoke.py
└── docs/
    ├── PRODUCT_SPEC.md
    ├── ARCHITECTURE.md
    ├── DATA_SCHEMA.md
    ├── IMPLEMENTATION_PLAN.md
    ├── RECOMMENDATION_DESIGN.md
    └── WAVE2_SKILLS.md
```

该结构中的核心应用文件已经实现；正式数据库、账号和商家后台仍不在当前范围。

## 3. 组件职责与数据流

1. `config` 只读取 DeepSeek 环境变量并判断是否配置 Key，不输出密钥。
2. `llm_client` 封装 OpenAI-compatible 请求、一次受控重试和安全错误映射。
3. `request_parser` 将 DeepSeek JSON 或确定性规则结果校验为统一 `parsed_customer_request`；总预算换算也在此完成。
4. Streamlit 展示累计解析字段，并立即调用渐进式推荐适配层；补充问题不阻止当前推荐。
5. `data_loader` 读取五个 CSV，校验类型、枚举、唯一性、外键和业务范围。
6. `progressive_recommender` 只把已知约束传给 `recommender`，计算推荐模式、覆盖度、归一化匹配分和替代建议。
7. `recommender` 执行不可绕过的明确硬约束、八维基础评分和稳定排序，不调用 DeepSeek。
8. `content` 只使用产品数据库和模板中的事实；缺失事实显示“待商家确认”。
9. `inquiry` 将需求、推荐快照和开放问题组装为 JSON。
10. Streamlit 使用 session state 保存当前会话状态，不持久化客户身份或订单。

## 4. 系统边界与信任边界

- 浏览器与 Streamlit 会话：输入均视为不可信，限制长度、枚举和数值范围，并对展示文本使用框架默认转义。
- 本地演示数据：加载时必须校验；`is_demo=true` 和数据版本必须传递到页面与导出。
- 文件导出：仅在内存中生成 JSON；文件名使用系统生成的 `inquiry_id`，不拼接用户输入。
- 网络：只有用户选择自动智能解析且本地配置 DeepSeek Key 时才调用 DeepSeek；无网络或无 Key 时回退演示解析，其他核心流程不依赖外部服务。

## 5. 推荐引擎

### 5.1 规范化

- 预算统一为 CNY 分；总预算除以数量得到单件预算区间，除法向保守方向取整。
- 标签统一为受控小写 snake_case 集合；缺省偏好为空集合，表示该维度不加偏好而不是自动命中。
- 日期转换为可用制作天数；没有日期则交期维度记中性分并列为待确认。

### 5.2 硬过滤

按顺序记录淘汰原因：

1. `status != active`；
2. `price_min_fen > unit_budget_max_fen`，即最低演示单价超过用户绝对单件预算；
3. `quantity < min_order_qty` 或超过非空的 `demo_max_order_qty`；
4. 用户要求必须定制但产品没有启用的定制选项，或必需定制类型不受支持；
5. 用户要求必须加入 Logo，但产品没有启用 `logo` 定制选项；
6. 用户给出交付日期，且可用天数小于有效制作周期。有效制作周期为 `lead_time_days` 加上所选必需定制项中最大的 `extra_lead_days`；
7. 海外运输为必要条件，但 `supports_international_shipping=false`。

只有用户明确提供的预算、数量、定制、Logo、交期和海外运输条件才启用相应过滤。未知字段不执行过滤，也不作为不匹配。若全部淘汰，返回无完全匹配产品、各原因计数、调整建议及独立替代方案，不绕过已知硬约束。

### 5.3 加权评分

每个已知维度先得到 0–1 的 `match_ratio`，再乘基础权重。渐进式适配层只用参与维度归一化为 0–100 的当前匹配分；未知维度显示为未参与。

| 维度 | 权重 | match_ratio 规则 |
|---|---:|---|
| budget | 25 | 产品价格区间完全落入用户单价区间为 1；区间有交集为 0.8；仅最低价可承受为 0.5；否则已被过滤 |
| recipient | 15 | 用户标签与产品标签交集数 / 用户标签数；产品含 `universal` 时最低为 0.5；用户未选为 0.5 |
| occasion | 15 | 同 recipient，使用 `occasion_tags` |
| style | 15 | 同 recipient，使用 `style_tags`；用户未选为 0.5 |
| cultural_meaning | 10 | 同 recipient，使用 `meaning_tags`；用户未选为 0.5 |
| customization | 10 | 无定制需求为 1；所有偏好均支持为 1；部分支持为 0.5；必需项不支持已被过滤 |
| quantity | 5 | 数量在 `[min_order_qty, recommended_max_qty]` 为 1；超过建议量但未超过演示上限为 0.5；建议量为空时为 0.5 并待确认 |
| lead_time | 5 | 交期充足且余量至少 20% 为 1；刚好可行为 0.7；未提供日期为 0.5；不可行已被过滤 |

`recommended_max_qty` 或 `demo_max_order_qty` 为空时不假设无限履约：评分可行但必须添加“产能待确认”。所有比例限制在 `[0, 1]`。

### 5.4 排序与解释

- 按 `total_score desc, product_id asc` 排序，最多返回 3 件。
- 推荐理由由最高的 2–3 个且与用户已选偏好相关的维度模板组成；不能把中性分包装为命中。
- 风险说明来自预算边缘、交期余量小、超建议数量、产能/物流未知和未审核内容等结构化标记。
- UI 展示当前匹配分、信息覆盖度、置信度和全部八维状态，避免把未知信息包装成命中。

## 6. 双语内容策略

`product_texts.csv` 保存 `zh-CN` 和 `en` 两行内容及审核状态。展示模板由产品名、工艺摘要、文化含义、适用场景和来源说明组成。只有 `review_status=approved` 的事实可作为确定陈述；`draft` 可在演示中展示但必须标注“演示文案，待商家审核”。英文是独立审核字段，不在运行时调用机器翻译。

## 7. 错误与降级

- 数据 schema 错误：启动时阻断并显示文件、行/ID、字段和修复建议。
- 无推荐：显示硬过滤原因分布和可调整条件，不降低必需约束。
- 单一语言缺失：不自行翻译，显示待补充并使数据质量测试失败。
- 导出失败：保留页面预览，显示可操作错误，不输出部分 JSON。

## 8. 未来演进点

未来可将 DataFrame 仓储替换为数据库、将规则引擎替换/增强为学习排序或大模型服务、增加商家后台和多语言内容工作流。接口应继续围绕 `gift_request -> recommendation_result[] -> customization_inquiry`，避免 UI 依赖底层存储。任何模型增强都应保留硬约束层、规则基线和解释审计记录。

## 9. 第三阶段解析层

新增 `llm_client.py` 和 `request_parser.py`。数据流为：用户原文 → DeepSeek 或确定性演示解析 → 本地严格校验 → 用户修改确认 → `GiftRequest` → 原推荐引擎。Streamlit 不持有 API 客户端业务逻辑，推荐引擎也不调用模型。

DeepSeek 配置只从环境读取，使用 JSON 输出和非思考模式，瞬时故障最多安全重试一次。认证、余额、超时、网络、空响应和非法 JSON 均转换为不含密钥或底层堆栈的安全错误；应用随后使用明确标记的演示解析模式。无密钥、无网络时，详细表单仍可完整运行。

### 9.1 Wave 2 状态机

```text
连续对话或详细表单
→ 结构化需求累计
→ 探索、引导或约束推荐
→ 明确硬约束过滤与已知维度评分
→ 可选补充问题
→ 双语文化内容
→ 定制需求单
```

对话会话保存各轮原文、消息、累计校验结果、澄清轮数、推荐签名、推荐结果和当前选中产品。参与推荐的字段变化时签名改变并重新推荐；签名不变时保留旧结果。

### 9.2 本阶段边界

本阶段不实现 RAG、向量数据库、AI 语义重排、数据库持久化或商家自助入驻。产品文化事实只来自本地产品数据和模板；DeepSeek 只提取客户明确表达的需求字段。
## 对话式顾问增量架构（当前实现）

当前页面保留详细表单，并新增由 Streamlit session state 驱动的多轮顾问：

```text
st.chat_input / st.chat_message
  → conversation_state.py（不可变会话状态）
  → dialogue_manager.py（字段合并、一次一个可选问题、需求签名）
  → llm_client.py（可选 DeepSeek JSON；失败回退）
  → request_parser.py（不可信输出本地校验）
  → progressive_recommender.py（模式、覆盖度、未知字段和替代建议）
  → GiftRequest
  → recommender.py（明确硬过滤、基础权重、排序保持不变）
```

`dialogue_manager.py` 是对话策略的权威边界。模型返回的 `ready_to_recommend` 和
`recommended_action` 不得直接控制业务；任意非空用户需求都可以得到当前推荐。交期、Logo、
国际运输等一旦被用户明确为硬要求，仍原样交给推荐引擎过滤。所有缺失字段只影响推荐模式、
信息覆盖度、置信度和待补充提示。

会话以需求字段的稳定哈希作为推荐签名，同一签名不会重复调用推荐器。对话只保存在当前
session，不写数据库。无产品时 `customization_concept.py` 可生成独立的概念需求对象；它不含
现有产品身份，并强制声明待商家确认。
