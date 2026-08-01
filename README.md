# HAHA｜飞颐礼遇

HAHA 代表 **Help Artisan Happy Again**：让手艺人因被看见、被尊重、获得持续机会而再次绽放笑容。HAHA｜飞颐礼遇，是连接非遗手艺人与全球礼赠及商业机会的 AI 出海平台。平台以“让中国手艺被世界理解、选择与珍藏”为愿景，面向全国 20 万件非遗产品资源的长期数字化连接目标，帮助传统工艺跨越语言、文化与商业沟通门槛。当前可运行 Demo 目录共 50 件：20 件带图推荐方案，以及 30 件带明确来源边界、不可下单且不参与推荐的开放馆藏探索参考。

本项目属于 SynNovator 数字文化赛道（原赛道标识：`track-98`）。

## Wave 3 Submission

第三轮提交材料已按“Agent + Skills + Demo + Specs 证据”重新组织。评审者请从 [Wave 3 最短评审路径](docs/wave3/README.md) 开始；其中包含 Agent 执行闭环、七项 Skills 编排、可复现 Demo、Specs 证据矩阵和评测命令。

Agent Orchestration：Streamlit 客户页只调用统一 `run_agent_turn` 入口，由七项正式 Skills 完成带门控执行、安全回退和仅评审可见的脱敏 Trace。机器清单见 [`agent_manifest.yaml`](docs/wave3/agent_manifest.yaml)，实现与四条轨迹见 [`ORCHESTRATION.md`](docs/wave3/ORCHESTRATION.md)。

- Live Demo：`<LIVE_DEMO_URL>`
- Review Mode：`<REVIEW_MODE_URL>`
- Demo Video：`<DEMO_VIDEO_URL>`
- 部署指南：[`STREAMLIT_DEPLOYMENT.md`](docs/wave3/STREAMLIT_DEPLOYMENT.md)
- 浏览器验收：[`BROWSER_ACCEPTANCE.md`](docs/wave3/BROWSER_ACCEPTANCE.md)
- 提交文本与清单：[`SUBMISSION_TEXT.md`](docs/wave3/SUBMISSION_TEXT.md) · [`SUBMISSION_CHECKLIST.md`](docs/wave3/SUBMISSION_CHECKLIST.md)

```text
Streamlit UI → Agent Orchestrator → Skills 1–6 带门控客户链 → AgentTurnResult
授权匿名事件 → Skill 7 离线按需聚合（不自动修改推荐）
```

七项 Skills：需求理解、受控软偏好推断、稳定礼品推荐、可靠双语内容、最终方案、匿名授权记录和匿名信号分析。2026-08-01 发布收口验收为 Ruff 全部通过、`164 passed`；真实浏览器结果见 Wave 3 评测和浏览器验收文档。

最短本地运行：

```powershell
python -m pip install -e .
python -m streamlit run app.py
```

数据和隐私：50件目录中仅20件正式方案参与推荐，30件馆藏参考不进入正式结果；匿名选择默认关闭且不保存完整聊天或联系方式。

## Wave 2 Submission

### Wave 2 Alignment

- 当前阶段：OPC 2026 Youth S3 第二轮 Wave 2。
- 报名并提交截止：2026年7月20日；社区交叉评测：2026年7月21日；晋级结果公布：2026年7月22日。
- 本轮任务：完成产品原型，跑通关键能力；当前交付不是正式商业平台。
- Submitted Skills：
  1. [Conversational Gift Request Understanding / 对话式礼赠需求理解](docs/wave2/skills/01-conversational-gift-request-understanding.md)
  2. [Progressive Heritage Gift Recommendation / 渐进式非遗礼品推荐](docs/wave2/skills/02-progressive-heritage-gift-recommendation.md)
  3. [Grounded Bilingual Heritage Content / 有事实边界的双语文化内容组织](docs/wave2/skills/03-grounded-bilingual-heritage-content.md)
  4. [Merchant-Ready Customization Brief / 商家可执行的定制需求单生成](docs/wave2/skills/04-merchant-ready-customization-brief.md)
