# 第三课：生成模拟推荐与选择日志

## 本步目的

前两步回答“商品是什么”。本步准备“发生了什么”的行为数据，
为下一步清洗事实表、计算推荐与选择指标提供输入。
所有事件均标记 `data_source=synthetic_demo`，不代表真实用户行为。

## 输入和生成规则

- 固定使用第二步 `output/step02_20260907_201837_082177/dim_product_snapshot`。
- 只从 `catalog_role=recommendation_demo` 的商品抽样，排除目录参考与待核实角色。
- 默认 10000 个模拟会话，随机种子 42，30 天内产生会话和推荐。
- 默认窗口为 2026-08-08 至 2026-09-06，UTC。选择可在推荐之后跨天发生；
  日志还可能晚到，因而到达日期目录可能超出这个窗口。
- 使用固定商品快照模拟这一时间窗口，不声称还原过去的真实目录。
- 每个会话一次推荐，每次三个不同商品。
- 按人为设定的 65% 概率生成选择，选择排名权重为 6:3:1。
- 已选择会话以 30% 概率标记“生成定制方案”；只有模拟标记，不实际生成方案文档。
- 场景和预算为随机标签，商品随机抽样；本步没有调用 HAHA 推荐算法，
  不能用这些数据评价真实推荐效果或预算匹配效果。
- 每 100 个会话重复投递一次推荐事件（事件 ID 与全部内容相同）。
- 每 20 个会话的一组日志延迟约 48 小时到达。
- 选择在推荐后 1 分钟至 23 小时内发生，可能跨日。

## 三类输出：每行一个 JSON 对象（JSONL）

| 事件类型 | 一行代表什么 | 主要字段 |
|---|---|---|
| session | 一次会话开始 | anonymous_session_id、scene、budget_per_item_fen |
| recommendation | 一次推荐展示 | recommendation_event_id、recommended_product_ids、ranking_positions、match_scores |
| selection | 一次选择 | selection_event_id、recommendation_event_id、selected_product_id、selected_rank_position |

共同字段：event_id、event_type、event_time、ingested_at、data_source、schema_version。
`event_time` 是事件发生时间；`ingested_at` 是模拟日志到达时间。
推荐数组里的第一个商品对应第一个排名和第一个分数。
没有选择的会话仍保留 session 和 recommendation，后续才能获得完整分母。
预算用整数分，与商品价格单位一致。
沿用原项目主要 ID 与推荐、选择字段；这是教学用 v1 事件格式，并非直接导入原数据库的完整记录。

## 运行

```powershell
Set-Location 'F:\HC\hackathon'
.\.venv\Scripts\python.exe .\haha-data-engineering\step03_generate_events.py
```

调整规模示例（创建新批次，不覆盖已有文件）：

```powershell
.\.venv\Scripts\python.exe .\haha-data-engineering\step03_generate_events.py --sessions 1000 --seed 42 --start-date 2026-08-08 --days 30
```

本版默认 1 万会话：生成器逐条写出，但独立验证器在 Python 内存中保存唯一事件；
百万规模需要先把完整关联检查迁移到 Spark，不能把本版视为百万规模基准。

## 输出在哪里

`output/step03_运行时间/`：

```text
session/ingest_date=YYYY-MM-DD/part-00000.jsonl
recommendation/ingest_date=YYYY-MM-DD/part-00000.jsonl
selection/ingest_date=YYYY-MM-DD/part-00000.jsonl
manifest.json
_SUCCESS
```

`manifest.json` 记录数量、参数、商品范围、源维度路径、文件 SHA-256 及检查结果。
相同输入、种子与参数产生相同的事件内容；输出批次目录名随运行时间不同。
JSONL 按到达日期保存，不代表已完成按事件日期的业务汇总。

## 验证了什么

1. 生成会话数与输入参数一致，每个会话均有推荐。
2. 推荐商品存在于选定商品集合，数组数量和排名正确。
3. 选择属于对应会话和推荐，商品与排名一致，时间在推荐后 24 小时内。
4. 重复 ID 的内容必须相同；重复保留在原始层，下一课再去重。
5. 到达时间不得早于事件发生时间。
6. 用 Spark 实际读取三类文件，核对行数，并检查公共时间字段能解析。
7. 单元测试覆盖可复现性、错误商品、冲突重复、错误时间、参数和文件保护。

完整业务字段由独立 Python 回读校验；本步 Spark 回读只指定公共字段类型。
下一课将为完整事件定义 Spark Schema，并输出明细 Parquet。

## 以后学习时的阅读顺序

先看 `generate_events` 理解记录如何产生，再看 `write_events` 理解 JSONL 和日期目录，
最后看 `validate_events` 理解会话、推荐和选择如何通过 ID 对应。
核心概念：事件、主外键、随机种子、重复投递、事件时间、到达时间。

下一步：Spark 读取原始日志，按事件 ID 去重，展开推荐数组，生成推荐与选择明细表。
