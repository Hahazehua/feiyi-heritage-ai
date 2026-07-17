# Wave 2 PR Description

建议标题：`Wave 2: 飞颐礼遇 Streamlit Prototype and Four Submitted Skills`

## Summary

本变更面向 OPC 2026 Youth S3 第二轮 Wave 2，整理“飞颐礼遇”可运行 Streamlit Prototype、四个 Submitted Skills、一条完整主 Workflow，以及与 Specs 对应的代码和测试证据。当前交付用于验证关键能力，不是正式商业平台。

## Wave 2 Alignment

- 当前阶段：OPC 2026 Youth S3 第二轮 Wave 2。
- 报名并提交截止：2026年7月20日。
- 社区交叉评测：2026年7月21日。
- 晋级结果公布：2026年7月22日。
- 本轮任务：完成产品原型，跑通关键能力。
- Submitted Skills：下方列出的四个 Skills。
- Submitted Workflow：Conversational Heritage Gift Matching and Customization Workflow / 对话式非遗礼品匹配与定制工作流。
- Prototype：使用 Streamlit 实现的“飞颐礼遇”可运行产品原型。
- 测试和评测入口：[`EVALUATION.md`](EVALUATION.md)。

## Submitted Skills

1. [Conversational Gift Request Understanding / 对话式礼赠需求理解](skills/01-conversational-gift-request-understanding.md)
2. [Progressive Heritage Gift Recommendation / 渐进式非遗礼品推荐](skills/02-progressive-heritage-gift-recommendation.md)
3. [Grounded Bilingual Heritage Content / 有事实边界的双语文化内容组织](skills/03-grounded-bilingual-heritage-content.md)
4. [Merchant-Ready Customization Brief / 商家可执行的定制需求单生成](skills/04-merchant-ready-customization-brief.md)

## Submitted Workflow

[Conversational Heritage Gift Matching and Customization Workflow / 对话式非遗礼品匹配与定制工作流](WORKFLOW.md)

```text
自然语言描述或详细表单
→ 结构化理解与用户确认
→ 渐进式推荐和明确硬约束过滤
→ 有事实边界的双语文化内容
→ 商家可执行的定制需求单
```

## Prototype 能力

- Streamlit 五阶段页面：描述、确认、推荐、文化内容、需求单；
- 确认阶段的多轮历史展示、补充输入和本地累计字段合并；
- DeepSeek 可选需求字段提取，以及无 Key/失败时的确定性演示回退；
- 明确硬约束过滤、八维固定权重、已知维度归一化评分和稳定排序；
- 最多 3 件符合全部明确硬约束的目录 MVP 演示方案；无满足条件的目录方案时不强行推荐；
- 基于本地已有字段和审核状态组织中英文文化内容；
- 可预览、复制和下载的 JSON 商家需求单；
- AppTest、纯函数单测、数据校验和阻断真实 API 的测试守卫。

## 最短评审路径

1. 打开 [`README.md`](README.md)。
2. 查看四个 Skill 文档。
3. 查看 [`WORKFLOW.md`](WORKFLOW.md)。
4. 运行 [`DEMO_CASE.md`](DEMO_CASE.md) 的企业海外礼赠案例。
5. 使用本地命令安装并启动：

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e .[dev]
   python -m streamlit run app.py
   ```

6. 按 [`EVALUATION.md`](EVALUATION.md) 运行 Ruff、pytest 和 AppTest。
7. 查看 [`COMPLIANCE.md`](COMPLIANCE.md) 的数据边界、已知限制和 14 项合规状态。

DeepSeek API Key 不是本地最短评审路径的前置条件。评审者可以直接选择“确定性演示模式”。

## 测试与评测状态

- 自动化测试通过 `tests/conftest.py` 阻断真实 DeepSeek 网络调用，不产生真实 API 费用。
- 需求解析、回退、硬过滤、渐进式推荐、无结果、文化内容、需求单和五阶段 UI 均有对应测试文件。
- 2026年7月17日在 Windows、Python 3.11.4 环境实测：Ruff 格式与静态检查通过，pytest 为 `106 passed in 12.01s`，无 API Key 的独立 Streamlit 健康端点返回 `200:ok`。
- `tests/evaluation_cases.json` 的 14 个案例属于确定性回归案例，不等同于已由商家或领域专家标注的黄金集。
- Top-1 命中率、Top-3 命中率和商家满意度当前未评测，不声明数值。

## 数据与事实边界

- 当前数据为 1 个平台演示选品主体、4 个 `unverified` 分类、20 件商品方案、40 条双语资料和 43 条定制选项。
- 40 条双语资料当前全部为 `draft`，必须标注待商家审核。
- 图片和历史元数据来自可追溯开放馆藏；价格、数量、交期、运输和定制能力为独立维护的 MVP 演示方案字段。
- 商品方案、文化文案和需求单均不构成正式报价、库存、产能、物流或交付承诺。

## 明确不在本轮范围

本轮不提交 RAG、向量数据库、正式数据库、多商家后台、商家自主入驻、用户账号、支付、物流、税务、正式订单系统或生产级权限审核体系。这些能力不得在 PR 中写成当前已实现。

## 已知限制

- 当前 Streamlit 在确认阶段的展开区用 Markdown 展示历史，并用补充输入和显式按钮合并新一轮信息；它仍是 session 内轻量顾问，不提供账号、跨设备同步、长期历史或生产级会话治理。
- 所有文化资料仍为 `draft`，需要真实商家进一步审核。
- 当前没有可公开验证的在线 Demo 链接；不提供占位链接。
- 当前没有商家或领域专家标注的正式业务指标；实际工程验证记录见 `EVALUATION.md`。

## Wave 2 Compliance Summary

逐项证据、状态和仍需人工完成的事项见 [`COMPLIANCE.md`](COMPLIANCE.md)。
