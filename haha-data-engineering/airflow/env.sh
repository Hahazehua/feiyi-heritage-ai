#!/usr/bin/env bash
# 只影响当前 shell；元数据库在 Linux 文件系统，避免 Windows 挂载盘锁问题。
export HAHA_PROJECT=/mnt/f/HC/hackathon/haha-data-engineering
export HAHA_RUNTIME="$HOME/.local/share/haha-airflow"
export AIRFLOW_HOME="$HAHA_RUNTIME/home"
export PATH="$HAHA_RUNTIME/venv/bin:$PATH"
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PYSPARK_PYTHON="$HAHA_RUNTIME/venv/bin/python"
export SPARK_LOCAL_IP=127.0.0.1
export AIRFLOW__CORE__DAGS_FOLDER="$HAHA_PROJECT/airflow/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__PARALLELISM=2
export AIRFLOW__API__HOST=127.0.0.1
export AIRFLOW__API__PORT=8088
export AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS=admin:admin
export AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://127.0.0.1:8088/execution/
