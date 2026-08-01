# W3 Specs 证据矩阵

| W3 要求 | 产品行为 | 代码证据 | 自动化/人工证据 | 状态 |
|---|---|---|---|---|
| Agent 完整可运行 | 输入→追问→推荐→选品→最终方案 | `app.py`、`src/heritagelink/` | 全量 pytest；Demo A | 已实现 |
| 初步交互能力 | 自然语言、快捷入口、单问题追问、跳过和修改 | `dialogue_manager.py`、`conversation_state.py` | `test_dialogue_manager.py`、`test_app_smoke.py` | 已实现 |
| Skills 整合 | 理解→推断→推荐→内容→方案→分析 | `SKILLS.md` 中的映射 | 对应模块单测和 AppTest | 已实现 |
| 用户价值可见 | 降低需求澄清成本，同页输出可解释方案 | 推荐卡、文化内容、最终方案 | Demo A | 已实现 |
| 受控推断 | 明确值和推测值分离，禁止商业事实推断 | `inference_policy.py` | `test_inference_policy.py` | 已实现 |
| 推荐可解释 | 硬约束过滤、匹配理由、可展开评分 | 推荐引擎与产品卡 | 推荐测试；Demo A/B | 已实现 |
| 异常时可用 | 无 Key、模型失败、数据库失败均可继续 | parser、analytics 回退 | API/DB 失败测试；Demo C | 已实现 |
| 不制造无效结果 | 无合格商品返回 0 个结果和调整方向 | `recommender.py` | 无结果 AppTest；Demo B | 已实现 |
| 隐私与分析 | 明示同意、匿名字段、幂等、SQLite/Postgres | `analytics.py`、`repositories/` | 分析与仓储测试；Demo D | 已实现 |
| Skill 6：授权选择记录 | 未授权零写入；授权后保存匿名事件；rerun 防重 | `skills/capture-consented-choice/SKILL.md`、`analytics_service.py` | analytics service/repository/AppTest；Demo D | 已实现 |
| Skill 7：选择信号分析 | 漏斗、产品、排名、场景、预算和轮数聚合；小样本保护 | `skills/analyze-gift-choice-signals/SKILL.md`、`choice_analysis.py`、CLI | choice analysis/CLI 测试；Demo E | 已实现 |
| 数据事实有边界 | 演示声明、来源、审核状态、未知值可见 | CSV、`content.py`、UI | 内容与加载测试 | 已实现 |
| 移动端可用 | 窄屏不横向溢出，主操作可触达 | `ui/theme.py` | AppTest CSS + 浏览器窄屏检查 | 已实现 |
| 社区/AI/专家评审 | 最短复现命令和结构化证据 | `docs/wave3/` | 评审记录待赛事阶段填写 | 待执行 |

## 不应宣称的指标

自动化回归证明实现行为稳定，不等于经独立标注的 Top-1/Top-3 命中率、商家满意度或商业转化率。获得真实用户或专家标注前，不填写这些业务指标。

## 提交门槛

- `ruff format --check`、`ruff check`、`pytest` 全部退出码为 0。
- 无 API Key 的 Streamlit 健康端点返回 `200:ok`，主流程可手工完成。
- 在线 Demo 与视频链接实际可访问，不保留占位 URL。
- 不提交 `.env`、数据库文件、真实对话或联系方式。
- 合成数据库必须位于 `.local/`，报告必须显示合成数据声明。
- 交叉评审问题、处理结论和未修复影响有书面记录。
