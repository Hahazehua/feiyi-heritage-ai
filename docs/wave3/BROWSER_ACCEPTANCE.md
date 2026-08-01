# Wave 3 真实浏览器验收

验收环境：本地 Streamlit、真实 Chromium 浏览器控制、预设合成演示输入。自动化单元/集成测试与 Streamlit AppTest 不计入本表的浏览器结果。

| Case | Viewport | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| 客户首页 | Desktop 1440×1000 | 标题和聊天可见、无技术 Trace | 标题、快捷入口、聊天框可见；环境开启但无URL参数时Trace隐藏；无横向滚动 | Pass | [首页](evidence/customer-home-desktop.png) |
| 正常 Agent 路径 | Desktop 1440×1000 | Skills 1→6 按门控执行并生成方案 | 完成对话、推荐解释、选品、方案和下载触发；最终回合Skill 5 success、Skill 6按授权跳过 | Pass | [方案](evidence/final-plan.png) · [轨迹](evidence/review-normal-trace.png) |
| API 回退 | Desktop 1440×1000 | Skill 1 fallback，客户页无技术错误 | 关闭LLM后Skill 1 fallback，Skills 2/3 success；客户页未显示API或技术错误 | Pass | [回退轨迹](evidence/review-fallback-trace.png) |
| 无匹配 | Desktop 1440×1000 | Skill 3返回0件，Skills 4/5跳过 | 500件、100元、Logo、3天、寄美国返回0件；无选择按钮；Skills 4/5 skipped | Pass | [0结果轨迹](evidence/review-no-match-trace.png) |
| 未授权 | Desktop 1440×1000 | Skill 6 skipped，方案继续 | 未勾选授权时方案与下载正常，Skill 6 skipped | Pass | [未授权轨迹](evidence/review-consent-skipped.png) |
| 已授权 | Desktop 1440×1000 | Skill 6 saved，rerun幂等 | 临时SQLite写入1条选择；页面rerun后仍为1条；Trace只显示saved状态，不显示URL/UUID | Pass | [授权保存](evidence/review-consent-saved.png) |
| 数据库故障 | Desktop 1440×1000 | Skill 6 degraded，客户流程继续 | 授权但无仓库时Skill 6 degraded；选品和最终方案继续；客户页无数据库错误 | Pass | [存储降级](evidence/review-storage-degraded.png) |
| 手机布局 | Mobile 390×844 | 无横向滚动，主操作和 Trace 可访问 | `scrollWidth <= clientWidth`；3张卡同列、图片324×243；聊天框和评审Trace可访问 | Pass | [手机页面](evidence/customer-mobile.png) |

## 检查口径

- 用页面 `scrollWidth <= clientWidth` 判断横向溢出。
- 通过可见标题、按钮、推荐卡、方案区和 Trace 状态确认流程。
- 截图只使用预设演示输入，不包含真实 Key、数据库地址或客户资料。
- 授权保存和存储降级分别使用本地临时数据库与无仓库配置，不连接生产数据库。

## 额外安全与交互结果

- 仅 `review_mode=1`、环境开关关闭：Trace隐藏。
- 环境开关开启、无URL参数：Trace隐藏。
- 配置可选Token后，错误或缺失Token隐藏Trace；正确Token显示Trace。
- Trace页面未发现聊天原文之外的联系方式、Key、数据库URL、SQL、内部UUID或异常堆栈。
- 客户流程实际完成一轮追问、立即推荐、推荐解释、选品、方案、下载触发、需求修改重算和重新开始。
- 所有本地Streamlit验收服务均已关闭；临时SQLite已删除。
