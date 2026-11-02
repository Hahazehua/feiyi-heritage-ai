"""第四课：Spark 清洗模拟事件，去重并展开推荐，写入行为明细 Parquet。"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

from pyspark.sql import functions as F

from step02_product_dimension import ROOT, start_spark

DEFAULT_INPUT = ROOT / "output/step03_20260907_202430_910057"
COMMON = "schema_version STRING, data_source STRING, event_type STRING, event_id STRING, anonymous_session_id STRING, event_time TIMESTAMP, ingested_at TIMESTAMP"
SCHEMAS = {
    "session": COMMON + ", session_started_at TIMESTAMP, scene STRING, budget_per_item_fen BIGINT, entry_source STRING, app_version STRING",
    "recommendation": COMMON + ", recommendation_event_id STRING, recommendation_timestamp TIMESTAMP, recommended_product_ids ARRAY<STRING>, ranking_positions ARRAY<INT>, match_scores ARRAY<DOUBLE>",
    "selection": COMMON + ", selection_event_id STRING, recommendation_event_id STRING, selected_product_id STRING, selected_rank_position INT, selected_at TIMESTAMP, whether_customization_brief_generated BOOLEAN, final_action STRING",
}


def require_none(frame, condition, message):
    if frame.filter(condition).limit(1).count():
        raise ValueError(message)


def deduplicate(frame):
    # 同一 ID 的已解析 v1 字段必须完全相同，不能随意选一条覆盖冲突。
    payload = F.to_json(F.struct(*[F.col(c) for c in frame.columns]))
    conflicting = frame.groupBy("event_id").agg(F.countDistinct(payload).alias("versions"))
    require_none(conflicting, F.col("versions") > 1, "事件 ID 内容冲突")
    return frame.dropDuplicates(["event_id"])


def expand_recommendations(frame):
    require_none(frame, F.expr("""
        recommended_product_ids IS NULL OR ranking_positions IS NULL OR match_scores IS NULL
        OR size(recommended_product_ids) <> 3 OR size(ranking_positions) <> 3 OR size(match_scores) <> 3
        OR size(array_distinct(recommended_product_ids)) <> 3
        OR exists(recommended_product_ids, x -> x IS NULL OR trim(x) = '')
        OR ranking_positions <> array(1, 2, 3)
        OR exists(ranking_positions, x -> x IS NULL)
        OR exists(match_scores, x -> x IS NULL OR isnan(x) OR x < 0 OR x > 100)
    """), "推荐数组、排名或分数不符合 v1 三商品规则")
    # 三个数组先一一配对，然后展开；不能分别 explode，避免产生笛卡尔积。
    return frame.withColumn("item", F.explode(F.arrays_zip(
        "recommended_product_ids", "ranking_positions", "match_scores"
    ))).drop("recommended_product_ids", "ranking_positions", "match_scores").select(
        "*", F.col("item.recommended_product_ids").alias("product_id"),
        F.col("item.ranking_positions").alias("ranking_position"),
        F.col("item.match_scores").alias("match_score"),
    ).drop("item")


def link_selections(selections, items):
    keys = ["recommendation_event_id", "anonymous_session_id", "data_source", "product_id", "ranking_position"]
    choices = selections.withColumnRenamed("selected_product_id", "product_id").withColumnRenamed(
        "selected_rank_position", "ranking_position"
    )
    reference = items.select(*keys, "recommendation_timestamp")
    if choices.join(reference, keys, "left_anti").limit(1).count():
        raise ValueError("选择找不到匹配的推荐、会话、商品或排名")
    linked = choices.join(reference, keys, "left")
    require_none(linked, F.expr("event_time < recommendation_timestamp OR event_time >= recommendation_timestamp + INTERVAL 24 HOURS"),
                 "选择超出推荐后 24 小时窗口")
    return linked.withColumn("recommendation_date", F.to_date("recommendation_timestamp"))


def build_tables(frames):
    sessions, recs, selections = (frames[k] for k in SCHEMAS)
    for frame, key, name in ((sessions, "anonymous_session_id", "会话"),
                             (recs, "anonymous_session_id", "每会话推荐"),
                             (selections, "recommendation_event_id", "每推荐选择")):
        require_none(frame.groupBy(key).count(), F.col("count") > 1, name + "不符合 v1 唯一性规则")
    require_none(sessions, F.expr("session_started_at <> event_time OR budget_per_item_fen <= 0"), "会话时间或预算错误")
    require_none(recs, F.expr("recommendation_event_id <> event_id OR recommendation_timestamp <> event_time"), "推荐 ID 或时间错误")
    require_none(selections, F.expr("selection_event_id <> event_id OR selected_at <> event_time OR final_action <> CASE WHEN whether_customization_brief_generated THEN 'customization_brief_generated' ELSE 'selected' END"), "选择 ID、时间或动作错误")
    session_ref = sessions.select("anonymous_session_id", "data_source", "session_started_at", "scene", "budget_per_item_fen")
    keys = ["anonymous_session_id", "data_source"]
    if recs.join(session_ref, keys, "left_anti").limit(1).count() or sessions.join(recs, keys, "left_anti").limit(1).count():
        raise ValueError("会话和推荐未完整对应")
    recs = recs.join(session_ref, keys, "left")
    require_none(recs, F.col("event_time") < F.col("session_started_at"), "推荐早于会话")
    items = expand_recommendations(recs)
    linked = link_selections(selections, items)
    return {name: frame.withColumn("event_date", F.to_date("event_time")).withColumn("ingest_date", F.to_date("ingested_at"))
            for name, frame in (("dwd_session", sessions), ("dwd_recommendation_item", items), ("dwd_selection", linked))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="调度器指定的本次输出目录")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    source = args.input.resolve()
    if not (source / "_SUCCESS").is_file():
        raise ValueError("需要第三步验证通过的批次")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # 确认本次读取的文件与第三步验证时相同，拒绝额外文件或内容修改。
    declared = {f["path"]: f["sha256"] for f in manifest["files"]}
    actual = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in source.glob("*/ingest_date=*/*.jsonl")}
    if declared != actual or not manifest["validation_passed"]:
        raise ValueError("原始日志与第三步清单不一致")
    spark = start_spark()
    spark.sparkContext.setJobDescription("HAHA Step 04: deduplicate and expand events")
    cached = []
    try:
        frames, raw_counts, unique_counts = {}, {}, {}
        for kind, schema in SCHEMAS.items():
            frame = (spark.read.schema(schema).option("mode", "FAILFAST").option("recursiveFileLookup", "true")
                     .json((source / kind).as_uri())) if (source / kind).exists() else spark.createDataFrame([], schema)
            frame = frame.cache()
            cached.append(frame)
            raw_counts[kind] = frame.count()
            if raw_counts[kind] != manifest["raw_rows"].get(kind, 0):
                raise ValueError("原始数量与第三步清单不一致")
            for column in frame.columns:
                require_none(frame, F.col(column).isNull(), f"{kind} 必填字段为空：{column}")
            require_none(frame, F.expr("trim(event_id) = '' OR trim(anonymous_session_id) = '' OR data_source <> 'synthetic_demo' OR schema_version <> '1' OR ingested_at < event_time") | (F.col("event_type") != kind), "公共事件字段不合法")
            frames[kind] = deduplicate(frame).cache()
            cached.append(frames[kind])
            unique_counts[kind] = frames[kind].count()
        tables = build_tables(frames)
        # 推荐商品必须属于第三步所记录的演示商品集合。
        require_none(tables["dwd_recommendation_item"], ~F.col("product_id").isin(manifest["product_ids"]), "推荐商品不在输入目录集合")
        expected = {"dwd_session": unique_counts["session"], "dwd_recommendation_item": unique_counts["recommendation"] * 3,
                    "dwd_selection": unique_counts["selection"]}
        run_dir = args.output_dir.resolve() if args.output_dir else ROOT / "output" / ("step04_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        results = {}
        for name, frame in tables.items():
            frame = frame.cache()
            cached.append(frame)
            count = frame.count()
            if count != expected[name]:
                raise ValueError("关联或展开后数量错误：" + name)
            path = run_dir / name
            frame.write.mode("errorifexists").partitionBy("event_date").parquet(path.as_uri())
            # 指定完整 Schema：日期分区类型不依赖自动推断；同时支持零选择事件。
            restored = spark.read.schema(frame.schema).parquet(path.as_uri()).select(*frame.columns)
            equal = restored.dtypes == frame.dtypes and not frame.exceptAll(restored).limit(1).count() and not restored.exceptAll(frame).limit(1).count()
            if not equal:
                raise ValueError("Parquet 回读不一致：" + name)
            results[name] = dict(rows=count, event_date_partitions=frame.select("event_date").distinct().count(), roundtrip_equal=bool(equal), output=str(path))
        report = dict(input=str(source), input_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                      spark_version=spark.version, data_source="synthetic_demo", raw_counts=raw_counts, unique_counts=unique_counts,
                      removed_duplicates={k: raw_counts[k] - unique_counts[k] for k in SCHEMAS}, tables=results,
                      selections_without_match=0,
                      cross_day_selections=tables["dwd_selection"].filter("event_date <> recommendation_date").count(),
                      sessions_without_selection=frames["session"].join(frames["selection"], "anonymous_session_id", "left_anti").count(),
                      validation_passed=True)
        (run_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "_SUCCESS").write_text("all three tables validated\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"第四步完成：{run_dir}")
    finally:
        for frame in cached:
            frame.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
