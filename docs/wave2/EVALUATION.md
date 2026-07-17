# Wave 2 测试与评测

## Wave 2 Alignment

- 当前阶段：OPC 2026 Youth S3 第二轮 Wave 2。
- 报名并提交截止：2026年7月20日。
- 社区交叉评测：2026年7月21日。
- 晋级结果公布：2026年7月22日。
- 本轮任务：完成产品原型，跑通关键能力。
- Submitted Skills：四个详细 Skill 文档位于 [`skills/`](skills/)。
- Submitted Workflow：[Conversational Heritage Gift Matching and Customization Workflow / 对话式非遗礼品匹配与定制工作流](WORKFLOW.md)。
- Prototype：使用 Streamlit 实现的“飞颐礼遇”可运行产品原型。
- 测试入口：本文件列出的 Ruff、pytest、AppTest 和人工冒烟路径。

> 当前状态：2026年7月17日已完成安装、Ruff、全量 pytest 和无 API Key 的独立 Streamlit 启动验证。自动化结果是工程回归证据，不等同于 Top-1、Top-3、商家满意度或公开排行榜指标。

## 评测原则

1. Specs、实现、README、Skill 文档和测试使用同一输入输出与边界口径。
2. 自动化测试必须是确定性的，不调用真实外部 API。
3. 明确硬约束违规推荐数应为 0；未知字段不能被当作负面匹配。
4. 无目录 MVP 演示方案满足全部明确硬约束时，不得强行推荐或虚构商品方案。
5. 文化内容只能使用本地已有字段，并保留来源与审核状态。
6. 需求单必须区分已知事实、MVP 演示数据和商家待确认信息。
7. 只报告实际执行产生的证据；目标值、回归案例和人工评价不得混写为已取得指标。

## Specs → 代码 → 测试证据矩阵

| 能力 | 主要代码 | 自动化测试 | 当前证据状态 |
|---|---|---|---|
| Conversational Gift Request Understanding / 对话式礼赠需求理解 | `request_parser.py`、`llm_client.py`、`dialogue_manager.py`、`conversation_state.py`、`app.py::_render_describe/_render_confirm` | `test_request_parser.py`、`test_llm_client.py`、`test_dialogue_manager.py`、`test_app_smoke.py` | 通过；覆盖无 Key 回退、多轮合并、不确定字段隔离和详细表单未知默认值。 |
| Progressive Heritage Gift Recommendation / 渐进式非遗礼品推荐 | `progressive_recommender.py`、`recommender.py`、`customization_concept.py`、`app.py::_render_recommend` | `test_progressive_recommender.py`、`test_recommender.py`、`test_customization_concept.py`、无结果 AppTest | 通过；未知与不确定字段不参与硬过滤，无合格目录方案时不强推。 |
| Grounded Bilingual Heritage Content / 有事实边界的双语文化内容组织 | `content.py`、`data_loader.py`、`data/demo/product_texts.csv`、`app.py::_render_culture` | `test_content.py`、`test_data_loader.py`、五阶段 AppTest | 通过；20 条英文来源说明已本地化并保留来源 URL；40 条资料均为 `draft`。 |
| Merchant-Ready Customization Brief / 商家可执行的定制需求单生成 | `inquiry.py`、`request_parser.to_inquiry_details`、`app.py::_build_inquiry_for_selection/_render_inquiry` | `test_inquiry.py`、五阶段 AppTest | 通过；未知值保持 `null`，重新确认需求会清除并重建旧需求单。 |
| 主 Workflow | `app.py` 的 describe → confirm → recommend → culture → inquiry | `test_app_smoke.py::test_product_culture_and_inquiry_complete_five_stage_flow` | 通过；AppTest 覆盖五阶段，独立 Streamlit 健康端点返回 `200:ok`。 |

## 建议执行命令

### 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

### 全量质量检查

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

### 分 Skill 复现

```powershell
python -m pytest tests/test_request_parser.py tests/test_dialogue_manager.py tests/test_llm_client.py
python -m pytest tests/test_progressive_recommender.py tests/test_recommender.py tests/test_customization_concept.py
python -m pytest tests/test_content.py tests/test_data_loader.py
python -m pytest tests/test_inquiry.py
python -m pytest tests/test_app_smoke.py
```

### Streamlit 冒烟

```powershell
python -m streamlit run app.py --server.headless true
```

该命令为持续运行的服务，应在确认应用成功启动后由执行者正常终止。自动化 UI 复现优先使用 `python -m pytest tests/test_app_smoke.py`。

## 自动化测试不会调用真实外部 API

`tests/conftest.py` 定义自动使用的 `block_real_deepseek` fixture：

- 把 `DEEPSEEK_API_KEY` 设置为占位值，避免测试读取开发者本地 Key；
- 将 OpenAI-compatible completion 创建调用替换为立即抛出断言错误的函数；
- 因此任何意外真实网络调用都会使测试失败，而不是静默访问 DeepSeek 或产生费用。

DeepSeek 成功、超时、认证、空响应和非法 JSON 路径使用 Fake、Mock 或本地构造对象测试。

## 确定性回归案例的真实含义

