# 飞颐礼遇 MVP 架构设计

## 1. 当前架构目标

飞颐礼遇使用一个可本地运行的 Streamlit 单体应用验证交易前礼赠匹配和手艺人资料整理流程。Buyer 是默认模式，Artisan Studio 通过顶部切换或 `?mode=artisan` 进入；两者共用应用壳层，但不共用业务 Repository。UI 只负责输入、session 写回和展示；统一 Agent 编排器负责 Buyer 路径的调用顺序、门控和回退；字段校验、对话累计、推荐、内容组织和需求单构造位于七个可独立测试的薄包装 Skill 之后。

当前客户层为单页面聊天式顾问，领域层仍维持确定性推荐边界。新增 `inference_policy`/`recommendation_context` 分离用户陈述与软偏好推断，新增 `analytics`、`analytics_models` 和 `repositories` 分离 UI 与匿名事件存储。

当前架构遵循以下原则：

- DeepSeek 是可选字段提取器，不是推荐决策者；
- 多轮累计、校验、问题选择和推荐就绪状态以本地代码为准；
- 推荐硬约束、固定权重和稳定排序不可由模型或 UI 改写；
- 产品主数据仍是本地 CSV；当前会话使用 Streamlit session；经用户授权的匿名选择事件可使用本地 SQLite 或云端 PostgreSQL；
- Artisan 草稿使用独立的内存或 SQLite Repository，不写入 Buyer 匿名分析表，也不自动写入产品 CSV；
- 馆藏参考事实、MVP 商品方案字段和模板表达必须保持可区分；
- 每项 Artisan 事实分别记录来源和核验状态；AI 候选必须经逐项人工确认；
- 未知客户字段保持未知，不得用推荐内部代理值冒充客户事实；
- 核心流程在没有 API Key 和外部网络时仍可运行。
- 数据库未配置或写入失败时不影响推荐、选择和方案下载。

### 1.1 当前单页面数据流

```text
Streamlit UI
→ shopping_turn_router（仅在已有推荐时识别比较/调整/选择）
→ agent_orchestrator.run_agent_turn
→ AgentTurnResult

需求或调整 → Skills 1–3：需求理解、受控推断、稳定推荐
当前推荐比较 → ProductComparisonService（application layer；七项 Skill 保持原合同）
选品与方案 → Skills 4–5：可靠内容与最终方案
授权记录 → Skill 6：明确授权后匿名记录（无授权/故障不阻断）

显式离线入口 → Skill 7：匿名聚合指标（不回写推荐权重）
```

`agent_trace.safe_summary` 是唯一 Trace 摘要边界；评审模式同时要求环境开关与 `review_mode=1`，公开模式不渲染技术轨迹。完整设计见 [`wave3/ORCHESTRATION.md`](wave3/ORCHESTRATION.md)。

Repository 不接收完整聊天原文。推荐事件使用会话 ID 与推荐签名生成稳定 UUID，选择事件使用推荐事件与产品 ID 生成稳定 UUID；数据库约束和 upsert 共同抵御 Streamlit rerun 重复写入。

记录服务返回结构化安全状态；数据库错误被截断在分析边界内。选择信号分析由独立 CLI 或服务调用，不出现在公开客户 UI，也不自动影响线上推荐。

### 1.2 AI Shopping 应用层

`RequestedAction` 继续是唯一用户动作模型，并在兼容原动作的前提下支持：

- `compare_recommendations`：比较当前全部正式推荐；
- `compare_selected_products`：比较当前推荐中的指定序号范围；
- `refine_recommendations`：把相对偏好更新送回现有 Skills 1–3；
- `explain_difference`：解释当前推荐差异，不重新执行推荐；
- `select_product`：自然语言选品继续复用现有 Skills 4–6 路径。

`shopping_turn_router` 位于 Skill 1 之前，只解析已有推荐上下文中的序号与动作意图。它不读取商品事实、不计算分数，也不创建新的会话状态机。没有当前推荐时，消息保持 `continue_conversation`，照常进入 Skill 1。

比较动作仍调用 `run_agent_turn(...)`。编排器把该动作交给 application-layer `ProductComparisonService`，并在正式七项 `execution_trace` 中明确记录各 Skill 未执行；结构化比较及其安全信息另存为 `application_trace`。因此 `AgentTurnResult.execution_trace` 的七项 Skill 合同与 Agent manifest 均未改变。

