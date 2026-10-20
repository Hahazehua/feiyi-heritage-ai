# HAHA 数据工程第一课：CSV → Spark → Parquet

第二课已提供：[商品、商家、非遗项目关联](STEP02.md)。先跑通本页的第一课，再继续第二课。

持续更新的[学习进度记录](LEARNING_LOG.md)汇总每一步做了什么及验证证据。
第三课：[生成模拟推荐与选择日志](STEP03.md)。
第四课：[Spark 清洗与行为明细](STEP04.md)。
第五课：[每日商品与场景指标](STEP05.md)。
第六课：[Airflow 环境与自动任务链](STEP06.md)，本机页面 http://localhost:8088 。
第七课：[每日调度、重试、补数和幂等发布](STEP07.md)，已完成七次真实运行验收。
第八课：[性能实验与分析看板](STEP08.md)，看板 http://localhost:8501 。
求职展示：[中英文简历要点、面试问题与三分钟演示](PORTFOLIO.md)。

本课读取原项目的商品 CSV，制作一张商品维度基础表。每行代表一件商品。
输入包含演示商品、目录参考及待核实合作商品；数据状态保留在输出中。

## 在这台 Windows 电脑上运行

打开 PowerShell，执行：

```powershell
Set-Location 'F:\HC\hackathon'
.\.venv\Scripts\python.exe .\haha-data-engineering\step01_products.py
```

Python 环境位于 `F:\HC\hackathon\.venv`，无需激活。
已安装 PySpark 3.5.6 和 Py4J 0.10.9.7，使用电脑已有的 Python 3.11.4、Java 17。
本课尚未引入 Airflow。

## 执行时观察什么

1. `printSchema()` 显示字段结构。商品 ID 是字符串，价格分是 long，演示标记是 boolean。
2. `show(5)` 展示前五件商品。第一件商品最低价格为 98000 分，即 980.00 元。
3. 用途统计应为 `catalog_reference=30`、`recommendation_demo=23`、`partner_pending_verification=1`。
4. 最后看到“第一步完成！”以及检查报告。

这份源文件当前应有 54 行、54 个不同商品 ID、0 条异常记录。
脚本根据实际输入行数检查，不会通过强行截取或补齐让数据满足 54 行。

## 找到输出

每次运行会创建一个新的 `output/运行时间/` 文件夹，其中有：

```text
dim_product/
    part-....snappy.parquet
    _SUCCESS
validation.json
```

`dim_product` 是一组 Parquet 文件组成的表目录；读取时传整个目录。
`validation.json` 记录输入与输出行数、主键检查、类型与全部字段值的回读比较。
Parquet 是列式文件格式，不是数据库服务。
失败运行留下的目录不算成功结果；以“第一步完成”和检查报告为准。

## 按这个顺序阅读脚本

| 代码 | 含义 | 小练习 |
|---|---|---|
| `SparkSession.builder` | 创建 Spark 入口；`local[2]` 用本机两个任务槽 | 找到应用名称，改成自己的名字 |
| `spark.read...csv(...)` | 读取 CSV，得到 DataFrame | 观察表头与 Schema 的关系 |
| `raw.select(...)` | 选字段并明确类型 | 在选择列表中增加 `region_code` |
| `withColumn(...)` | 派生新字段 | 类似最低价，增加最高价的元字段 |
| `groupBy(...).count()` | 分组计数 | 将用途统计换成 `category_code` 统计 |
| `write.parquet(...)` | 将处理结果写为 Parquet | 找到本次新生成的目录 |
| `spark.read.parquet(...)` | 重新读取已写入的表 | 检查报告中两个 equal 字段为 true |

`select`、`withColumn` 等主要描述计算步骤；`show`、`count`、写入会触发执行。
本课为 54 行教学数据，会执行多次检查；大规模作业需要另行评估重复计算和缓存。
输出仅整合商品自身字段，商家和非遗维度关联放到下一课。

## Windows 环境说明

Windows 本地写文件需要 Hadoop 的原生组件。本练习使用社区仓库
`cdarlint/winutils` 的 Hadoop 3.3.5 版 `winutils.exe` 与 `hadoop.dll`，
并非 Apache 发布的 Windows 二进制包。下载固定在提交
`7386986d5d8a079b5cd4464f4599766dd27e7d13`，文件 URL 与 SHA-256 记录在
`tools/native-dependencies.json`。Spark 自带 Hadoop Java 客户端为 3.3.4，
本机功能是否通过以运行报告为准，不代表所有 Hadoop 功能的兼容性认证。

脚本只为当前进程设置 HADOOP_HOME 和 PATH，不更改系统设置。
原商品 CSV 只读取，输出始终放在练习目录。

若终端出现 `ModuleNotFoundError: pyspark`，请使用上面的完整 Python 路径，
不要换成全局的 `python` 或 `py`。
若出现 `JAVA_GATEWAY_EXITED`，先检查 `java -version` 及 JAVA_HOME。
若出现 `winutils.exe` 或 `NativeIO` 错误，检查 `tools/hadoop-3.3.5/bin` 的两个文件。

参考资料：
- https://spark.apache.org/docs/3.5.6/api/python/getting_started/install.html
- https://spark.apache.org/docs/3.5.6/sql-data-sources-csv.html
- https://cwiki.apache.org/confluence/spaces/HADOOP2/pages/120730292/WindowsProblems
