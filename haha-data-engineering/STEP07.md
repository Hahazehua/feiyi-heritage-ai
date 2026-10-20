# 第七步：调度、重试、补数、幂等发布

这一步解决的是：原先需要人手动运行的流程，如何按日期执行，失败后如何恢复，重跑如何避免重复累计。

## 实际完成的工作

1. 保留第六步完整 DAG `haha_learning_pipeline`，仍可手动运行五个 Spark 作业并验收。
2. 新增 `haha_daily_publish`：每个 UTC 零点调度一次。调度器已真实产生一次 scheduled 运行并成功，不只是写了定时配置。
3. 将第六步已验证的 DWD 和商品维度固定为输入快照。输入 Parquet 内容计算 SHA-256，不会每天重新生成一批随机行为。
4. Spark 按 `ingested_at <= as_of` 计算截至某时刻可见的指标。业务日期使用推荐发生日期；选择跨天仍归回推荐日期。
5. 每日默认更新最近四个业务日，覆盖 24 小时选择窗口加 49 小时晚到容忍。未满 73 小时的比例不展示。
6. 注入一次故障。`step07_retry` 的 recovery_gate 第一次失败，第二次自动成功；下游随后发布。
7. 重跑同一批 30 天数据。`step07_idempotent` 的 changed 为空，30 天全部 unchanged，发布目录哈希不变。
8. 通过 Airflow 原生 backfill 创建 2026-08-08、09、10 三个历史区间，全部成功。已有日期重放不重复累计；另用隔离目录测试补齐缺失日期。
9. 六项发布测试通过：幂等、故障隔离、旧截止时间不能回退、损坏缓存拒绝、缺日补齐、未闭合窗口不展示比例。

## 任务链

```mermaid
flowchart LR
 A[固定 DWD + 维度] --> B[Spark 按观察截止时间计算]
 B --> C[重试演练关卡]
 C --> D[质量校验与按日期发布]
 D --> E[Streamlit 看板]
```

对应 DAG 中的 `compute_snapshot → recovery_gate → publish_metrics`。XCom 仅传路径，数据保存在项目 output 目录。

## 为什么重跑不会重复

每个业务日期的三张汇总表形成一个不可变 JSON 版本。版本名来自内容哈希，同样数据会得到同样名字。发布时先完成全部检查和文件写入，再原子替换 `catalog.json`，让看板一次看到完整版本。Linux 文件锁保护单机并发发布。

这属于聚合结果的本地 serving 层；DWD/DWS 原始输出仍是 Parquet。不是数据库事务，也不是分布式 exactly-once。计算失败留下的缓存不会自动成为发布结果。数据量小，汇总结果才允许 collect；生产大表需要分布式写入和表格式事务。

同一输入、计算逻辑、as_of 可复用已验证缓存；历史补数不必重复执行所有 Spark 转换。本次三个 backfill 使用已存在缓存，不能把其运行秒数理解为全量计算速度。

## 参数与时间

| 参数 | 含义 | 示例 |
|---|---|---|
| business_date | 最后一个要发布的业务日期 | 2026-09-06 |
| as_of | 只观察此前已到达的数据 | 2026-09-11T00:00:00Z |
| refresh_days | 包含该日期向前更新多少天 | 30 |
| fail_once | 让关卡第一次故意失败 | true |

不填日期时，定时/补数运行采用 Airflow 数据区间；无数据区间的手动运行采用该运行的 run_after，更新其前一天起的四天。每次运行的时间固定，重试不会改用另一个当前时间。

`2026-09-11` 是模拟观察时钟，目的是让全部模拟迟到日志到齐，不代表当天已经实际到来。较旧 as_of 不能覆盖较新的已发布日期。本项目没有接入持续产生的新日志，也没有流式 watermark；四天更新窗口只覆盖既定模拟迟到上限，超期更正需要显式历史补跑。

## 如何自己练习

先启动 Airflow，打开 http://localhost:8088。用户名 admin；密码查看方式在 STEP06.md。

```powershell
wsl -d Ubuntu -- python3 /mnt/f/HC/hackathon/haha-data-engineering/airflow/service.py start
```

在 `haha_daily_publish` 页面手动触发，填上表参数；观察 compute_snapshot 成功、recovery_gate 先失败再成功、publish_metrics 最后成功。

也可以一次提交重试和重复运行两次练习，运行名自动带时间：

```powershell
wsl -d Ubuntu -- python3 /mnt/f/HC/hackathon/haha-data-engineering/airflow/exercise_step07.py
```

执行发布测试：

```powershell
wsl -d Ubuntu -- bash /mnt/f/HC/hackathon/haha-data-engineering/airflow/run_python.sh /mnt/f/HC/hackathon/haha-data-engineering/test_step07.py
```

Airflow 3.1.0 本机 CLI 的 `backfill --dag-run-conf` 把 JSON 字符串直接传给参数对象导致异常。`airflow/backfill_step07.py` 是固定版本的兼容脚本：传入解码后的字典，调用 CLI 使用的同一个原生 backfill 函数。数据库 run_type 确认是 backfill，不是伪装的手动运行。它使用内部接口，升级版本后须重新检查。原三天已经执行，默认 none 策略不会重复创建；要练新日期可修改脚本日期范围。

调度时区是 UTC。运行时所在美东夏令时对应前一晚 20:00，冬令时 19:00。Windows/WSL 和服务必须保持运行；电脑关机不会执行任务，未配置开机自启。

## 证据与学习重点

- `airflow/step07_verification.json`：调度器、DAG run、每个任务状态、尝试次数和发布结果。
- `output/step07_tests.txt`：六项测试。
- `output/step07_runs/`：每次业务发布日期和 changed/unchanged 记录。
- `output/published/catalog.json`：看板唯一发布入口。

学习时先解释清楚 business_date 和 as_of 的区别，再看三个 task，最后看 publish 函数。能够解释“为什么失败时旧看板仍可用”和“为什么重跑不多算一遍”，比记住全部代码更重要。

参考：[Apache Airflow DAG Runs](https://airflow.apache.org/docs/apache-airflow/3.1.2/core-concepts/dag-run.html)。本机 3.1.0 的精确参数以已安装 CLI 帮助和兼容脚本为准。
