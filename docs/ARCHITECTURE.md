# 飞颐礼遇 MVP 架构设计

## 1. 当前架构目标

飞颐礼遇使用一个可本地运行的 Streamlit 单体应用验证交易前礼赠匹配流程。UI 只负责编排输入、确认和展示；字段校验、对话累计、推荐、内容组织和需求单构造位于可独立测试的 Python 模块中。

当前架构遵循以下原则：

- DeepSeek 是可选字段提取器，不是推荐决策者；
- 多轮累计、校验、问题选择和推荐就绪状态以本地代码为准；
- 推荐硬约束、固定权重和稳定排序不可由模型或 UI 改写；
- 当前存储是本地 CSV/JSON 和 Streamlit session，不是正式数据库；
- 馆藏参考事实、MVP 商品方案字段和模板表达必须保持可区分；
- 未知客户字段保持未知，不得用推荐内部代理值冒充客户事实；
- 核心流程在没有 API Key 和外部网络时仍可运行。

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
│       ├── content.py                # 本地双语内容组织
│       ├── customization_concept.py  # 无合格方案时的独立概念对象
│       ├── inquiry.py                # InquiryRequestContext 与需求单 JSON
│       └── ui/
│           ├── __init__.py
│           ├── theme.py
│           ├── components.py
│           ├── requirements.py
│           ├── product_card.py
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
    └── wave2/
        ├── README.md
        ├── WORKFLOW.md
        ├── DEMO_CASE.md
        ├── EVALUATION.md
        ├── PR_DESCRIPTION.md
        ├── COMPLIANCE.md
        └── skills/
            ├── 01-conversational-gift-request-understanding.md
            ├── 02-progressive-heritage-gift-recommendation.md
            ├── 03-grounded-bilingual-heritage-content.md
            └── 04-merchant-ready-customization-brief.md
```

`CONTRIBUTING.md`、`SUBMISSIONS.md`、`submissions.json` 和 `.forgejo/` 是比赛基线或自动化文件，不属于业务模块。

## 3. 端到端数据流

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
- 4 个 `unverified` 工艺分类；
- 20 件带图 MVP 礼赠方案；
- 40 条中英文文化资料，全部为 `review_status=draft`；
- 43 条 MVP 定制选项。

方案价格、数量、交期、运输和定制能力均为 MVP 演示字段，需要商家复核，不是正式报价或产能承诺。

### 6.2 开放馆藏参考

`data/catalog/heritage_products.csv` 保存馆藏来源页面、历史元数据、图片许可、本地路径和 `museum_reference_not_for_sale` 状态。馆藏原物只作图片、工艺和文化资料参考，不作为平台商品出售，也不用于推断方案价格、产能、交期、运输或定制能力。

### 6.3 双语内容

`product_texts.csv` 为每件方案保存 `zh-CN` 和 `en` 两条本地资料。`content.py` 只组织这些字段和来源说明：

- `approved` 才能表示已完成相应审核；
- `draft` 必须显示“演示文案，待商家审核”；
- 缺失字段显示“待商家确认 / Pending merchant confirmation”；
- 当前 40 条资料全部为 `draft`，不得称为商家已审核内容；
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
- 数据与来源：`test_data_loader.py`、`test_catalog.py`、`test_catalog_app.py`；
- 内容与需求单：`test_content.py`、`test_inquiry.py`、`test_customization_concept.py`；
- 端到端 UI：`test_app_smoke.py`；
- 导入边界：`test_imports.py`。

`tests/conftest.py` 自动设置占位 Key，并把真实 OpenAI-compatible completion 调用替换为立即失败的守卫。因此任何意外外部 API 调用都会使测试失败，而不会产生真实费用。

`tests/evaluation_cases.json` 是确定性回归集合，不是商家或领域专家标注的排行榜数据集。实际命令和人工冒烟结果以 `docs/wave2/EVALUATION.md` 为准。

## 10. 当前系统边界与未来演进

本轮不包含 RAG、向量数据库、正式数据库、商家自主入驻、多商家后台、用户账号、支付、物流、税务、正式订单或生产级权限审核体系。

未来可以在真实商家和用户验证后增加正式存储、商家工作台、带来源的检索和模型辅助草稿，但必须继续保留：

- 明确硬约束层；
- 当前确定性规则基线；
- 来源、审核和演示状态；
- 未知客户事实不被代理值覆盖；
- 可复现的测试和审计记录。
