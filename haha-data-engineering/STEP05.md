# 第五课：明细变成每日分析指标

## 输入与处理

固定读取第四步已验证批次 `output/step04_20260907_203332_934029`，
使用第二步商品维度补充名称、品类、商家和演示标记。

```text
推荐商品明细 + 选择明细
    ↓ 按推荐ID、会话、来源、商品、排名左连接
每条推荐商品是否被选择、是否有定制方案标记
    ↓ 按推荐日期及商品/场景预算聚合
每日商品表 + 每日场景预算表 + 每日概览
```

左连接保留未选择商品，选择数填 0。输入主键、维度主键和关联完整性先检查。
每张汇总表的推荐商品数、选择数、方案标记数都与明细总数核对。
本步信任第四步的 v1 契约：每推荐最多一次选择；不是任意行为数据通用聚合器。

## 三张表及粒度

| 表 | 每行代表 |
|---|---|
| dws_product_daily | 推荐日期 × 数据来源 × 商品 |
| ads_scene_budget_daily | 推荐日期 × 数据来源 × 场景 × 单件预算 |
| ads_daily_overview | 推荐日期 × 数据来源 |

商品表含 product_name_zh、category_code、merchant_name_zh、catalog_role、is_demo。
所有汇总含模拟来源、观察截止时间、晚到容忍时长和窗口是否完整。
仅输出存在推荐的组合，不补齐从未推荐商品或空日期的零值行。

## 指标口径

- recommendation_item_count：推荐商品明细行数。
- recommendation_count：去重推荐事件数。
- selection_count：匹配的选择数。
- customization_brief_count：模拟方案生成标记数，没有实际生成订单或文档。
- selection_rate：选择数 / 推荐商品明细数。
- recommendation_conversion_rate：选择数 / 推荐事件数，仅概览和场景表保留。

示例：一次推荐 3 件商品，用户选了 1 件。
商品选择率是 1/3；推荐转化率是 1/1。两个比例的分母不同，不能混用。
跨天选择按原推荐日期归属，不能直接拿某天的选择数除以某天的推荐数。
本项目仍无订单、GMV或真实成交率。

## 观察窗口与晚到

默认 `--as-of 2026-09-11T00:00:00Z` 是模拟观察截止时间，不是电脑当前时间，
选择这个时间是为覆盖这批模拟日志的全部选择和延迟到达。
读取时只计算到达时间不晚于截止时间的记录。

选择窗口 24 小时，加上默认晚到容忍 49 小时，共等待 73 小时。
49 小时覆盖第三步人为设置的 48 小时 30 秒到达延迟。
组内所有已观察推荐超过该窗口，is_window_complete 才为 true。
未完整时计数仍展示当前观察值，但两个比例留空，避免把“尚未观察到”当作无选择。
超过容忍范围的真实迟到、丢失推荐或上游停机不能由这个标记保证，需要后续调度监控。
日期和时间统一 UTC。

## 运行与输出

```powershell
Set-Location 'F:\HC\hackathon'
.\.venv\Scripts\python.exe .\haha-data-engineering\step05_daily_metrics.py
```

`output/step05_运行时间/` 内包含三张按 metric_date 分区的 Parquet 表、
validation.json 和整批成功标记。每次运行新建目录，尚未做增量覆盖和 Airflow。

提前观察练习：

```powershell
.\.venv\Scripts\python.exe .\haha-data-engineering\step05_daily_metrics.py --as-of 2026-09-06T12:00:00Z
```

这将生成另一份批次；靠近截止时间的组比例应留空，部分晚到选择尚不计入。
测试命令：

```powershell
.\.venv\Scripts\python.exe .\haha-data-engineering\test_step05.py
```

测试用可手算样本核对两个分母、跨天归属、零选择保留、晚到过滤、窗口边界、重复维度和错误关联。

## 学习顺序

打开 step05_daily_metrics.py：先读 prepare 理解左连接，再读 aggregate 理解分组统计与分母，
然后看 build_metrics 如何复用聚合逻辑生成三张表，最后看 main 的总数核对与回读验证。
目前是模拟统计，只能用于验证工程和指标口径，不代表真实消费者偏好。

下一步：把手动运行的流程接入 Airflow。Windows 上需要先准备可运行 Airflow 的 Linux 环境。
