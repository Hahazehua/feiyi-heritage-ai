"""第五课：按推荐日期汇总商品、场景预算和每日概览，区分商品选择率与推荐转化率。"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from pyspark.sql import functions as F
from step02_product_dimension import ROOT, start_spark
from step04_event_details import require_none

DEFAULT_INPUT = ROOT / "output/step04_20260907_203332_934029"
DEFAULT_DIM = ROOT / "output/step02_20260907_201837_082177/dim_product_snapshot"
KEYS = ["data_source", "recommendation_event_id", "anonymous_session_id", "product_id", "ranking_position"]


def parse_as_of(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise argparse.ArgumentTypeError("as-of 必须包含时区，例如 2026-09-11T00:00:00Z")
    return result.astimezone(timezone.utc)


def unique(frame, keys, label):
    require_none(frame.groupBy(*keys).count(), F.col("count") > 1, label + "键重复")
    for key in keys:
        require_none(frame, F.col(key).isNull(), label + "键为空")


def prepare(items, selections, dimension, as_of, late_hours=49):
    if late_hours < 0:
        raise ValueError("晚到容忍小时数不得小于零")
    unique(items, KEYS, "推荐明细")
    unique(selections, KEYS, "选择明细")
    unique(dimension, ["product_id"], "商品维度")
    if selections.join(items.select(*KEYS), KEYS, "left_anti").limit(1).count():
        raise ValueError("存在无法匹配推荐的选择")
    if items.join(dimension.select("product_id"), "product_id", "left_anti").limit(1).count():
        raise ValueError("存在无法匹配维度的商品")
    observed_items = items.filter(F.col("ingested_at") <= F.lit(as_of))
    observed_choices = selections.filter(F.col("ingested_at") <= F.lit(as_of)).select(
        *KEYS, F.lit(1).alias("selected_count"),
        F.col("whether_customization_brief_generated").cast("int").alias("brief_count")
    )
    # LEFT JOIN 保留没有选择的推荐商品，确保分母不会被筛掉。
    base = observed_items.join(observed_choices, KEYS, "left").fillna({"selected_count": 0, "brief_count": 0})
    return base.withColumn("metric_date", F.to_date("recommendation_timestamp")).withColumn(
        "window_complete", (F.col("recommendation_timestamp") + F.expr(f"INTERVAL {24 + late_hours} HOURS") <= F.lit(as_of)).cast("int")
    )


def aggregate(base, dimensions):
    result = base.groupBy("metric_date", "data_source", *dimensions).agg(
        F.count("*").alias("recommendation_item_count"),
        F.countDistinct("recommendation_event_id").alias("recommendation_count"),
        F.sum("selected_count").alias("selection_count"),
        F.sum("brief_count").alias("customization_brief_count"),
        F.min("window_complete").cast("boolean").alias("is_window_complete"),
    )
    # 不足完整观察窗口时，计数显示已观察值，比例留空而不是误显示为零。
    result = result.withColumn("selection_rate", F.when(F.col("is_window_complete"),
        (F.col("selection_count") / F.col("recommendation_item_count")).cast("decimal(12,6)")))
    return result.withColumn("recommendation_conversion_rate", F.when(F.col("is_window_complete"),
        (F.col("selection_count") / F.col("recommendation_count")).cast("decimal(12,6)")))


def build_metrics(items, selections, dimension, as_of, late_hours=49):
    base = prepare(items, selections, dimension, as_of, late_hours).cache()
    product = aggregate(base, ["product_id"]).join(dimension.select(
        "product_id", "product_name_zh", "category_code", "merchant_name_zh", "catalog_role", "is_demo"
    ), "product_id", "left")
    # 单商品的推荐次数等于推荐商品数，去掉重复口径的转化率列。
    product = product.drop("recommendation_conversion_rate")
    tables = {"dws_product_daily": product,
              "ads_scene_budget_daily": aggregate(base, ["scene", "budget_per_item_fen"]),
              "ads_daily_overview": aggregate(base, [])}
    return base, {name: frame.withColumn("as_of", F.lit(as_of)).withColumn("late_tolerance_hours", F.lit(late_hours))
                  for name, frame in tables.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="调度器指定的本次输出目录")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dimension", type=Path, default=DEFAULT_DIM)
    parser.add_argument("--as-of", type=parse_as_of, default=parse_as_of("2026-09-11T00:00:00Z"),
                        help="模拟观察截止时间，默认取全部模拟日志到齐之后；不是当前真实时间")
    parser.add_argument("--late-hours", type=int, default=49)
    args = parser.parse_args()
    if not (args.input / "_SUCCESS").is_file() or not (args.dimension / "_SUCCESS").is_file():
        raise ValueError("需要已验证的第四步批次和第二步维度")
    evidence = json.loads((args.input / "validation.json").read_text(encoding="utf-8"))
    if not evidence["validation_passed"]:
        raise ValueError("第四步验证未通过")
    spark = start_spark()
    cached = []
    try:
        items = spark.read.parquet((args.input.resolve() / "dwd_recommendation_item").as_uri())
        selections = spark.read.parquet((args.input.resolve() / "dwd_selection").as_uri())
        dimension = spark.read.parquet(args.dimension.resolve().as_uri())
        for name, frame in (("dwd_recommendation_item", items), ("dwd_selection", selections)):
            if frame.count() != evidence["tables"][name]["rows"]:
                raise ValueError("输入行数与第四步报告不一致")
        base, tables = build_metrics(items, selections, dimension, args.as_of, args.late_hours)
        cached.append(base)
        expected = base.agg(F.count("*").alias("items"), F.sum("selected_count").alias("selected"), F.sum("brief_count").alias("briefs")).first()
        run_dir = args.output_dir.resolve() if args.output_dir else ROOT / "output" / ("step05_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        outputs = {}
        for name, frame in tables.items():
            frame = frame.cache()
            cached.append(frame)
            require_none(frame, F.expr("selection_count > recommendation_item_count OR customization_brief_count > selection_count OR selection_rate < 0 OR selection_rate > 1"), "指标范围错误")
            sums = frame.agg(F.sum("recommendation_item_count"), F.sum("selection_count"), F.sum("customization_brief_count")).first()
            if tuple(v or 0 for v in sums) != tuple(v or 0 for v in expected):
                raise ValueError("汇总总数与明细不一致：" + name)
            output = run_dir / name
            frame.write.mode("errorifexists").partitionBy("metric_date").parquet(output.as_uri())
            restored = spark.read.schema(frame.schema).parquet(output.as_uri()).select(*frame.columns)
            if restored.dtypes != frame.dtypes or frame.exceptAll(restored).limit(1).count() or restored.exceptAll(frame).limit(1).count():
                raise ValueError("汇总回读不一致")
            outputs[name] = dict(rows=frame.count(), incomplete_groups=frame.filter("NOT is_window_complete").count(), totals_match=True, roundtrip_equal=True, output=str(output))
        overview = tables["ads_daily_overview"].agg(F.sum("recommendation_count"), F.sum("selection_count")).first()
        report = dict(input=str(args.input.resolve()), dimension=str(args.dimension.resolve()), data_source="synthetic_demo",
                      as_of=args.as_of.isoformat(), late_tolerance_hours=args.late_hours,
                      observed_recommendation_items=expected[0], observed_selections=expected[1] or 0,
                      observed_briefs=expected[2] or 0, observed_recommendations=overview[0] or 0,
                      tables=outputs, validation_passed=True,
                      note="模拟数据；按推荐日期归属；73小时为24小时选择窗口加49小时晚到容忍，不是生产完整性保证")
        (run_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "_SUCCESS").write_text("all metrics validated\n", encoding="utf-8")
        tables["ads_daily_overview"].orderBy("metric_date").show(3, truncate=False)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"第五步完成：{run_dir}")
    finally:
        for frame in cached:
            frame.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