比较服务的信任链为：

```text
current ProgressiveRecommendationResult allowlist
→ full Product lookup
→ catalog_role == recommendation_demo
→ product / merchant / heritage status == active
→ original recommendation order
→ Structured ProductComparisonResult
→ optional injected grounded narration or deterministic fallback
```

双重校验阻止被伪造的推荐快照、失效商品和 30 件 `inactive/catalog_reference` 进入正式比较。服务不创建比较分或新排名；调用方即使交换 `product_ids` 顺序，输出仍按原推荐顺序排列。

每个可展示事实由 `ComparisonEvidence` 承载，并使用四态 `EvidenceState`：`verified_yes`、`verified_no`、`unknown`、`not_applicable`。价格、定制、数量、工期、便携性和国际运输都先检查相应事实状态；缺少可靠来源时保留为 `unknown`，不能从非空演示字段推断为已确认，也不能把缺失值显示为否定事实。

可选语言叙述通过依赖注入进入 `ProductComparisonService`，只接收脱敏后的结构化比较。叙述异常或安全校验失败时，服务返回预先生成的 deterministic summary。当前编排器在未注入叙述客户端时自然使用该确定性回退，核心比较不依赖 API 或网络。

`AgentSessionState` 保存当前 `comparison_result` 和最多最近三次 `comparison_history`。它们只存在于当前 Streamlit session；重新开始会清空，现有匿名选择 consent 不会触发比较历史持久化。

### 1.3 Artisan Studio 与 Heritage Passport 应用层

Artisan Studio 不经过 `run_agent_turn(...)`，也不注册新 Skill。它使用独立 application action `artisan_product_onboarding` 记录脱敏轨迹，并通过本地服务完成：草稿创建、候选字段提取、双语草稿、冲突检测、逐项人工确认、Heritage Passport 构造和提交审核。

```text
Artisan Streamlit mode
→ ArtisanProductDraft（独立 session 草稿）
→ optional extraction/writing client or deterministic fallback
→ ProvenancedFact + BilingualProductDraft
→ explicit field-level human confirmation
→ HeritagePassport
→ ArtisanDraftRepository
→ pending_review
```

`FactSource` 与 `VerificationStatus` 是正交维度。`artisan_provided` 只表示输入来源，不能自动成为 `confirmed`；`ai_inferred` 永远不能直接确认。价格、材料、定制、最低起订量、运输和交期发生不一致时生成 `FactConflict`，在用户明确选择解决值之前禁止提交。

发布状态为 `draft → pending_review → reference_only/recommendable/archived`。提交只进入 `pending_review`。评审模式的模拟审核不会把草稿转换成 canonical `Product`，也不会修改 CSV。生产环境还需要一条有身份、商家、来源和商业能力审核的显式发布事务。

Skill 3 前的统一资格门控只接受逻辑发布状态为 `recommendable` 的 canonical 产品。为保持现有 CSV 合同不变，资格适配层把 `recommendation_demo` 且产品、商家与工艺状态均为 `active` 的记录视为 legacy `recommendable`，把 `catalog_reference/inactive` 视为 `reference_only`。因此 `draft`、`pending_review`、`reference_only`、`archived` 和所有未显式接入目录的 Artisan 记录都被排除。23 条正式演示推荐、30 条参考、1 条合作方待核验、54 条 canonical 总数保持不变。

## 2. 当前仓库结构

以下为当前实现使用的主要文件，不包含 `.git`、缓存、虚拟环境和比赛自动化内部文件：

