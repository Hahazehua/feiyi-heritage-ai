"""只读导出指定 DAG run 的状态证据，不读取密码或连接凭据。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--run-id", default="learning_full_20260907_v1")
args = parser.parse_args()
db = Path.home() / ".local/share/haha-airflow/home/airflow.db"
with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
    connection.row_factory = sqlite3.Row
    run = connection.execute("SELECT dag_id, run_id, state, start_date, end_date FROM dag_run WHERE dag_id=? AND run_id=?", ("haha_learning_pipeline", args.run_id)).fetchone()
    tasks = connection.execute("SELECT task_id, state, try_number, start_date, end_date FROM task_instance WHERE dag_id=? AND run_id=? ORDER BY start_date", ("haha_learning_pipeline", args.run_id)).fetchall()
with urllib.request.urlopen("http://127.0.0.1:8088", timeout=10) as response:
    status = response.status
report = dict(captured_at=datetime.now(timezone.utc).isoformat(), run=dict(run) if run else None,
              tasks=[dict(t) for t in tasks], ui_http_status=status,
              all_tasks_success=len(tasks) == 6 and all(t["state"] == "success" for t in tasks))
target = Path("/mnt/f/HC/hackathon/haha-data-engineering/airflow/verification.json")
target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
