# 飞颐礼遇 Wave 2 实施与收尾计划

状态快照日期：2026年7月17日。

本文件记录当前已经落地的实现、最终验证步骤和仍需人工完成的提交事项。赛事阶段、截止日期和交叉评审入口统一见 `docs/wave2/README.md`，此处不重复赛事公告。

## 1. 当前交付范围

当前仓库目标是完成一套可本地运行、可测试、可解释的 Streamlit 原型，而不是正式商业平台。Submitted Skills 和唯一 Workflow 以以下文件为准：

- `docs/WAVE2_SKILLS.md`：简洁兼容入口；
- `docs/wave2/skills/`：四个详细 Skill 文档；
- `docs/wave2/WORKFLOW.md`：唯一端到端 Workflow；
- `docs/wave2/EVALUATION.md`：实际命令与评测证据；
- `docs/wave2/COMPLIANCE.md`：最终合规状态和人工待办。

当前目录使用本地 CSV/JSON 和 Streamlit session，不使用正式数据库、RAG、向量检索、账号、支付、物流、订单或生产级后台。

## 2. 截至 2026年7月17日的完成状态

### 2.1 Conversational Gift Request Understanding

已实现：

- 自然语言首轮解析和详细表单；
- DeepSeek 可选字段提取；
- 无 Key、认证、余额、超时、网络、空响应和非法 JSON 的安全回退；
- 本地字段白名单、类型、枚举、金额和交叉字段校验；
- `ConversationState`、`process_turn` 和累计字段合并；
- 确认页中的连续历史展示、下一轮补充和显式合并；
- 用户结构化修订和确认优先于模型候选输出。

AI 只提供候选字段。多轮合并、问题选择、需求签名和推荐就绪状态均由本地代码决定。

### 2.2 Progressive Heritage Gift Recommendation

已实现：

- 探索、引导和约束三种推荐模式；
- 只对用户明确条件启用硬过滤；
- 25/15/15/15/10/10/5/5 八维固定权重；
- 只使用已知维度的 0–100 归一化当前匹配分；
- `score desc, product_id asc` 稳定排序和最多 3 件输出；
- 页面展示信息覆盖度、低/中/高置信度和八维状态；
- 无方案满足全部明确硬约束时返回零件合格推荐、冲突原因和调整方向；
- 冲突方案只出现在独立参考区；独立定制概念不虚构产品身份。

### 2.3 Grounded Bilingual Heritage Content

已实现：

- 本地中英文资料加载和双语模板组织；
- 来源说明、审核状态和缺失字段标记；
- 运行时不调用机器翻译、DeepSeek 或 RAG 补写文化事实；
- 馆藏参考目录、图片许可和本地图片关联；
- 馆藏物件与 MVP 礼赠方案商业字段分开维护。

当前 20 件方案对应 40 条双语资料，全部为 `review_status=draft`。这表示文案可用于明确标记的 MVP 演示，但不能称为商家已审核内容。

### 2.4 Merchant-Ready Customization Brief

已实现：

- 一个选中合格方案的商品与价格快照；
- 客户需求、定制、交付、双语内容、行动项和开放问题；
- `InquiryRequestContext` 保留客户未知预算、数量、定制、Logo、国际运输和交期为 `None`；
- 中英文 MVP 演示需求单声明；
- 页面预览、可复制摘要和 UTF-8 JSON 下载；
- 下载前结构校验。

无合格方案时的 `custom_heritage_gift_concept` 是独立输出，不等于选中产品需求单。

### 2.5 Prototype 与数据

已实现五阶段 Streamlit 主路径：

```text
描述需求
→ 确认、连续补充与结构化修订
→ 渐进式推荐
→ 双语文化内容
→ 商家需求单
```

当前 `data/demo/` 包含：

- 1 个平台演示选品主体；
- 4 个 `unverified` 工艺分类；
- 20 件带图 MVP 礼赠方案；
- 40 条 `draft` 双语资料；
- 43 条 MVP 定制选项。

页面全局显示 `MVP 演示数据 / MVP demo data`。价格、数量、交期、运输和定制能力需要商家复核，不构成报价或履约承诺。

## 3. 当前测试资产

仓库已包含以下测试层：

- 需求解析、DeepSeek 客户端、无 Key 回退和对话合并；
- 渐进式推荐、每项硬过滤、固定评分和稳定排序；
- 数据列、主键、外键、枚举、金额、数量、双语资料、图片和演示声明；
- 双语内容缺失与审核边界；
- 需求单完整性、未知客户字段和 JSON 校验；
- 无结果概念不虚构商品；
- Streamlit AppTest 主路径、连续补充、无强推和探索性需求单未知值；
- 14 个确定性推荐回归案例。

`tests/conftest.py` 设置占位 API Key，并把真实 completion 调用替换为立即失败的守卫。自动化测试不得访问真实 DeepSeek API 或产生费用。

这些测试资产已在2026年7月17日完成全量验证；真实环境、命令和结果记录在 `docs/wave2/EVALUATION.md`，不得将其改写为业务指标。

## 4. 最终自动化验证

### 4.1 环境记录

2026年7月17日已记录：