- Submitted Workflow：[Conversational Heritage Gift Matching and Customization Workflow / 对话式非遗礼品匹配与定制工作流](docs/wave2/WORKFLOW.md)。
- Prototype：使用 Streamlit 实现的“飞颐礼遇”；安装后运行 `python -m streamlit run app.py`，没有 DeepSeek API Key 时使用确定性演示回退。
- 测试与评测入口：运行 `python -m pytest`，并查看 [测试与评测证据](docs/wave2/EVALUATION.md)。自动化测试会阻断真实外部 API 调用。

不熟悉项目的评审人员可直接从 [Wave 2 最短评审路径](docs/wave2/README.md) 开始，无需先阅读长期商业规划。

## 当前单页面用户流程

```text
用户描述需求 → 顾问每轮提出至多一个问题 → 展示自然语言需求摘要
→ 受控补全非关键偏好 → 同页展示最多 3 件推荐 → 用户选择产品
→ 生成并下载专属礼品方案
```

- 首屏直接显示欢迎语、聊天输入和四个快捷需求，不要求先选择录入模式；
- “我想直接填写需求”保留为次级入口；
- 信息足够、用户要求直接推荐、用户跳过、已完成最多 5 次主动追问或继续追问价值很低时停止追问；
- 风格、文化寓意、包装语气和内容语言可以按集中策略受控补全，用户可通过“调整需求”覆盖；
- 预算、数量、交期、运输、价格、产能、材料、尺寸和定制能力不得推断；
- 硬约束和八维评分权重保持不变，详细评分只在“为什么推荐给我？”中展示；
- DeepSeek 只做可选字段提取，不决定推荐结果，也不能绕过硬性条件；失败状态不在客户主流程中暴露。

页面使用 `st.session_state` 保存当前会话。只有用户主动勾选匿名授权后，系统才会通过独立 Repository 保存结构化偏好、推荐和选择事件；不保存姓名、联系方式或完整聊天原文。

匿名反馈闭环：`capture-consented-choice` 在明确授权后幂等保存匿名选择，`analyze-gift-choice-signals` 再读取这些事件并输出带最小样本保护的聚合信号。分析只提供未来优化依据，不自动修改推荐权重或排序。

## 非遗礼赠产品库

首页可进入“浏览完整礼品目录”。50 件记录均有本地图片、双语名称和来源状态；其中只有原有 20 件 MVP 方案进入演示推荐，新增 30 件开放馆藏记录仅用于跨品类探索，不能下单，也不会进入规则推荐引擎。

