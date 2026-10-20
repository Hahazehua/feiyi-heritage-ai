"""Reproducible local Spark join/pruning experiments; synthetic scale data."""
import json
import platform
import statistics
import tempfile
import time
from pathlib import Path
from pyspark.sql import functions as F
from step02_product_dimension import ROOT, start_spark


def main():
    out = ROOT / "output/benchmark"
    out.mkdir(parents=True, exist_ok=True)
    spark = start_spark()
    spark.conf.set("spark.sql.adaptive.enabled", "false")
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
    records = []
    try:
        with tempfile.TemporaryDirectory(prefix="haha_benchmark_") as temporary:
            for n in (100000, 1000000):
                fact = spark.range(n).selectExpr("id", "id % 1000 as product_id", "cast(id % 30 as int) as event_day", "id % 97 as value")
                dim = spark.range(1000).selectExpr("id as product_id", "id % 7 as weight")
                path = str(Path(temporary) / str(n))
                fact.write.partitionBy("event_day").parquet(path)
                disk = spark.read.parquet(path)
                queries = {
                    "broadcast_join": lambda: fact.join(F.broadcast(dim), "product_id").agg(F.sum(F.col("value") * F.col("weight")).alias("checksum")),
                    "sort_merge_join": lambda: fact.hint("merge").join(dim.hint("merge"), "product_id").agg(F.sum(F.col("value") * F.col("weight")).alias("checksum")),
                    "partition_pruned": lambda: disk.filter("event_day = 7").agg(F.sum("value").alias("checksum")),
                    "full_scan_conditional": lambda: disk.agg(F.sum(F.when(F.col("event_day") == 7, F.col("value"))).alias("checksum")),
                }
                timings = {name: [] for name in queries}
                checksums = {}
                jobs = {name: [] for name in queries}
                for name, factory in queries.items():
                    query = factory()
                    query.collect()  # one warm-up per query; filesystem caches remain warm
                    (out / f"plan_{n}_{name}.txt").write_text(query._jdf.queryExecution().toString(), encoding="utf-8")
                for repeat in range(3):
                    names = list(queries) if repeat % 2 == 0 else list(reversed(queries))
                    for name in names:
                        query = queries[name]()  # fresh plan prevents reuse of a completed shuffle stage
                        group = f"{n}_{name}_{repeat}"
                        spark.sparkContext.setJobGroup(group, group)
                        start = time.perf_counter()
                        rows = query.collect()
                        timings[name].append(time.perf_counter() - start)
                        job_ids = list(spark.sparkContext.statusTracker().getJobIdsForGroup(group))
                        assert job_ids, "No Spark job was executed"
                        jobs[name].append(job_ids)
                        checksums[name] = rows[0]["checksum"]
                assert checksums["broadcast_join"] == checksums["sort_merge_join"]
                assert checksums["partition_pruned"] == checksums["full_scan_conditional"]
                for name in queries:
                    records.append({"rows": n, "query": name, "seconds": timings[name],
                                    "median_seconds": statistics.median(timings[name]), "checksum": checksums[name], "spark_job_ids": jobs[name]})
                print(json.dumps(records[-4:]), flush=True)
        report = {"spark": spark.version, "python": platform.python_version(), "platform": platform.platform(),
                  "master": spark.sparkContext.master, "shuffle_partitions": 2, "AQE": False,
                  "dimension_rows": 1000, "partition_count": 30, "timing": "fresh query plan per collect, one warm-up then three alternating runs, warm OS caches; not cold disk latency",
                  "data": "generated synthetic numeric rows; not production traffic", "results": records}
        (out / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
