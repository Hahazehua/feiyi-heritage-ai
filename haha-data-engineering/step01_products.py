"""第一课：使用本机 Spark 把商品 CSV 转为经过检查的 Parquet。"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StringType, StructField, StructType


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "feiyi-heritage-ai-publish/data/demo/products.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="调度器指定的本次输出目录")
    args = parser.parse_args()
    # 使用本练习的 Python；配置只作用于当前进程，不修改系统环境变量。
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    if os.name == "nt":
        hadoop_home = ROOT / "tools" / "hadoop-3.3.5"
        if not all((hadoop_home / "bin" / name).is_file()
                   for name in ("winutils.exe", "hadoop.dll")):
            raise FileNotFoundError("缺少本练习所需的 Windows Hadoop 组件，请查看 README.md")
        os.environ["HADOOP_HOME"] = str(hadoop_home)
        os.environ["PATH"] = str(hadoop_home / "bin") + os.pathsep + os.environ["PATH"]
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        columns = next(reader)
        expected_rows = sum(1 for row in reader if row)

    # local[2] 表示在本机最多并行执行两个任务，不需要另建集群。
    spark = (
        SparkSession.builder.appName("HAHA-Step01-Products")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.ansi.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    try:
        # 先保留源字段为字符串，再显式转换需要的类型。
        # CSV 内的 JSON 标签使用双引号转义，所以 escape 也设成双引号。
        raw = (
            spark.read.schema(StructType([StructField(c, StringType()) for c in columns]))
            .option("header", "true")
            .option("enforceSchema", "false")
            .option("encoding", "UTF-8")
            .option("multiLine", "true")
            .option("quote", '"')
            .option("escape", '"')
            .option("mode", "FAILFAST")
            .csv(SOURCE.as_uri())
        )

        # 每行是一件商品；本课先制作商品维度的基础版本。
        products = raw.select(
            F.trim("product_id").alias("product_id"),
            "merchant_id", "heritage_id", "product_name_zh", "category_code",
            F.col("price_min_fen").cast("long"),
            F.col("price_max_fen").cast("long"),
            "catalog_role", "commercial_data_status", "data_version",
            F.col("is_demo").cast("boolean"),
        )
        # 只用定点小数展示元，源金额仍保留整数分。
        products = products.withColumn(
            "price_min_yuan",
            (F.col("price_min_fen").cast("decimal(18,2)") / F.lit(100))
            .cast("decimal(18,2)"),
        )

        row_count = products.count()
        invalid = products.filter(
            F.col("product_id").isNull() | (F.col("product_id") == "")
            | F.col("price_min_fen").isNull() | F.col("price_max_fen").isNull()
            | (F.col("price_min_fen") < 0)
            | (F.col("price_max_fen") < F.col("price_min_fen"))
            | F.col("is_demo").isNull()
        ).count()
        unique_ids = products.select("product_id").distinct().count()
        if row_count != expected_rows or invalid or unique_ids != row_count:
            raise ValueError(
                f"质量检查失败：源记录={expected_rows}, Spark记录={row_count}, "
                f"异常记录={invalid}, 唯一商品ID={unique_ids}"
            )

        print("\nMVP 演示数据 / MVP demo data")
        products.printSchema()
        products.orderBy("product_id").show(5, truncate=False)
        print("\n按商品用途统计：")
        products.groupBy("catalog_role").count().orderBy("catalog_role").show()

        # 每次运行写入一个新目录，便于保留练习结果。
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_dir = args.output_dir.resolve() if args.output_dir else ROOT / "output" / run_id
        output = run_dir / "dim_product"
        products.write.mode("errorifexists").parquet(output.as_uri())

        # 重新读取文件，验证行数、字段类型和全部字段值，而不只检查写入成功。
        restored = spark.read.parquet(output.as_uri()).select(*products.columns)
        same_types = restored.dtypes == products.dtypes
        same_values = (
            not products.exceptAll(restored).limit(1).count()
            and not restored.exceptAll(products).limit(1).count()
        )
        if not same_types or not same_values:
            raise ValueError("Parquet 回读检查失败：字段类型或内容不一致")

        report = {
            "source": str(SOURCE), "spark_version": spark.version,
            "source_rows": expected_rows, "output_rows": restored.count(),
            "unique_product_ids": unique_ids, "invalid_rows": invalid,
            "roundtrip_types_equal": same_types, "roundtrip_values_equal": same_values,
            "data_notice": "MVP 演示数据 / MVP demo data", "output": str(output),
        }
        (output.parent / "validation.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("\n第一步完成！")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
