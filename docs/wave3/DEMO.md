# W3 产品 Demo 脚本

## 启动

```powershell
python -m pip install -e .[dev]
python -m streamlit run app.py
```

打开 `http://localhost:8501`。不配置 DeepSeek Key 也能完成完整演示。

评审 Trace 需要同时设置 `$env:AGENT_REVIEW_MODE_ENABLED="true"` 并访问 `http://localhost:8501/?review_mode=1`；普通 URL 始终保持客户模式。

## Demo A：单页顾问主路径（约 3 分钟）

1. 在首屏点击一个快捷入口，或输入：`想给海外合作伙伴准备一份有中国文化特色的礼物`。
2. 回答顾问的问题，例如预算、数量和对象。观察每轮只出现一个问题，且总轮数不超过 5。
3. 展开需求摘要，说明明确条件与暂时推测分开显示；软推断带理由，用户可以改写覆盖。
4. 信息足够时让顾问自动推荐，或点击“先为我推荐”。无需切换页面即可看到最多 3 个图文方案。
5. 展开“为什么推荐给我？”查看硬约束、匹配原因和排序解释。
6. 选择一个礼品，在同一页查看文化内容与最终礼赠方案，并下载 JSON。

预期：用户完成从模糊需求到可交付方案的闭环，页面上不暴露 Agent、Skill、Wave、parser、API 状态或调试术语。

## Demo B：修改偏好与无结果

1. 在“调整需求”里修改预算或明确风格，再重新推荐，观察结果随用户明确值重新计算。
2. 将单件预算设为 `100` 元、数量设为 `1` 后推荐。

预期：无合格商品时返回 0 个结果，并说明冲突和可选调整方向；不会虚构一个可购买商品。

## Demo C：无 API 与数据库故障

1. 不配置 `DEEPSEEK_API_KEY`，输入自然语言需求并完成主流程。
2. 保持 `ANALYTICS_ENABLED=false`，或配置不可用的测试数据库地址后完成推荐和选品。

预期：页面只给出顾客可理解的回退提示，推荐流程继续；不暴露 Key、Prompt、数据库异常或堆栈。

## Demo D：匿名选择与幂等

1. 在选品前勾选“允许保存匿名选择用于改进推荐”。
2. 选择一个方案，重复刷新或重复运行同一会话。
3. 在本地 SQLite 中核对：同一推荐事件和同一选择只保存一次；选择另一商品时新增一条选择。

预期：未同意时零写入；同意后只保存匿名结构化字段，不保存原始聊天、姓名和联系方式。

## Demo E：合成数据聚合分析

```powershell
python scripts/generate_synthetic_choice_data.py --sessions 50
python skills/analyze-gift-choice-signals/scripts/analyze_choices.py --format table
python skills/analyze-gift-choice-signals/scripts/analyze_choices.py --scene anniversary --format json
```

预期：展示推荐/选择次数、产品与排名选择率、场景和预算分布、平均对话轮数；报告明确声明数据为合成演示数据。将最小样本调高后，小分组百分比应被隐藏并显示样本不足提示。

## Demo F：数据库故障

将分析地址改为不可用的本地测试地址后完成推荐、选品和最终方案。预期客户流程不崩溃，也不显示 SQL、数据库类型、URL、UUID 或内部错误类别。

## Demo G：四条 Agent 轨迹

1. 输入“给30位美国合作伙伴准备周年礼品，每件预算1000元，需要Logo，30天内完成。”，完成推荐、选择和方案；观察 Skills 1–6 门控顺序。
2. 关闭 LLM 或不配置 Key；观察 Skill 1 为 `fallback`，Skills 2–3 正常继续。
3. 输入“500件，每件100元，必须Logo，3天交付并寄往美国。”；观察 Skill 3 返回0件，Skills 4–5 跳过。
4. 分别在未授权、授权+本地库、授权+不可用库下选品；观察 Skill 6 为 `skipped/success/degraded`，客户流程均继续。

可直接运行 `python -m pytest tests/test_agent_orchestration.py -q` 复现这些门控结果。

## 录屏建议

- 0:00–0:30：用户问题与一句话价值。
- 0:30–1:15：自然语言、多轮单问题追问和受控推断。
- 1:15–2:10：同页推荐、解释与偏好修改。
- 2:10–2:50：选品、文化内容与最终方案。
- 2:50–3:20：无结果、无 API/数据库回退与隐私边界。

提交前补充：在线 Demo URL、演示视频 URL、最终 commit、交叉评审日期与记录。

本地真实浏览器验收截图见 [`BROWSER_ACCEPTANCE.md`](BROWSER_ACCEPTANCE.md)；截图中的输入均为预设演示数据。