```text
feiyi-heritage-ai/
├── app.py
├── pyproject.toml
├── README.md
├── AGENTS.md
├── data/
│   ├── demo/
│   │   ├── merchants.csv
│   │   ├── heritage_items.csv
│   │   ├── products.csv
│   │   ├── product_texts.csv
│   │   └── customization_options.csv
│   └── catalog/
│       └── heritage_products.csv
├── assets/
│   └── catalog/
│       └── products/                 # 20 张本地馆藏参考图
├── src/
│   └── heritagelink/
│       ├── __init__.py
│       ├── config.py                 # DeepSeek 环境配置
│       ├── llm_client.py             # OpenAI-compatible 调用与安全错误映射
│       ├── dialogue_prompt.py        # 受控 JSON 提取约束
│       ├── conversation_state.py     # session 内不可变会话状态
│       ├── dialogue_manager.py       # process_turn、合并、问题和签名
│       ├── request_parser.py         # 解析、本地校验、确定性回退和转换
│       ├── models.py                 # 领域数据类型和枚举
│       ├── data_loader.py            # 五个 demo CSV 的加载与校验
│       ├── catalog.py                # 开放馆藏参考目录和图片校验
│       ├── recommender.py            # 硬过滤、八维基础评分和稳定排序
│       ├── progressive_recommender.py # 渐进模式、覆盖度和已知维度归一化
│       ├── catalog_eligibility.py      # Skill 3 与比较共享的正式资格门控
│       ├── comparison_models.py       # 比较 schema、EvidenceState 与 Application trace
│       ├── product_comparison.py      # application-layer 结构化比较与叙述回退
│       ├── shopping_turn_router.py    # 推荐后的比较、调整与序号选品路由
│       ├── heritage_passport_models.py # 事实来源、核验、发布状态与文化护照
│       ├── heritage_passport.py      # canonical Product 到文化护照的保守适配
│       ├── artisan_studio.py           # 草稿、AI 回退、冲突、确认和提交审核
│       ├── repositories/
│       │   ├── memory_artisan_draft_repository.py
│       │   └── sqlite_artisan_draft_repository.py
│       ├── content.py                # 本地双语内容组织
│       ├── customization_concept.py  # 无合格方案时的独立概念对象
│       ├── inquiry.py                # InquiryRequestContext 与需求单 JSON
│       └── ui/
│           ├── __init__.py
│           ├── theme.py
│           ├── components.py
│           ├── requirements.py
│           ├── product_card.py
│           ├── comparison.py
│           ├── artisan_studio.py
│           ├── heritage_passport.py
│           ├── catalog_gallery.py
│           └── inquiry_summary.py
├── tests/
│   ├── conftest.py                   # 阻断真实 DeepSeek 网络请求
│   ├── evaluation_cases.json         # 14 个确定性回归案例
│   ├── fixtures/
│   │   └── README.md
│   ├── test_app_smoke.py
│   ├── test_catalog_app.py
│   ├── test_catalog.py
│   ├── test_content.py
│   ├── test_customization_concept.py
│   ├── test_data_loader.py
│   ├── test_dialogue_manager.py
│   ├── test_imports.py
│   ├── test_inquiry.py
│   ├── test_llm_client.py
│   ├── test_progressive_recommender.py
│   ├── test_recommender.py
│   └── test_request_parser.py
└── docs/
    ├── PRODUCT_SPEC.md
    ├── ARCHITECTURE.md
    ├── DATA_SCHEMA.md
    ├── IMPLEMENTATION_PLAN.md
    ├── RECOMMENDATION_DESIGN.md
    ├── WAVE2_SKILLS.md
    ├── wave2/
    │   ├── README.md
    │   ├── WORKFLOW.md
    │   ├── DEMO_CASE.md
    │   ├── EVALUATION.md
    │   ├── PR_DESCRIPTION.md
    │   ├── COMPLIANCE.md
    │   └── skills/
    │       ├── 01-conversational-gift-request-understanding.md
    │       ├── 02-progressive-heritage-gift-recommendation.md
    │       ├── 03-grounded-bilingual-heritage-content.md
    │       └── 04-merchant-ready-customization-brief.md
    └── wave4/
        ├── AI_SHOPPING.md
        ├── ARTISAN_STUDIO.md
        └── HERITAGE_PASSPORT.md
```

`CONTRIBUTING.md`、`SUBMISSIONS.md`、`submissions.json` 和 `.forgejo/` 是比赛基线或自动化文件，不属于业务模块。

## 3. 端到端数据流

### 3.1 Buyer 数据流

```text
自然语言首轮、连续补充或详细表单
  → dialogue_manager.process_turn / request_parser
  → 本地校验后的 ParsedCustomerRequest
  → 用户在确认页修订并确认
  → progressive_recommender.recommend_progressively
  → recommender.recommend
  → 0–3 件合格 MVP 演示方案，或明确的无结果与冲突
  → content.generate_bilingual_content
  → InquiryRequestContext + build_customization_inquiry
  → 页面预览、复制和 UTF-8 JSON 下载
```

组件职责如下：