- 验证对象为本次未提交工作树，最终 commit hash 仍需提交负责人补录；
- Microsoft Windows NT 10.0.26200.0；
- Python 3.11.4、Streamlit 1.59.2、Starlette 1.3.1；
- 独立启动检查移除了 `DEEPSEEK_API_KEY`；
- 数据规模为 1 个演示选品主体、4 个分类、20 件方案、40 条双语资料和 43 条定制选项。

### 4.2 安装

在干净 Python 3.11+ 环境中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

以上 editable install 已在独立 `.venv` 中成功完成，退出码为 0。

### 4.3 质量检查

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

实测结果：Ruff 格式检查为 `37 files already formatted`，静态检查为 `All checks passed!`，pytest 为 `106 passed in 12.01s`；三条命令退出码均为 0。

### 4.4 分 Skill 复现

必要时使用：

```powershell
python -m pytest tests/test_request_parser.py tests/test_dialogue_manager.py tests/test_llm_client.py
python -m pytest tests/test_progressive_recommender.py tests/test_recommender.py tests/test_customization_concept.py
python -m pytest tests/test_content.py tests/test_data_loader.py tests/test_catalog.py
python -m pytest tests/test_inquiry.py
python -m pytest tests/test_app_smoke.py tests/test_catalog_app.py
```

失败时先保存可定位的失败信息，再修复代码、数据、测试或文档；不得删除合理断言来制造通过结果。

## 5. Streamlit 人工冒烟

启动命令：

```powershell
python -m streamlit run app.py --server.headless true
```

该命令持续运行。确认应用成功启动后，按 `docs/wave2/DEMO_CASE.md` 至少走查：

1. 无 `.env` 或主动选择确定性演示模式；
2. 企业海外礼赠代表案例完成五阶段主路径；
3. 确认页输入第二轮补充并验证累计字段更新；
4. 推荐页显示模式、覆盖度、置信度和不超过 3 件结果；
5. 文化页显示来源、`draft` 和待审核边界；
6. 需求单未知字段保持待确认，页面显示中英文 MVP 声明，JSON 可以下载并解析；
7. 低预算无结果案例不显示合格方案选择按钮；
8. 馆藏目录明确说明馆藏原物不是平台在售商品。

把实际观察、浏览器地址和终止方式记录到 `docs/wave2/EVALUATION.md`。

## 6. 一致性收尾

最终提交前执行以下只读检查：

- 四个 Submitted Skills 的中英文名称在根 README、Specs、Skill 文档和 PR 描述中完全一致；
- 仓库只声明一条指定名称的 Submitted Workflow；
- README、Specs、架构、数据 schema、代码和测试没有把未来能力写成当前功能；
- 所有链接和相对路径存在；
- 安装、启动和测试命令与最终 `pyproject.toml` 一致；
- 所有产品数量、文化资料数量和定制选项数量与最终 CSV 一致；
- 所有公开资料、MVP 演示字段、模板表达和待确认事实保持可区分；
- `.env`、密钥、缓存和个人信息未进入提交；
- 没有占位在线 Demo 链接、虚构测试数或未经验证的指标。

## 7. 评测证据边界

`tests/evaluation_cases.json` 的 14 个案例只证明确定性回归行为。当前没有商家或领域专家标注人、独立盲评或满意度证据，因此不报告：

- 自然语言解析准确率；
- Top-1 或 Top-3 命中率；
- 商家满意度；
- 询单转化率；
- 真实履约成功率。

未来若开展人工评测，必须记录案例版本、标注人角色、标注依据、计算脚本和可复现输出，不能把自动化测试通过比例改写为业务指标。

## 8. 用户或提交负责人仍需完成

- 由不熟悉项目的人按 `docs/wave2/README.md` 的最短路径复现一次；
- 最终提交后在 `docs/wave2/EVALUATION.md` 补录 commit hash；
- 检查 PR 描述、提交表单和最终仓库链接；
- 如提供在线 Demo，只填写实际可访问且经过验证的地址；没有则保留“仅本地 Prototype”；
- 后续由真实商家审核 40 条 `draft` 双语资料及价格、产能、交期、运输和定制字段；在完成前保持演示和待确认标记。

## 9. 后续阶段而非本轮交付

以下内容继续保留为未来计划，不得写成当前已实现：

- RAG、Embedding、向量数据库和 AI 语义重排；
- 正式数据库和长期会话持久化；
- 多商家后台、商家自主入驻和生产级审核权限；
- 用户账号；
- 正式库存、报价、合同、支付、物流、税务和订单系统；
- 未经人工审核的文化事实自动发布。

## 10. 完成条件

只有在以下事项全部有证据时，Wave 2 工程材料才可标为最终完成：

1. 四个 Skills 和唯一 Workflow 与最终代码一致；
2. 干净环境安装、Ruff、pytest 和 Streamlit 启动均有真实记录；
3. 无 Key、连续补充、成功推荐、无结果和需求单路径均完成复现；
4. 演示数据、来源、审核和未来边界在页面与文档中一致；
5. 所有相对链接有效；
6. 提交负责人完成最终人工走查和外部提交步骤。
