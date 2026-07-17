# 飞颐礼遇 Wave 2 Submitted Skills

本文件是旧路径的简洁兼容入口。四个 Submitted Skills 的完整输入、输出、运行方式、代码映射、测试、回退、AI 边界和当前限制，以 [`docs/wave2/skills/`](wave2/skills/) 下的详细文档为准。

## 1. Conversational Gift Request Understanding / 对话式礼赠需求理解

- 作用：把自然语言首轮、确认页中的连续补充或详细表单转换为经过本地校验、可由用户确认的累计结构化需求。
- 当前实现：DeepSeek 可选字段提取或确定性演示回退；`process_turn`、字段合并、问题选择、校验和需求签名均由本地代码控制。
- 详细文档：[01-conversational-gift-request-understanding.md](wave2/skills/01-conversational-gift-request-understanding.md)

## 2. Progressive Heritage Gift Recommendation / 渐进式非遗礼品推荐

- 作用：只使用已知条件执行明确硬约束过滤和已知维度评分，返回探索、引导或约束推荐。
- 当前实现：固定 25/15/15/15/10/10/5/5 权重、稳定排序、信息覆盖度、置信度和 0–3 件合格 MVP 演示方案；无方案满足全部明确硬约束时不强行推荐。
- 详细文档：[02-progressive-heritage-gift-recommendation.md](wave2/skills/02-progressive-heritage-gift-recommendation.md)

## 3. Grounded Bilingual Heritage Content / 有事实边界的双语文化内容组织

- 作用：从本地中英文资料、来源说明和审核状态组织文化内容，不补写未知产品事实。
- 当前实现：20 件方案对应 40 条本地双语资料，全部为 `review_status=draft`；页面必须标为 MVP 演示文案、待商家审核。
- 详细文档：[03-grounded-bilingual-heritage-content.md](wave2/skills/03-grounded-bilingual-heritage-content.md)

## 4. Merchant-Ready Customization Brief / 商家可执行的定制需求单生成

- 作用：把客户已确认事实、一个选中方案快照、双语内容和待确认问题组装为可预览、复制和下载的 JSON 需求单。
- 当前实现：`InquiryRequestContext` 保留未知预算、数量、定制、Logo、国际运输和交期为 `null`；输出包含中英文 MVP 演示声明。无合格方案时的独立定制概念不等于选中产品需求单。
- 详细文档：[04-merchant-ready-customization-brief.md](wave2/skills/04-merchant-ready-customization-brief.md)

## 唯一 Submitted Workflow

[Conversational Heritage Gift Matching and Customization Workflow / 对话式非遗礼品匹配与定制工作流](wave2/WORKFLOW.md)

```text
自然语言描述、连续补充或详细表单
→ 本地校验、累计与用户确认
→ 渐进式推荐和明确硬约束过滤
→ 有事实边界的双语文化内容
→ 选中方案的商家可执行定制需求单
```

完整评审入口、代表性案例和实际验证状态见 [`docs/wave2/README.md`](wave2/README.md) 与 [`docs/wave2/EVALUATION.md`](wave2/EVALUATION.md)。