1. `config` 只读取 DeepSeek 环境变量并判断 Key 是否有效，不向页面或日志输出密钥。
2. `llm_client` 请求受控 JSON，禁用思考模式，对瞬时错误最多重试一次，并将认证、余额、超时、网络、空响应和非法 JSON 转换为安全错误。
3. `dialogue_manager.process_turn` 处理首轮和后续补充，调用可选模型或确定性解析器，再由本地代码合并字段、选择至多一个问题、计算覆盖度和需求签名。
4. `request_parser` 对不可信提取结果执行字段白名单、类型、枚举、金额和交叉字段校验；总预算换算由本地十进制逻辑完成。
5. `app.py` 在确认页的展开区用 Markdown 展示当前 session 的历史，并通过显式“合并这条补充”按钮提交下一轮；详细表单仍是完整回退入口。
6. `data_loader` 读取五个 `data/demo` CSV，校验列、类型、主键、外键、枚举、金额、数量、双语行、图片和演示声明。
7. `catalog` 读取开放馆藏参考目录，校验来源 URL、许可、本地图片和 `demo_product_id` 一一关联。
8. `progressive_recommender` 只把已知约束传给基础推荐器，计算探索/引导/约束模式、信息覆盖度、置信度、参与维度和独立替代建议。
9. `recommender` 执行不可绕过的硬过滤、八维基础评分和稳定排序，不调用 DeepSeek。
10. `content` 只组织本地中英文资料、来源和审核状态，不在运行时机器翻译或补写事实。
11. `InquiryRequestContext` 保存客户实际确认的信息；未知预算、数量、定制、Logo、运输和交期保持 `None`。
12. `inquiry` 将客户上下文、一个选中方案快照、双语内容和开放问题构造为 JSON，并在下载前校验。
13. `shopping_turn_router` 只在当前推荐存在时把比较、差异解释、相对偏好调整和序号选品映射到已有 `RequestedAction`。
14. `product_comparison` 读取当前 `ProgressiveRecommendationResult`、`RecommendationContext` 与完整目录快照，执行 allowlist 和正式资格复核后构造结构化比较；它不调用推荐器或重排结果。
15. `ui.comparison` 把同一结构化结果渲染为桌面列式矩阵与移动卡片；客户层不显示技术分数、内部 ID 或叙述来源。
16. `ApplicationExecutionTrace` 只在评审模式作为独立 Application Action 展示，和固定七项 `SkillExecutionTrace` 分开。

### 3.2 Artisan 数据流

1. `app.py` 根据顶部模式切换或 `mode=artisan` 渲染同一 Streamlit 应用内的 Artisan Studio；默认仍为 Buyer。
2. `ArtisanProductDraft` 保存不完整作品资料、可选图片、双语草稿、冲突与发布时间戳。
3. `artisan_studio` 只把模型输出当作候选，经字段白名单和本地校验后写为 `ai_inferred/pending_review`；模型失败时使用确定性回退。
4. `confirm_facts` 只升级用户本次明确选择的字段为 `artisan_confirmed/confirmed`，双语草稿单独确认。
5. `build_passport` 分开汇总文化与商业核验状态；未知商业条件保持未知，不能显示为不支持。
6. `submit_for_review` 拒绝未解决冲突，将草稿写入独立 `ArtisanDraftRepository` 并设为 `pending_review`。
7. 模拟审核只演示状态变化，不向 Buyer 产品主数据或匿名分析 Repository 写入记录。

## 4. 对话理解与本地权威状态

### 4.1 模型边界

DeepSeek 只提供候选结构化字段。模型返回的 `ready_to_recommend`、`recommended_action`、问题或置信信息不能直接控制业务状态。以下行为由本地代码决定：

- 合并新旧字段；
- 拒绝未知字段、非法类型和非法枚举；
- 总预算换算；
- 已知、缺失和不确定字段；
- 问题优先级和每轮至多一个问题；
- 推荐签名和是否需要重新计算；
- 所有产品资格、分数和排序。

无 Key 或模型调用失败时，`demo_parse_request` 提供明确标记的有限关键词与正则解析。该降级只改变字段提取方式，不改变后续推荐、内容或需求单逻辑。

### 4.2 ConversationState

`ConversationState` 在当前 Streamlit session 内保存：

