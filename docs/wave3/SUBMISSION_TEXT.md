# Wave 3 平台提交文本

## Project Title

HAHA｜Heritage Artisans, Horizons Ahead

## One-line Description

连接非遗手艺人、文化礼品与全球买家的 AI 出海智能体。An AI agent connecting heritage artisans, culturally meaningful gifts, and global buyers through grounded recommendations and bilingual sales workflows.

## Project Description

HAHA 代表 Heritage Artisans, Horizons Ahead。飞颐礼遇 AI 礼赠顾问是 HAHA 当前的产品原型。中国非遗拥有深厚的文化价值，却常因语言、文化解释和商业需求沟通之间的断层，难以进入全球礼赠场景。项目从一份真实需求出发，通过单页对话逐步理解对象、场景、预算、数量、文化寓意、定制与交付边界，每轮最多提出一个高价值问题，并允许用户随时要求立即推荐或修改条件。

Agent 将七项 Skills 按门控链执行：礼赠需求理解、受控软偏好推断、非遗礼品硬过滤与稳定推荐、有事实边界的双语内容、最终礼品方案、匿名授权选择记录，以及离线匿名选择信号分析。推荐严格保留硬过滤、固定八维权重和稳定排序；20件正式 Demo 商品可进入推荐，30件馆藏参考不会被补入正式结果。

DeepSeek 只用于可选字段提取，失败时安全回退到确定性解析。无合格商品时返回0件及调整方向，不虚构产品。选择记录必须获得明确授权；未授权零写入，数据库故障只降级而不阻断方案生成。评审模式展示脱敏执行链、回退、安全检查和耗时，不展示聊天原文、Key、数据库地址或内部 UUID。Skill 7 仅离线按需运行，不自动修改推荐权重。

## Submitted Skills

1. 礼赠需求理解 / Understand Gift Request
2. 受控软偏好推断 / Infer Soft Preferences
3. 非遗礼品硬过滤与稳定推荐 / Recommend Heritage Gifts
4. 有事实边界的双语文化内容 / Compose Grounded Content
5. 最终礼品方案生成 / Build Final Gift Plan
6. 匿名授权选择记录 / Capture Consented Choice
7. 匿名礼品选择信号分析 / Analyze Gift Choice Signals

## Workflow

```text
自然语言或表单 → 需求理解 → 单问题追问/立即推荐
→ 受控推断 → 硬过滤与最多3件推荐 → 选品
→ 双语文化内容 → 可下载最终方案 → 授权后匿名记录

授权匿名事件 → 人工触发离线聚合分析（不回写线上权重）
```

## Prototype

公开 Streamlit 页面提供对话、需求摘要、推荐解释、选品、最终方案和 JSON 下载。评审 URL 在服务端开关与 URL 参数同时满足后，显示七项 Skills 的脱敏 execution trace。

## Evaluation

- 2026-08-01 发布收口验收：Ruff format/lint 通过，`164 passed`。
- 真实浏览器结果：以 `EVALUATION.md` 和 `BROWSER_ACCEPTANCE.md` 的发布验收记录为准。
- 四条轨迹覆盖正常路径、DeepSeek 回退、硬约束0结果，以及未授权/saved/数据库降级。

## Links

- Repository: `https://www.synnovator.com/harrychen901/feiyi-heritage-ai`
- Live Demo: `https://feiyi-haha-ai.streamlit.app/`
- Demo Video: `https://www.bilibili.com/video/BV1rcMm64ELw/`
