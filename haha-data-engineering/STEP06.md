# 第六课：Airflow 自动执行完整任务链

## 实际环境

- Windows 上已有 Ubuntu WSL2；本次使用它运行 Airflow。
- WSL：Python 3.12、Java 17、Airflow 3.1.0、PySpark 3.5.6。
- Airflow 使用官方约束文件安装，具体版本见 `airflow/installed-requirements.txt`。
- 虚拟环境：`/home/harrychen901/.local/share/haha-airflow/venv`。
- 元数据库、运行日志、登录信息：`/home/harrychen901/.local/share/haha-airflow/home`。
- 本地学习环境使用 standalone、LocalExecutor 和 SQLite。
- Windows 原有 Spark 虚拟环境仍可运行前五步。

## 本步实现的自动化

在网页点一次触发后，Airflow 自动完成：

```text
products → dimension → events → details → metrics → verify_run
```

分别对应商品整理、维度关联、模拟日志、明细清洗、每日统计、整体验收。
每步成功才开始下一步，每个 Spark 作业用 spark-submit 提交。
这里使用 Airflow TaskFlow 包装 spark-submit，不使用 SparkSubmitOperator。
数据文件保存在练习目录，XCom 只传本次结果路径。

每个 DAG run 的输出独立在 `output/airflow/运行ID哈希/` 下。
重试按 try_number 写新目录，不读取失败尝试的残留文件。
给前五步增加了可选 `--output-dir`，手动运行命令继续可用。
最关键的变化：任务间传本次输出，完全不依赖之前固定的练习结果或“最新目录”。

**当前是手动触发后自动执行整链，schedule=None，尚未设置每天定时。**
默认 10000 个会话，可在触发参数中选择 100～10000。
教学模拟时间窗口仍固定；维度采集标签 2026-09-07，指标观察时间 2026-09-11，
均为教学配置，不能把这条 DAG 当成真实历史数据的每日增量流水线。

## 打开网页和登录

访问 http://localhost:8088 ，用户名 `admin`。
密码由 Airflow 随机生成并保存在 WSL，查看命令：

```powershell
wsl -d Ubuntu -- cat /home/harrychen901/.local/share/haha-airflow/home/simple_auth_manager_passwords.json.generated
```

密码不会写入项目代码或此文档。
进入 DAG 列表，选择 `haha_learning_pipeline`，可查看图、任务状态与每个任务的日志。
点击触发按钮，保持 sessions=10000，即可重跑一整条。

## 启动、停止和命令行触发

后台启动（已经运行时不会重复启动）：

```powershell
wsl -d Ubuntu -- python3 /mnt/f/HC/hackathon/haha-data-engineering/airflow/service.py start
```

查看服务状态：

```powershell
wsl -d Ubuntu -- python3 /mnt/f/HC/hackathon/haha-data-engineering/airflow/service.py status
```

触发新的完整运行：

```powershell
wsl -d Ubuntu -- bash /mnt/f/HC/hackathon/haha-data-engineering/airflow/cli.sh dags trigger haha_learning_pipeline
```

停止本练习服务：

```powershell
wsl -d Ubuntu -- python3 /mnt/f/HC/hackathon/haha-data-engineering/airflow/service.py stop
```

重启 Windows 或关闭 WSL 后需要重新启动。此步没有注册开机服务。
Airflow 绑定 127.0.0.1:8088；服务启动日志位于 WSL 的
`~/.local/share/haha-airflow/standalone.log`。

## 失败时会怎样

- 作业非零退出或校验失败，该任务失败；下游不会拿到成功输出。
- 前五个任务配置一次重试，间隔 20 秒；每任务超时 25 分钟，Spark 子进程超时 20 分钟。
- max_active_runs=1，防止多次全量运行同时占用本机资源。
- verify_run 最后再次核对跨阶段数量，输出 pipeline_validation.json。
- 本步验证正常完整运行；故障注入、补数和幂等发布放在下一步。

## 学习顺序

本次完整验证已通过：run_id 为 `learning_full_20260907_v1`，六个任务全部一次成功，
约 5 分 5 秒；商品 54、会话 10000、推荐商品明细 30000、选择 6429。
对应输出为 `output/airflow/bb864b1b9297e08e0143/`。

1. 先在网页看六个节点，理解依赖关系。
2. 打开 `airflow/dags/haha_learning_pipeline.py`，看最底部任务如何连接。
3. 看 run_step：任务怎样提交 Spark、保存结果、返回路径。
4. 看 verify_run：怎样证明同一批数据走完了全流程。
5. 看 `airflow/verification.json` 与对应输出的 pipeline_validation.json 对照状态及数据数量。

核心概念：DAG、Task、Dag Run、Task Instance、XCom、重试、调度器和执行器。

官方安装依据：https://airflow.apache.org/docs/apache-airflow/3.1.0/start.html
