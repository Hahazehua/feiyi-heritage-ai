# Wave 3 PR Description

建议标题：`Wave 3: add gated seven-Skill Agent demo and release evidence`

## Summary

本变更将飞颐礼遇整理为一个可运行、可观察、可复现的七 Skills Agent。Streamlit 客户页通过统一入口完成需求理解、受控推断、硬过滤推荐、选品内容、最终方案和授权记录；匿名信号分析保持离线按需执行。

## Reviewer path

1. 从 [`docs/wave3/README.md`](README.md) 开始。
2. 查看 [`ORCHESTRATION.md`](ORCHESTRATION.md) 与 [`agent_manifest.yaml`](agent_manifest.yaml)。
3. 按 [`EVALUATION.md`](EVALUATION.md) 运行 Ruff 和 pytest。
4. 按 [`DEMO.md`](DEMO.md) 复现四条轨迹。
5. 查看 [`BROWSER_ACCEPTANCE.md`](BROWSER_ACCEPTANCE.md) 与 `evidence/` 截图。

## Safety boundaries

- 不改变硬过滤、固定八维权重或稳定排序。
- 未授权时匿名事件零写入；存储失败不阻断客户流程。
- 评审 Trace 默认关闭并集中脱敏。
- Skill 7 不进入客户主链，也不自动修改推荐配置。
- 当前不包含账号、支付、订单、物流、RAG或商家后台。

## Links to fill manually

- Repository: `<REPOSITORY_URL>`
- Pull Request: `<PULL_REQUEST_URL>`
- Live Demo: `<LIVE_DEMO_URL>`
- Review Mode: `<REVIEW_MODE_URL>`
- Demo Video: `<DEMO_VIDEO_URL>`