- 结构化资料位于 `data/catalog/heritage_products.csv`；
- 网页使用的本地图片位于 `assets/catalog/products/`；
- `data/demo/products.csv` 保存 20 件可推荐 Demo 方案与 30 件 inactive 馆藏参考及对应 `image_path`；
- `data/catalog/heritage_products.csv` 的 `demo_product_id` 将图片来源资料与商品一一关联；
- `source_url`、`image_source_url`、`source_object_number` 和 `image_license` 保存资料出处与使用许可；
- 当前图片来自大都会艺术博物馆开放馆藏，所选页面均标记为 Public Domain，目录按 [The Met Open Access](https://www.metmuseum.org/about-the-met/policies-and-documents/open-access) 记录为 CC0；
- 图片与历史信息作为设计依据；所有价格、数量、交期、运输和定制演示值均标记 `demo_assumption`，不得理解为馆方或商家承诺。来源、覆盖矩阵和审计结论见 [`docs/CATALOG_EXPANSION_REPORT.md`](docs/CATALOG_EXPANSION_REPORT.md)。

未来替换为商家的正式产品图片时，应把文件放入 `assets/products/<merchant_id>/`，再由正式商品数据中的图片路径关联；不要覆盖本目录的馆藏来源图片。

## 安装

需要 Python 3.11 或更高版本。建议在独立虚拟环境中运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## 配置 DeepSeek

在 [DeepSeek 开放平台](https://platform.deepseek.com/)创建 API Key。复制示例配置：

```powershell
Copy-Item .env.example .env
notepad .env
```

把 `.env` 中的占位符替换为自己的 Key：

```dotenv
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

当前默认模型为 `deepseek-v4-flash`。程序使用 DeepSeek 官方 OpenAI 兼容接口和非思考模式，只请求 JSON 字段提取结果。

安全注意事项：

- 不要把真实 Key 写入代码、README、测试、日志或截图；
- 不要提交 `.env`；仓库只保留无密钥的 `.env.example`；
- 如果怀疑 Key 泄露，应立即在开放平台撤销并重新创建；
- 自动化测试全部使用 Mock，不会调用真实 API 或产生费用。

## 启动

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py
```

浏览器通常会打开 `http://localhost:8501`。

### DeepSeek 与安全回退

- 自动模式：存在有效 `DEEPSEEK_API_KEY` 时优先调用 DeepSeek，并由本地代码重新校验、合并和判断推荐就绪状态；
- 回退模式：使用有限的正则和关键词规则，客户主界面继续提供顾问式交互，不显示技术模式或错误细节；
- 没有 API Key、认证失败、余额不足、超时、网络错误或空响应时，系统安全回退到演示模式；
- API 故障不会影响详细表单和原有推荐功能；
- 推荐、文化内容和方案生成不依赖外部模型成功。

## 匿名选择分析配置

默认关闭跨会话分析。启用时使用环境变量或 Streamlit Secrets：

```dotenv
ANALYTICS_ENABLED=true
ANALYTICS_DATABASE_URL=postgresql://user:password@host:5432/database
ANALYTICS_BACKEND=auto
ANALYTICS_STORE_RAW_CHAT=false
APP_VERSION=0.1.0
```

本地开发可使用 `sqlite:///var/analytics/choices.sqlite3`；SQLite 文件已由 `.gitignore` 排除，不适合作为 Streamlit Cloud 跨会话正式存储。云端使用 PostgreSQL/Supabase 兼容连接，数据库不可用时只记录内部日志，不中断推荐流程。`ANALYTICS_STORE_RAW_CHAT` 默认且建议保持 `false`，当前记录模型不包含完整聊天原文。

生成并分析明确标记的本地合成演示数据：

```powershell
python scripts/generate_synthetic_choice_data.py --sessions 50
python skills/analyze-gift-choice-signals/scripts/analyze_choices.py --format table
python skills/analyze-gift-choice-signals/scripts/analyze_choices.py --scene anniversary --format json
```

默认数据库位于 `.local/heritagelink_analytics_demo.db`，不会提交到 Git；所有输出都会说明合成数据不代表真实客户偏好。

## 测试与代码检查

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

Streamlit 冒烟启动：

```powershell
python -m streamlit run app.py --server.headless true
```

## 演示数据

`data/demo/` 包含 1 个平台演示选品主体、4 个 `unverified` 工艺分类、20 件带图商品方案、40 条双语资料和 43 条定制选项。价格、数量、交期、运输和定制能力属于当前方案数据，正式询单时仍需商家复核；仓库不声明真实传承人身份、官方认证级别或政府背书。

## 当前限制

- 当前商品由一个平台演示选品主体统一维护，尚未开放真实商家自助入驻；
- DeepSeek 只提取用户明确表达的字段；对话摘要可随时查看和修改，推荐资格由本地代码决定；
- 推荐仍是固定硬性过滤、权重和稳定排序，不是学习模型；
- 双语文化内容来自本地资料和模板，不由 DeepSeek 编写，仍需商家审核；
- 不提供登录、支付、库存、合同、物流、结算或商家后台；
- 不保存客户个人身份和联系方式；
- 当前不使用 RAG、向量数据库或 ORM；匿名选择分析可选使用 SQLite（本地）或 PostgreSQL（云端）。
- 当前不使用 AI 语义重排，也不提供商家自助入驻。
- 对话仅保存在当前 Streamlit session，不提供账号、跨设备同步或长期聊天历史；授权后的跨会话分析只保存匿名结构化事件。
- 20 件推荐商品均已关联本地图片；图片来源与商品方案通过稳定 ID 关联，后续可逐件替换为商家正式产品图。

## 后续大模型与 RAG 计划

在真实商家和用户验证规则基线后，可以让大模型辅助整理商家资料、生成待审核双语草稿和改写沟通文本。之后再评估 RAG，用于检索经过授权、审核且可追溯的非遗资料。大模型不会替代价格、产能、交期、运输和文化事实的人工确认，也不会替代现有硬性规则。
