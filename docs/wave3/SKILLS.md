# Skills 编排

飞颐礼遇 Agent 注册七项正式 Skills；前六项构成带门控客户链，第七项是显式离线支线。

| # | Skill | 输入 → 输出 | 代码与自动化证据 |
|---|---|---|---|
| 1 | [`understand-gift-request`](../../skills/understand-gift-request/SKILL.md) | 自然语言/表单 → 累计需求、一个问题、解析来源 | dialogue/request wrapper；fallback 与 Trace 测试 |
| 2 | [`infer-soft-preferences`](../../skills/infer-soft-preferences/SKILL.md) | 明确条件 → 软偏好、理由、置信度 | inference wrapper；禁止商业推断测试 |
| 3 | [`recommend-heritage-gifts`](../../skills/recommend-heritage-gifts/SKILL.md) | 有效需求/20件正式目录 → 0–3 个合规候选 | recommender wrapper；硬冲突0结果测试 |
| 4 | [`compose-grounded-content`](../../skills/compose-grounded-content/SKILL.md) | 选中商品/审核资料 → 双语内容与来源 | content wrapper；无产品门控测试 |
| 5 | [`build-final-gift-plan`](../../skills/build-final-gift-plan/SKILL.md) | 已确认需求/商品/内容 → 可下载 JSON | inquiry wrapper；未选品门控测试 |
| 6 | [`capture-consented-choice`](../../skills/capture-consented-choice/SKILL.md) | 明确授权+推荐+最终动作 → 幂等匿名事件或安全状态 | `analytics_service.py`、repositories；记录服务测试 |
| 7 | [`analyze-gift-choice-signals`](../../skills/analyze-gift-choice-signals/SKILL.md) | 匿名事件+筛选/样本阈值 → 聚合选择信号 | `choice_analysis.py`、CLI；分析与 CLI 测试 |

## 反馈闭环

```text
客户需求 → 推荐 → 自愿授权 → 选择/生成方案
→ Skill 6 幂等保存 → Skill 7 聚合分析
→ 人工评审未来优化方向（不自动改权重或排序）
```

## 编排约束

- 模型输出必须经过本地校验；商品资格和排序只由推荐引擎决定。
- 推断不得创造商业或产品事实。
- Skill 6 未获授权时零写入；故障时客户流程继续。
- Skill 7 只输出匿名聚合值，默认最小样本为 5，不输出个人级事件。
- 合成数据必须标记并声明不代表真实客户偏好。
- 分析结果只作未来决策证据，不自动更新线上推荐。

七项 ID、顺序、fallback 和入口由 `agent_registry.py` 与 `agent_manifest.yaml` 双重声明并自动校验。前四项 Wave 2 原始规格继续保留；Wave 3 的五个新包是现有代码的薄封装，不反向改写历史交付。