- `conversation_id`、可显示消息和各轮原文；
- 本地校验后的 `accumulated_request`；
- 缺失必要字段、缺失可选字段和不确定字段；
- 当前至多一个补充问题；
- 当前阶段、覆盖度和澄清轮数；
- 用户明确字段和上次推荐签名。

补充输入经过 `process_turn` 后生成新的不可变状态。会话不写入正式数据库，不提供账号、跨设备同步或长期历史记录。

## 5. 推荐引擎

### 5.1 渐进式输入

用户未提供预算、数量或偏好时，渐进式适配层可以为每件方案构造只用于基础推荐器运行的内部代理值。这些值不得写入用户摘要或需求单。真正的客户事实仍来自 `ParsedCustomerRequest` 和 `InquiryRequestContext`。

推荐模式为：

- `exploring`：没有足够的个性化字段，展示当前目录方向；
- `guided`：对象、场景、风格或寓意等部分偏好已知；
- `constrained`：预算、数量、定制、Logo、交期或国际运输等硬条件已知。

### 5.2 明确硬约束

基础推荐器按顺序检查：

1. 产品、演示主体和工艺分类状态；
2. 最低演示单价不超过用户明确的单件预算上限；
3. 用户数量不低于最低起订量、不超过非空演示上限；
4. 用户明确要求的定制类型受支持；
5. 用户明确要求 Logo 时存在启用的 Logo 选项；
6. 可用交期不短于基础周期加必要定制的最大附加工期；
7. 用户明确要求国际运输时方案允许进入国际运输评估。

除状态外，只有用户明确提供且未标为不确定的字段启用相应过滤。所谓“满足全部明确硬约束”只表示没有违反当前已知必要条件，不代表信息完整、真实在售或商家履约承诺。

### 5.3 固定评分与排序

| 维度 | 基础权重 |
|---|---:|
| 预算匹配 | 25 |
| 赠礼对象 | 15 |
| 使用场景 | 15 |
| 风格偏好 | 15 |
| 文化寓意 | 10 |
| 定制匹配 | 10 |
| 数量与产能余量 | 5 |
| 交付时间余量 | 5 |
| 合计 | 100 |

渐进式层只根据用户已提供的参与维度将基础分归一化到 0–100。未知维度显示“待补充”，不记零分，也不能显示为命中。当前 `Recommendation.total_score` 承载页面展示的归一化当前匹配分；如果没有任何参与维度，纯探索模式使用中性展示分 50，并按 `product_id` 稳定排序。该值不是购买概率、成功率或业务指标。

结果按 `total_score desc, product_id asc` 稳定排序，最多返回 3 件。页面同时展示信息覆盖度、低/中/高置信度和八维状态；置信度只描述信息覆盖，不是购买概率或商家满意度。

### 5.4 无结果

如果没有方案满足全部明确硬约束，合格推荐集合为空。页面展示冲突统计、可调整方向和独立的冲突参考方案，不降低用户硬约束。

`customization_concept.py` 可以构造 `is_existing_product=false` 的独立需求概念。它不得包含虚构产品 ID 或名称，也不等于选中产品的 `customization_inquiry`。

## 6. 数据与内容边界

### 6.1 当前数据集

`data/demo/` 当前包含：

- 1 个平台演示选品主体；
- 11 个工艺分类，其中 10 个 `official_level=unverified`，1 个 `national`（芜湖铁画）；
- 54 件带图目录记录，其中 23 件 `recommendation_demo/active`、30 件 `catalog_reference/inactive`、1 件 `partner_pending_verification/inactive`；
- 108 条中英文文化资料，全部为 `review_status=draft`；
- 51 条 MVP 定制选项。

方案价格、数量、交期、运输和定制能力均为 MVP 演示字段，需要商家复核，不是正式报价或产能承诺。

### 6.2 开放馆藏参考

`data/catalog/heritage_products.csv` 保存馆藏来源页面、历史元数据、图片许可、本地路径和 `museum_reference_not_for_sale` 状态。馆藏原物只作图片、工艺和文化资料参考，不作为平台商品出售，也不用于推断方案价格、产能、交期、运输或定制能力。

### 6.3 双语内容

`product_texts.csv` 为每件目录记录保存 `zh-CN` 和 `en` 两条本地资料。`content.py` 只组织这些字段和来源说明：

