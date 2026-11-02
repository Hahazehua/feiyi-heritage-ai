"""Read-only task, scheduler and publication evidence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
db = Path.home() / ".local/share/haha-airflow/home/airflow.db"
with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
    con.row_factory = sqlite3.Row
    runs = [dict(r) for r in con.execute("SELECT run_id,run_type,state,logical_date,start_date,end_date FROM dag_run WHERE dag_id='haha_daily_publish' ORDER BY start_date")]
    tasks = [dict(r) for r in con.execute("SELECT run_id,task_id,state,try_number FROM task_instance WHERE dag_id='haha_daily_publish' ORDER BY run_id,task_id")]
    schedule = dict(con.execute("SELECT dag_id,is_paused,next_dagrun,next_dagrun_create_after FROM dag WHERE dag_id='haha_daily_publish'").fetchone())
publications = [json.loads(p.read_text()) for p in (ROOT / "output/step07_runs").glob("*.json")]
report = {"captured_at": datetime.now(timezone.utc).isoformat(), "runs": runs, "tasks": tasks,
          "scheduler": schedule, "publications": publications}
(ROOT / "airflow/step07_verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"runs": runs, "tasks": tasks, "scheduler": schedule}, indent=2))
