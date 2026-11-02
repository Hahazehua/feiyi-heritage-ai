"""Airflow 3.1.0 CLI compatibility: pass decoded conf to its native backfill function.

The installed CLI passes a JSON string unchanged, causing ParamsDict.update to fail.
Version-pinned adapter only; resulting runs are native backfill runs in Airflow DB.
"""
import pendulum
from airflow.models.backfill import _create_backfill, ReprocessBehavior

if __name__ == "__main__":
    result = _create_backfill(dag_id="haha_daily_publish",
        from_date=pendulum.datetime(2026, 8, 8, tz="UTC"), to_date=pendulum.datetime(2026, 8, 10, tz="UTC"),
        max_active_runs=1, reverse=False,
        dag_run_conf={"as_of": "2026-09-11T00:00:00Z", "refresh_days": 1},
        triggering_user_name="harrychen901", reprocess_behavior=ReprocessBehavior.NONE)
    print("Native backfill created:", result)
