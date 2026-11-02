# 第八步：性能实验、看板与简历展示

## 这一步做了什么

1. 用 Spark 生成 100,000 和 1,000,000 行数值模拟数据，分别比较两种关联策略与分区读取策略。
2. 每组预热一次，交替顺序测三次，取中位数。每次重新建立查询计划，避免复用已经完成的 shuffle。保存作业 ID、全部耗时、结果校验和与物理执行计划。
3. 制作 Streamlit 看板，三个页面分别为每日概览、商品与场景、工程验收。
4. 验证全量指标和日期筛选；看板只读取已发布版本，汇总文件哈希不匹配会停止展示。
5. 整理中文/英文简历要点、三分钟演示流程、面试问题。

## 看板如何打开

当前地址：http://localhost:8501 。重启电脑后在 PowerShell 执行：

```powershell
& 'F:\HC\hackathon\haha-data-engineering\start-dashboard.ps1'
```

看板使用本机 E:\python.exe，Streamlit 1.59.2、pandas 2.3.3；版本见 requirements-dashboard.txt。Airflow/Spark 使用 WSL 独立环境，二者通过项目输出目录衔接。

已验证全日期范围：推荐 10,000、展示商品 30,000、选择 6,429、简报 1,895，推荐转化率 64.29%。选择 8 月 8 日至 10 日后：推荐 1,014、选择 669、简报 198。页面没有运行异常，服务健康检查返回 200。

推荐转化率 = 选择次数 / 推荐次数。商品选择率 = 选择次数 / 展示商品数。不能将分组比例简单平均；先加分子和分母再算。模拟排名偏好造成的选择差异不构成真实市场结论。

## 性能实测

环境：WSL2、Spark 3.5.6、Python 3.12.3、local[2]、shuffle 分区 2；关闭 AQE 和自动广播，通过提示明确对比 BroadcastHashJoin 与 SortMergeJoin。维度表 1,000 行，文件按 event_day 分成 30 个分区。

| 行数 | 广播关联 | 排序合并关联 | 分区筛选 | 全扫描条件求和 |
|---:|---:|---:|---:|---:|
| 100,000 | 0.107 秒 | 0.193 秒 | 0.085 秒 | 0.167 秒 |
| 1,000,000 | 0.082 秒 | 0.280 秒 | 0.067 秒 | 0.090 秒 |

均为三次 collect 耗时的中位数，包括查询执行而不含 Python 构造表达式、Spark 启动、输入生成和首次写盘。关联测试使用内存生成的 range 逻辑计划；分区测试使用 WSL 临时目录中的 Parquet。

百万行实验广播关联约为排序合并关联的 3.39 倍速度；分区筛选约为全扫描条件求和的 1.35 倍速度。两两校验和完全相等，执行计划分别包含 BroadcastHashJoin、SortMergeJoin 和分区过滤条件。

这是单机热缓存微基准，耗时很短，顺序、JIT 和操作系统缓存影响较大。百万行比十万行更快的部分结果体现这一影响，不说明大数据越多越快。不能把这些数字写成生产端到端加速，也不能声称完成百万真实事件的完整 ETL。

最初直接重复 collect 同一个 DataFrame 会复用已完成的 shuffle，导致数十毫秒的误导性结果。最终脚本改为每次新建查询计划，并记录实际 Spark job ID；报告使用修正后的结果。这是一次值得在面试中解释的实验方法改进。

重新运行实验：

```powershell
wsl -d Ubuntu -- bash /mnt/f/HC/hackathon/haha-data-engineering/airflow/run_python.sh /mnt/f/HC/hackathon/haha-data-engineering/step08_benchmark.py
```

证据：`output/benchmark/results.json`、同目录八份 `plan_*.txt`、`output/benchmark_run.log`。重跑会更新这些实验文件。

## 学习与求职材料

阅读 PORTFOLIO.md 中的项目介绍、简历要点和三分钟演示流程。先自己完整演示，再使用能独立解释的简历内容。本项目属于个人学习项目，不写成公司生产系统或真实经营成果。
