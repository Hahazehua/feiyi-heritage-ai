"""Daily refresh of fixed synthetic inputs; explicit cutoffs support historical replay."""
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import pendulum
from airflow.sdk import dag, task, get_current_context, Param
from airflow.timetables.interval import CronDataIntervalTimetable

PROJECT = Path(os.environ.get("HAHA_PROJECT", "/mnt/f/HC/hackathon/haha-data-engineering"))


@dag(dag_id="haha_daily_publish", schedule=CronDataIntervalTimetable("0 0 * * *", timezone="UTC"),
     start_date=pendulum.datetime(2026, 8, 8, tz="UTC"), catchup=False, max_active_runs=1,
     default_args={"retries": 1, "retry_delay": timedelta(seconds=15)},
     params={"business_date": Param("", type="string"), "as_of": Param("", type="string"),
             "refresh_days": Param(4, type="integer", minimum=1, maximum=60),
             "fail_once": Param(False, type="boolean")}, tags=["HAHA", "daily", "synthetic"])
def pipeline():
    @task(execution_timeout=timedelta(minutes=15))
    def compute_snapshot():
        ctx = get_current_context()
        cutoff = ctx.get("data_interval_end") or ctx["dag_run"].run_after
        as_of = ctx["params"]["as_of"] or cutoff.isoformat()
        result = subprocess.run([str(Path(sys.executable).parent / "spark-submit"),
                                 str(PROJECT / "step07_daily_publish.py"), "--as-of", as_of],
                                check=True, text=True, stdout=subprocess.PIPE, timeout=800)
        print(result.stdout)
        return result.stdout.split("CACHE_PATH=")[-1].strip()

    @task
    def recovery_gate(cache):
        ctx = get_current_context()
        if ctx["params"]["fail_once"] and ctx["ti"].try_number == 1:
            raise RuntimeError("Intentional first-attempt failure: retry recovery exercise")
        return cache

    @task
    def publish_metrics(cache):
        sys.path.insert(0, str(PROJECT))
        from step07_daily_publish import publish, atomic_json, digest
        ctx = get_current_context()
        interval_start = ctx.get("data_interval_start") or (ctx["dag_run"].run_after - timedelta(days=1))
        day = ctx["params"]["business_date"] or interval_start.date().isoformat()
        result = publish(cache, day, ctx["params"]["refresh_days"])
        result.update(run_id=ctx["run_id"], business_date=day, cache=cache)
        evidence = PROJECT / "output/step07_runs" / (digest(ctx["run_id"]) + ".json")
        atomic_json(evidence, result)
        return result

    publish_metrics(recovery_gate(compute_snapshot()))


pipeline()
