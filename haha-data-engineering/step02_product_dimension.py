"""第二课：读取第一课的 Parquet，关联商家和非遗项目，检查并保存商品维度。"""

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, functions as F
from pyspark.sql.types import StringType, StructField, StructType

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "feiyi-heritage-ai-publish/data/demo"
DEFAULT_PRODUCTS = ROOT / "output/20260906_203925_876380/dim_product"


def start_spark() -> SparkSession:
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    if os.name == "nt":
        native = ROOT / "tools/hadoop-3.3.5"
        os.environ["HADOOP_HOME"] = str(native)
        os.environ["PATH"] = str(native / "bin") + os.pathsep + os.environ["PATH"]
    spark = (
        SparkSession.builder.appName("HAHA-Step02-Product-Dimension")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.ansi.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def read_reference(spark: SparkSession, path: Path) -> DataFrame:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        columns = next(csv.reader(stream))
    return (
        spark.read.schema(StructType([StructField(c, StringType()) for c in columns]))
        .options(header=True, enforceSchema=False, multiLine=True,
                 encoding="UTF-8", quote='"', escape='"', mode="FAILFAST")
        .csv(path.resolve().as_uri())
    )


def check_key(frame: DataFrame, key: str, label: str) -> int:
    """关联前先检查唯一键，防止一对多连接意外放大商品行数。"""
    count = frame.count()
    if not count:
        raise ValueError(f"{label}为空")
    if frame.filter(F.col(key).isNull() | (F.trim(F.col(key)) == "")).limit(1).count():
        raise ValueError(f"{label}存在空主键：{key}")
    if frame.select(key).distinct().count() != count:
        raise ValueError(f"{label}存在重复主键：{key}")
    return count


def join_dimension(products: DataFrame, merchants: DataFrame, heritage: DataFrame) -> DataFrame:
    """保持每行一件商品，缺失外键关联时停止，不静默丢商品。"""
    count = check_key(products, "product_id", "商品表")
    check_key(merchants, "merchant_id", "商家表")
    check_key(heritage, "heritage_id", "非遗表")
    for reference, key, label in (
        (merchants, "merchant_id", "商家"), (heritage, "heritage_id", "非遗项目")
    ):
        # left_anti 查找“左表中在右表找不到对应项”的记录。
        missing = products.join(reference.select(key), key, "left_anti").count()
        if missing:
            raise ValueError(f"{missing} 件商品找不到对应{label}，请修复源数据")

    # left 保留全部商品；两张右表的键已验证唯一。
    enriched = products.join(merchants, "merchant_id", "left").join(
        heritage, "heritage_id", "left"
    )
    if check_key(enriched, "product_id", "关联结果") != count:
        raise ValueError("关联前后的商品数不一致")
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="调度器指定的本次输出目录")
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS,
                        help="第一课成功输出的 dim_product 目录；固定输入，不自动挑选最新目录")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, required=True,
                        help="本次采集快照的日期，YYYY-MM-DD；不表示源数据历史生效日期")
    args = parser.parse_args()
    product_path = args.products.resolve()
    if not (product_path / "_SUCCESS").is_file():
        raise FileNotFoundError(f"找不到第一课成功输出：{product_path}")
    spark = start_spark()
    try:
        products = spark.read.parquet(product_path.as_uri())
        merchants = read_reference(spark, DATA / "merchants.csv").select(
            "merchant_id", "merchant_name_zh",
            F.col("city").alias("merchant_city"),
            F.col("province").alias("merchant_province"),
            F.col("status").alias("merchant_status"),
            F.col("data_version").alias("merchant_data_version"),
            F.col("is_demo").cast("boolean").alias("merchant_is_demo"),
        )
        heritage = read_reference(spark, DATA / "heritage_items.csv").select(
            "heritage_id", "heritage_name_zh",
            F.col("region").alias("heritage_region"),
            F.col("category_code").alias("heritage_category_code"),
            F.col("official_level").alias("heritage_official_level"),
            F.col("verification_note").alias("heritage_verification_note"),
            F.col("status").alias("heritage_status"),
            F.col("data_version").alias("heritage_data_version"),
            F.col("is_demo").cast("boolean").alias("heritage_is_demo"),
        )
        enriched = join_dimension(products, merchants, heritage).withColumn(
            "snapshot_date", F.lit(args.snapshot_date).cast("date")
        )
        # 必需的描述信息与演示标记也必须完整。
        for field in ("merchant_name_zh", "heritage_name_zh", "merchant_is_demo", "heritage_is_demo"):
            if enriched.filter(F.col(field).isNull() | (F.trim(F.col(field).cast("string")) == "")).limit(1).count():
                raise ValueError(f"关联结果存在空字段：{field}")

        # 每次运行单独保存，暂不实现调度或覆盖历史分区。
        run_dir = args.output_dir.resolve() if args.output_dir else ROOT / "output" / ("step02_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        output = run_dir / "dim_product_snapshot"
        enriched.write.mode("errorifexists").parquet(output.as_uri())
        restored = spark.read.parquet(output.as_uri()).select(*enriched.columns)
        same_types = restored.dtypes == enriched.dtypes
        same_values = (not enriched.exceptAll(restored).limit(1).count()
                       and not restored.exceptAll(enriched).limit(1).count())
        # 所有原始商品字段必须保持不变。
        original = restored.select(*products.columns)
        original_preserved = (not products.exceptAll(original).limit(1).count()
                              and not original.exceptAll(products).limit(1).count())
        if not (same_types and same_values and original_preserved):
            raise ValueError("回读检查失败：类型、内容或原有商品字段不一致")

        report = {
            "snapshot_date": args.snapshot_date.isoformat(), "spark_version": spark.version,
            "product_input": str(product_path), "product_input_rows": products.count(),
            "merchant_input_rows": merchants.count(), "heritage_input_rows": heritage.count(),
            "output_rows": restored.count(),
            "unique_product_ids": restored.select("product_id").distinct().count(),
            "unmatched_merchants": 0, "unmatched_heritage_items": 0,
            "roundtrip_types_equal": same_types, "roundtrip_values_equal": same_values,
            "original_product_values_preserved": original_preserved,
            "reference_sources": [
                {"path": str(DATA / name), "sha256": hashlib.sha256((DATA / name).read_bytes()).hexdigest()}
                for name in ("merchants.csv", "heritage_items.csv")
            ],
            "data_notice": "MVP 演示数据 / MVP demo data；保留源资料核验状态",
            "output": str(output),
        }
        (run_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        restored.select("product_id", "product_name_zh", "merchant_name_zh", "heritage_name_zh").orderBy("product_id").show(5, truncate=False)
        restored.groupBy("merchant_name_zh").count().orderBy("merchant_name_zh").show(truncate=False)
        print("第二步完成！")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
