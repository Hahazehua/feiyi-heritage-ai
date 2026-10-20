"""手动触发一次后，由 Airflow 自动依次执行五步 Spark 作业并验收。"""
from datetime import timedelta
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

import pendulum
from airflow.sdk import dag, task, get_current_context, Param

PROJECT = Path(os.environ.get("HAHA_PROJECT", "/mnt/f/HC/hackathon/haha-data-engineering"))


def run_step(number, filename, arguments):
    context = get_current_context()
    run_key = hashlib.sha256(context["run_id"].encode()).hexdigest()[:20]
    output = PROJECT / "output/airflow" / run_key / f"step{number:02d}_try{context['ti'].try_number}"
    # 提交真正的 Spark 作业；参数数组避免 shell 字符串拼接，错误码直接令任务失败。
    command = [str(Path(sys.executable).parent / "spark-submit"), "--master", "local[2]",
               str(PROJECT / filename), "--output-dir", str(output), *arguments]
    subprocess.run(command, check=True, timeout=1200)
    report_path = output / ("manifest.json" if number == 3 else "validation.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if number <= 2:
        if not report["roundtrip_values_equal"] or not report["roundtrip_types_equal"]:
            raise ValueError("商品回读验证失败")
    elif not report["validation_passed"]:
        raise ValueError("下游数据验证失败")
    return str(output)  # XCom 仅传路径；数据保存在文件中。


@dag(dag_id="haha_learning_pipeline", schedule=None,
     start_date=pendulum.datetime(2026, 9, 7, tz="UTC"), catchup=False, max_active_runs=1,
     default_args={"retries": 1, "retry_delay": timedelta(seconds=20), "execution_timeout": timedelta(minutes=25)},
     params={"sessions": Param(10000, type="integer", minimum=100, maximum=10000)},
     tags=["HAHA", "learning", "synthetic"])
def pipeline():
    @task
    def products():
        return run_step(1, "step01_products.py", [])

    @task
    def dimension(product_output):
        return run_step(2, "step02_product_dimension.py", ["--products", str(Path(product_output) / "dim_product"), "--snapshot-date", "2026-09-07"])

    @task
    def events(dimension_output):
        count = get_current_context()["params"]["sessions"]
        return run_step(3, "step03_generate_events.py", ["--dimension", str(Path(dimension_output) / "dim_product_snapshot"), "--sessions", str(count)])

    @task
    def details(event_output):
        return run_step(4, "step04_event_details.py", ["--input", event_output])

    @task
    def metrics(detail_output, dimension_output):
        return run_step(5, "step05_daily_metrics.py", ["--input", detail_output, "--dimension", str(Path(dimension_output) / "dim_product_snapshot"), "--as-of", "2026-09-11T00:00:00Z"])

    @task(retries=0)
    def verify_run(product_output, dimension_output, event_output, detail_output, metric_output):
        stages = [product_output, dimension_output, event_output, detail_output, metric_output]
        reports = [json.loads((Path(path) / ("manifest.json" if i == 2 else "validation.json")).read_text(encoding="utf-8")) for i, path in enumerate(stages)]
        first, dim, event, detail, metric = reports
        assert first["output_rows"] == dim["output_rows"]
        assert event["sessions"] == get_current_context()["params"]["sessions"]
        assert detail["tables"]["dwd_recommendation_item"]["rows"] == event["recommendations"] * 3
        assert metric["observed_selections"] == event["selections"]
        assert metric["observed_recommendation_items"] == event["recommendations"] * 3
        record = dict(run_id=get_current_context()["run_id"], stage_outputs=stages, all_checks_passed=True,
                      products=dim["output_rows"], sessions=event["sessions"], selections=event["selections"],
                      recommendation_items=metric["observed_recommendation_items"], metrics=metric["tables"])
        target = Path(metric_output).parent / "pipeline_validation.json"
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)

    p = products()
    d = dimension(p)
    e = events(d)
    f = details(e)
    m = metrics(f, d)
    verify_run(p, d, e, f, m)


pipeline()
