#!/usr/bin/env bash
set -euo pipefail
source /mnt/f/HC/hackathon/haha-data-engineering/airflow/env.sh
mkdir -p "$HAHA_RUNTIME" "$AIRFLOW_HOME"
python3 -m venv "$HAHA_RUNTIME/venv"
python -m pip install 'apache-airflow==3.1.0' --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.1.0/constraints-3.12.txt
python -m pip install 'pyspark==3.5.6'
python -m pip check
python -m pip freeze > "$HAHA_PROJECT/airflow/installed-requirements.txt"
