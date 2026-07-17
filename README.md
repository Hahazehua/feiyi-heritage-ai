# 飞颐礼遇｜HeritageLink AI

飞颐礼遇是面向非遗礼品推荐与定制沟通的 AI 顾问。当前产品库包含漆艺、龙泉青瓷、传统织绣和传统玉雕四组共 20 件带图商品方案，用于验证从客户需求理解、渐进式推荐、双语文化介绍到商家定制需求单的完整交易前流程；HeritageLink AI 为项目英文名称。

本项目属于 SynNovator 数字文化赛道（原赛道标识：`track-98`）。

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

## 用户流程

页面采用五阶段礼赠顾问流程：

1. 用户在首页用自然语言描述需求，或切换到“精准填写需求”；
2. 系统先展示结构化理解结果，区分已确认、待确认和缺失信息；用户可继续补充或修正，再核对进入推荐；
3. 本地规则引擎执行硬性条件过滤和八维评分，最多展示 3 件可解释方案；
4. 用户查看中英文文化故事、工艺依据和定制建议，再选择具体方案；
5. 系统生成可预览、复制和下载的商家定制需求单。

首页“体验企业海外礼赠案例”会填入一套完整需求并调用真实的本地解析和推荐逻辑。页面使用 `st.session_state` 保存当前会话、阶段、确认需求、推荐结果和选中产品，支持连续补充、返回、调整与重新开始；会话不会写入长期存储。

DeepSeek 只做自然语言字段提取，不决定推荐结果，也不能绕过硬性条件。

## 非遗礼赠产品库

首页可进入“浏览 20 件非遗礼赠产品”。每件商品均配置本地图片、中英文名称、方案价格、起订量、交期、定制能力、文化介绍和推荐标签，可以直接进入规则推荐引擎。

- 结构化资料位于 `data/catalog/heritage_products.csv`；
- 网页使用的本地图片位于 `assets/catalog/products/`；
- `data/demo/products.csv` 保存 20 件可推荐商品及对应 `image_path`；
- `data/catalog/heritage_products.csv` 的 `demo_product_id` 将图片来源资料与商品一一关联；
- `source_url`、`image_source_url`、`source_object_number` 和 `image_license` 保存资料出处与使用许可；
- 当前图片来自大都会艺术博物馆开放馆藏，所选页面均标记为 Public Domain，目录按 [The Met Open Access](https://www.metmuseum.org/about-the-met/policies-and-documents/open-access) 记录为 CC0；
- 图片与历史信息作为设计依据；方案价格、数量、交期和定制能力由飞颐礼遇产品数据单独维护，不从馆藏资料推断。

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

### DeepSeek 模式与演示回退模式

- 自动模式：存在有效 `DEEPSEEK_API_KEY` 时优先调用 DeepSeek，并由本地代码重新校验、合并和判断推荐就绪状态；
- 演示模式：使用有限的正则和关键词规则，页面会明确显示“当前使用演示解析模式”；
- 没有 API Key、认证失败、余额不足、超时、网络错误或空响应时，系统安全回退到演示模式；
- API 故障不会影响详细表单和原有推荐功能；
- 用户也可主动选择确定性演示解析，完全不发出 API 请求。

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
- 当前不使用 RAG、向量数据库、数据库或 ORM。
- 当前不使用 AI 语义重排，也不提供商家自助入驻。
- 对话仅保存在当前 Streamlit session，不提供账号、跨设备同步或长期历史记录。
- 20 件推荐商品均已关联本地图片；图片来源与商品方案通过稳定 ID 关联，后续可逐件替换为商家正式产品图。

## 后续大模型与 RAG 计划

在真实商家和用户验证规则基线后，可以让大模型辅助整理商家资料、生成待审核双语草稿和改写沟通文本。之后再评估 RAG，用于检索经过授权、审核且可追溯的非遗资料。大模型不会替代价格、产能、交期、运输和文化事实的人工确认，也不会替代现有硬性规则。
