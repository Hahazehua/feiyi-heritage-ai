# 飞颐礼遇 Wave 2 提交入口

飞颐礼遇（HeritageLink AI）是一个可本地运行的 Streamlit 非遗礼赠原型：它把用户表达的礼赠需求转换为结构化条件，用确定性规则匹配当前 20 件 MVP 演示商品方案，展示有事实边界的中英文文化内容，并生成商家可继续核对的定制需求单。

## Wave 2 Alignment

- 当前阶段：OPC 2026 Youth S3 第二轮 Wave 2。
- 报名并提交截止：2026年7月20日。
- 社区交叉评测：2026年7月21日。
- 晋级结果公布：2026年7月22日。
- 本轮任务：完成产品原型，跑通关键能力。
- Submitted Skills：本页列出的四个 Skills。
- Submitted Workflow：Conversational Heritage Gift Matching and Customization Workflow / 对话式非遗礼品匹配与定制工作流。
- Prototype：使用 Streamlit 实现的“飞颐礼遇”可运行产品原型。
- 测试和评测入口：[`EVALUATION.md`](EVALUATION.md)。

## 最短评审路径

不需要先阅读长期商业规划。建议按以下顺序复现：

1. 阅读上方一句话介绍和本页的 Wave 2 Alignment。
2. 查看四个 Submitted Skills：
   - [Conversational Gift Request Understanding / 对话式礼赠需求理解](skills/01-conversational-gift-request-understanding.md)
   - [Progressive Heritage Gift Recommendation / 渐进式非遗礼品推荐](skills/02-progressive-heritage-gift-recommendation.md)
   - [Grounded Bilingual Heritage Content / 有事实边界的双语文化内容组织](skills/03-grounded-bilingual-heritage-content.md)
   - [Merchant-Ready Customization Brief / 商家可执行的定制需求单生成](skills/04-merchant-ready-customization-brief.md)
3. 查看 [Conversational Heritage Gift Matching and Customization Workflow / 对话式非遗礼品匹配与定制工作流](WORKFLOW.md)。
4. 查看并运行[代表性演示案例](DEMO_CASE.md)。
5. 按本页命令安装并启动 Streamlit Prototype。
6. 按 [`EVALUATION.md`](EVALUATION.md) 运行自动化测试。
7. 阅读本页的“数据声明”和“当前限制”，再查看 [`COMPLIANCE.md`](COMPLIANCE.md)。

## Submitted Skills

| # | Submitted Skill | 核心交付 |
|---|---|---|
| 1 | Conversational Gift Request Understanding / 对话式礼赠需求理解 | 自然语言或详细表单转换为经过本地校验、可由用户确认的结构化需求；无 Key 时回退到明确标记的确定性演示解析。 |
| 2 | Progressive Heritage Gift Recommendation / 渐进式非遗礼品推荐 | 只使用已知条件执行硬过滤和已知维度评分，返回 0–3 件符合全部明确硬约束的目录 MVP 演示方案；无完全匹配时不强行推荐。 |
| 3 | Grounded Bilingual Heritage Content / 有事实边界的双语文化内容组织 | 从本地中英文资料和模板组织文化内容，保留来源与审核状态，不补写未知事实。 |
| 4 | Merchant-Ready Customization Brief / 商家可执行的定制需求单生成 | 将确认需求、选中目录方案快照、双语内容和待确认问题组装为可预览、复制和下载的 JSON 需求单。 |

## Submitted Workflow

主 Workflow 为 [Conversational Heritage Gift Matching and Customization Workflow / 对话式非遗礼品匹配与定制工作流](WORKFLOW.md)：

```text
自然语言描述或详细表单
→ 结构化理解与用户确认
→ 渐进式推荐和明确硬约束过滤
→ 有事实边界的双语文化内容
→ 商家可执行的定制需求单
```

当前 Streamlit 页面使用 `process_turn` 建立会话，在确认阶段的展开区用 Markdown 展示历史，并允许用户通过“继续补充或修正需求”反复合并新一轮信息；同时保留结构化表单修订和五阶段主流程。该界面是当前 session 内的轻量多轮顾问，不是带账号、持久化历史和生产级会话管理的平台。

## 安装与启动

需要 Python 3.11 或更高版本。以下 Windows PowerShell 路径已在2026年7月17日使用 Python 3.11.4 实际验证；完整记录见 [`EVALUATION.md`](EVALUATION.md)。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m streamlit run app.py
```

浏览器通常打开 `http://localhost:8501`。

DeepSeek API Key 不是最短评审路径的前置条件。评审者可以不创建 `.env`，在页面选择“确定性演示模式”；没有 Key、认证失败、余额不足、超时、网络错误、空响应或模型输出未通过本地校验时，需求解析会安全回退，后续规则推荐、文化内容和需求单不依赖真实外部 API。

## 自动化测试

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

Streamlit 五阶段流程由 `tests/test_app_smoke.py` 使用 AppTest 覆盖。`tests/conftest.py` 会在所有自动化测试中设置占位 Key，并把真实 DeepSeek 网络请求替换为立即失败的守卫，因此测试不会调用真实外部 API，也不会产生 API 费用。2026年7月17日实测：Ruff 两项检查通过，pytest 为 `106 passed in 12.01s`，无 API Key 的独立 Streamlit 健康端点返回 `200:ok`。

## 数据声明

- `data/demo/` 当前包含 1 个平台演示选品主体、4 个 `unverified` 工艺分类、20 件带图商品方案、40 条双语文化资料和 43 条定制选项。
- 40 条双语文化资料当前全部为 `review_status=draft`，页面将其表述为 MVP 演示文案并提示待商家审核，不能称为商家已审核事实；`app.main` 同时在所有阶段显示 `MVP 演示数据 / MVP demo data` 全局声明。
- 图片与部分历史元数据来自可追溯的开放馆藏；商品方案名称、价格、数量、交期、运输和定制能力是独立维护的 MVP 演示数据，不能从馆藏资料推断，也不构成商家报价或履约承诺。
- 当前不声明真实传承人身份、官方认定级别、政府背书、真实库存、正式产能或实际交付能力。
- `tests/evaluation_cases.json` 是确定性回归案例集合，不是已经由商家或领域专家完成标注的公开排行榜数据集。

## 当前限制

- 当前 Prototype 不提供 RAG、向量数据库、正式数据库、商家自主入驻、多商家后台、用户账号、支付、物流、税务、正式订单或生产级权限审核体系。
- 推荐是固定硬约束、固定权重和稳定排序，不是学习模型或商业成功概率预测。
- 当前 Streamlit 支持确认阶段的多轮补充与字段合并，但使用 `st.text_input` 和显式“合并这条补充”按钮，不提供账号、跨设备同步、长期历史或生产级会话管理。
- 对话和选择只保存在当前 Streamlit session，不持久化客户身份或联系方式。
- 需求单可用于商家继续核对，但不是正式合同、订单、报价、产能或交付承诺。
- 当前没有可公开验证的在线 Demo 链接；评审路径以本地运行 Prototype 为准。
- Top-1、Top-3 命中率和商家满意度当前未评测，不在本提交包中声明数值。

## 其他提交材料

- [代表性演示案例](DEMO_CASE.md)
- [测试与评测](EVALUATION.md)
- [PR 描述](PR_DESCRIPTION.md)
- [Wave 2 Compliance Summary](COMPLIANCE.md)