- `approved` 才能表示已完成相应审核；
- `draft` 必须显示“演示文案，待商家审核”；
- 缺失字段显示“待商家确认 / Pending merchant confirmation”；
- 当前 108 条资料全部为 `draft`，不得称为商家已审核内容；
- 当前不使用运行时机器翻译、RAG 或模型生成文化事实。

## 7. 商家需求单

推荐器为缺失输入构造的代理 `GiftRequest` 只服务于逐产品计算。`app.py::_inquiry_context` 从用户确认的 `ParsedCustomerRequest` 构造 `InquiryRequestContext`，确保以下未知值保持 `None`：

- 单件和总预算；
- 数量；
- 是否需要定制；
- 是否需要 Logo；
- 是否要求国际运输；
- 可用交期。

`build_customization_inquiry` 接收一个合格推荐、双语内容、展示层详情和客户上下文。输出包含：

- 中英文 MVP 演示声明；
- 用户需求快照和 `pending_fields`；
- 恰好一个选中方案快照；
- 定制、交付和内容字段；
- 商家行动项和开放问题。

页面显示声明、待确认值、可复制摘要和 JSON 下载。当前需求单不是合同、订单、报价、库存、产能或交付承诺。

## 8. 信任边界、错误与降级

- 浏览器输入：限制长度、枚举和数值范围；用户文本不用于构造路径或文件名。
- 模型输出：视为不可信 JSON，必须经过本地白名单和业务校验。
- 本地 CSV：启动时校验；错误应指出文件、行或 ID、字段和修复方向。
- 演示标记：页面全局显示 `MVP 演示数据 / MVP demo data`，需求单同时保存 `is_demo` 和中英文声明。
- 无 Key/API 失败：安全回退确定性解析，详细表单和后续核心流程继续可用。
- 无合格方案：返回零件合格推荐，不强推冲突方案。
- 内容缺失：不自动翻译或补写，显示待确认。
- 需求单校验失败：不输出部分 JSON。

## 9. 测试架构

自动化测试分为：

- 解析与对话：`test_request_parser.py`、`test_llm_client.py`、`test_dialogue_manager.py`；
- 推荐：`test_progressive_recommender.py`、`test_recommender.py`、`evaluation_cases.json`；
- Shopping 路由与比较：`test_shopping_turn_router.py`、`test_product_comparison.py`；
- Artisan 领域、Repository、确认与发布门控：`test_artisan_studio_domain.py`；
- 数据与来源：`test_data_loader.py`、`test_catalog.py`、`test_catalog_app.py`；
- 内容与需求单：`test_content.py`、`test_inquiry.py`、`test_customization_concept.py`；
- 端到端 UI：`test_app_smoke.py`；
- 导入边界：`test_imports.py`。

`tests/conftest.py` 自动设置占位 Key，并把真实 OpenAI-compatible completion 调用替换为立即失败的守卫。因此任何意外外部 API 调用都会使测试失败，而不会产生真实费用。

`tests/evaluation_cases.json` 是确定性回归集合，不是商家或领域专家标注的排行榜数据集。实际命令和人工冒烟结果以 `docs/wave2/EVALUATION.md` 为准。

## 10. 当前系统边界与未来演进

本轮包含同一 Streamlit 应用中的 Artisan Studio 原型、独立草稿 Repository、逐字段来源与确认、Heritage Passport 和发布状态演示；不包含 RAG、向量数据库、生产数据库、真实身份或商家认证、多商家后台、用户账号、支付、物流、税务、正式订单或生产级权限审核体系。

未来可以在真实商家和用户验证后增加正式存储、商家工作台、带来源的检索和模型辅助草稿，但必须继续保留：

- 明确硬约束层；
- 当前确定性规则基线；
- 来源、审核和演示状态；
- 未知客户事实不被代理值覆盖；
- 可复现的测试和审计记录。
# Wave 4 extension: HAHA Growth Studio

The Artisan application now includes a separate Growth Studio state machine:

```text
Heritage Passport -> Market Intelligence -> Strategy -> Creative -> Guardian
                                                       ^              |
                                                       |-- revision --|
```

The revision loop is bounded to two cycles. The implementation reuses the existing
Agent Registry and safe Trace contracts, while keeping the original seven-Skill Buyer
chain unchanged. Campaign storage uses Repository adapters and is isolated from
anonymous Buyer analytics and catalogue publication. See
`docs/wave4/GROWTH_STUDIO.md` for the detailed mapping and safety boundaries.
