# HAHA 推荐行为数据工程项目

个人学习项目｜Python · PySpark · Spark SQL · Apache Airflow · Parquet · Streamlit · WSL2

## 项目介绍

基于 54 件演示商品与 30 天模拟推荐行为，建立商品维度、行为明细与每日分析指标。使用 Spark 进行类型校验、去重、关联和聚合，使用 Airflow 串联任务并验证定时调度、重试、历史补数与按日期幂等发布。看板展示 10,000 次模拟推荐、30,000 条推荐商品明细和 6,429 次选择。

数据流程：商品 CSV → 商品维度 → 模拟行为 JSONL → 去重后的 DWD Parquet → 每日 DWS/ADS → 按日期发布 → Streamlit 看板。

## 英文简历要点

**HAHA Recommendation Analytics Pipeline | Personal Project**

- Built a PySpark batch pipeline combining 54 demo products with 30 days of synthetic behavior data; validated and deduplicated events to produce 30,000 recommendation-item records and daily product and funnel metrics.
- Orchestrated Spark tasks with Apache Airflow; verified daily scheduling, automatic recovery from an injected failure, three historical backfill intervals, and idempotent publication with atomic catalog updates.
- Built a Streamlit dashboard and benchmarked broadcast joins and partition pruning on 100K- and 1M-row synthetic datasets, recording physical plans, result checksums, and median latency across three measured runs.

## 中文简历要点

- 使用 PySpark 构建商品与模拟行为数据处理链，完成类型检查、事件去重、维度关联和每日指标聚合，产出 3 万条推荐商品明细。
- 使用 Airflow 编排任务，实际验证每日调度、故障重试、三天历史补数及按日期幂等发布，并以原子目录索引更新保障看板读取完整结果。
- 搭建 Streamlit 分析看板，在十万和百万行模拟数据上比较广播关联与分区裁剪，保存物理计划、校验和及三次运行中位耗时。

以上表述对应已经完成的项目工作；正式投递前要能独立解释代码与设计。不要使用“服务百万真实用户”“提升业务转化率 64%”“实现分布式生产高可用”等没有证据的表述。

## 三分钟演示流程

| 时间 | 展示内容 | 说明重点 |
|---|---|---|
| 0:00–0:30 | 看板每日概览 | 明确是模拟数据；解释推荐次数与展示商品数 |
| 0:30–1:00 | 原完整 DAG | 五步 Spark 作业的依赖关系，XCom 只传路径 |
| 1:00–1:40 | 每日 DAG 历史运行 | 展示 scheduled、backfill，以及 retry 任务尝试次数 2 |
| 1:40–2:10 | 发布验收记录 | 重复运行 changed=[]，catalog 哈希相同 |
| 2:10–2:40 | 性能实验报告 | 说明广播小表与分区筛选，并解释微基准边界 |
| 2:40–3:00 | 项目限制与后续方向 | 本地批处理；未来可接实际日志、对象存储、数据库和监控 |

## 面试时需要能回答的问题

1. 为什么必须先去重再聚合？重复推荐事件会扩大分母和展示量。
2. 为什么选择要关联回推荐？不选中的商品也要留在分母中，所以使用 LEFT JOIN。
3. event_time 与 ingested_at 有什么区别？前者归属业务日期，后者决定观察截止时是否可见。
4. 为什么等待 73 小时？本模拟允许 24 小时内选择，另给 49 小时到达容忍；不等同于生产 SLA。
5. Airflow 做什么、Spark 做什么？Airflow 控制何时执行及先后依赖，Spark 执行数据计算。
6. retry 和 backfill 有什么不同？retry 重试一次任务尝试，backfill 为历史业务区间创建运行。
7. 为什么重复执行不多算？相同内容生成相同版本，发布操作替换日期指针，而不是追加计数。
8. 为什么不声称 exactly-once？这是单机文件锁与原子索引更新，未覆盖分布式事务、外部系统副作用和主机故障恢复。
9. 广播关联何时有帮助？小表能安全装入执行器内存时避免大表 shuffle；不能盲目广播大表。
10. 为什么性能结论有限？本机两槽、热缓存、合成数值行、短时微基准，不是生产全链吞吐量。

## 展示材料入口

- STEP06.md：原始完整 Airflow 流程与环境。
- STEP07.md：日期参数、幂等发布、补数与重试。
- STEP08.md：看板与性能报告。
- LEARNING_LOG.md：逐步完成记录。
- airflow/verification.json 与 airflow/step07_verification.json：运行证据。

尚未上传代码托管平台，也没有录制演示视频。本文件提供可自行演示的流程；依赖本机固定路径的设置在 env.sh 和脚本中明确列出，迁移电脑需调整路径并重新生成上游快照。