`tests/evaluation_cases.json` 当前包含 14 个版本化回归案例，覆盖预算、数量、交期、Logo、国际运输、定制类型、符合条件的目录方案和无结果场景。`tests/test_recommender.py::test_evaluation_cases_are_runnable` 检查：

- 案例能够构造 `GiftRequest` 并运行规则推荐；
- 推荐数量不超过 3；
- `expected_contains` 中的商品出现在结果集合；
- `expected_empty` 与是否存在符合条件的目录方案一致。

这些案例尚未记录商家或领域专家标注人、标注依据和独立盲评结果，也没有当前版本的 Top-1/Top-3 指标计算报告。因此：

- Top-1 命中率：未评测；
- Top-3 命中率：未评测；
- 商家满意度：未评测；
- 公开排行榜成绩：未提供。

在补齐真实标注来源和可复现计算前，不得把测试通过比例改写为上述业务指标。

## 代表性验收案例

| 案例 | 核心断言 | 对应测试 | 状态 |
|---|---|---|---|
| 企业海外礼赠 | 解析 20 件、单价 300 元、Logo、美国目的地；确认后得到不超过 3 件结果 | `test_home_explains_value_and_demo_case_reaches_confirmation`、`test_confirmation_is_required_before_recommendations` | 通过 |
| 五阶段 Workflow | 推荐 → 文化内容 → 需求单 → 下载按钮 | `test_product_culture_and_inquiry_complete_five_stage_flow` | 通过 |
| 未表达字段不编造 | AI 输入和详细表单均不预选未表达事实 | `test_confirmation_does_not_invent_unstated_select_fields`、`test_precise_form_does_not_preselect_unstated_customer_facts`、`test_unstated_fields_are_not_invented` | 通过 |
| 多轮补充 | 保留历史，把第二轮字段合并到累计需求，确认后仍使用新值 | `test_second_turn_merges_new_fields_instead_of_restarting`、`test_confirmation_supports_a_second_conversation_turn` | 通过 |
| 无 Key 或超时 | 明确回退到确定性演示解析 | `test_no_api_key_uses_demo_mode`、`test_timeout_safely_falls_back_to_demo_mode` | 通过 |
| 硬约束不可绕过 | 预算、数量、交期、定制、Logo、运输冲突被过滤；不确定字段除外 | `tests/test_recommender.py`、`test_uncertain_fields_are_treated_as_unknown_by_public_recommender` | 通过 |
| 无结果不强推 | 0 个合格推荐，显示冲突；定制概念不虚构产品 | 无结果 AppTest、`test_customization_concept.py` | 通过 |
| 文化内容有边界 | 只使用存储字段；缺失时标记待确认；英文来源说明保留 URL | `tests/test_content.py` | 通过 |
| 需求单完整 | 缺失项保持未知并进入开放问题；需求变化后旧需求单失效 | `tests/test_inquiry.py`、`test_reconfirming_request_invalidates_and_rebuilds_inquiry` | 通过 |

## 人工 Streamlit 检查

交叉评审的人工复现人员应核对以下结果，而不是仅凭代码存在判定通过：

1. 未配置 API Key 时，选择确定性演示模式并完成 [`DEMO_CASE.md`](DEMO_CASE.md) 案例 A，包括一次“继续补充或修正需求”的多轮合并。
2. 确认页面显示需求摘要、推荐模式、覆盖度、当前置信度、最多 3 件结果和约束说明。
3. 确认文化页面显示双语内容、来源、`draft`/待审核边界。
4. 确认需求单可以预览、复制并下载合法 JSON。
5. 运行案例 B，确认没有符合条件的目录方案时不会出现“选择此方案”。
6. 确认页面没有把演示价格、产能、交期和运输写成商家正式承诺。

## 最终验证记录

- 执行日期：2026年7月17日。
- 验证对象：本次未提交工作树；用户提交后需补录最终 commit hash。
- 环境：Microsoft Windows NT 10.0.26200.0、Python 3.11.4、Streamlit 1.59.2、Starlette 1.3.1。
- 安装：在独立 `.venv` 中执行 `python -m pip install -e .[dev]`，退出码 0。
- `python -m ruff format --check .`：退出码 0，`37 files already formatted`。
- `python -m ruff check .`：退出码 0，`All checks passed!`。
- `python -m pytest -p no:cacheprovider`：退出码 0，`106 passed in 12.01s`。
- 按 README 原样复跑 `python -m pytest`：退出码 0，`106 passed in 14.74s`；耗时会随环境波动。
- 无 API Key 启动：移除 `DEEPSEEK_API_KEY` 后，以 headless 模式在本地独立进程启动，`/_stcore/health` 返回 `200:ok`，随后正常终止进程。
- 人工观察：已在本地浏览器检查首屏、内置企业案例、确认页和第二轮补充；自动化 AppTest 完成最终五阶段路径、无结果、未知字段和需求单重建回归。2026年7月21日交叉评测前，仍建议由一名不熟悉项目的人员按七步路径完整走查一次。

当前没有可公开验证的在线 Demo 链接；本地 Prototype 是本轮可复现入口。当前没有商家或领域专家标注的业务指标，最终提交 commit hash 和第三方走查记录仍需用户补充。
