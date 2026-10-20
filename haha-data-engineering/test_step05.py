"""小样本手算核对指标，防止分母、跨天或未成熟窗口错误。"""
import unittest
from pyspark.sql import functions as F
from step02_product_dimension import start_spark
from step05_daily_metrics import aggregate, parse_as_of, prepare


class DailyMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = start_spark()
        cls.items = cls.spark.sql("""SELECT *, 'synthetic_demo' data_source,
            timestamp'2026-08-08 23:59:00' recommendation_timestamp,
            timestamp'2026-08-08 23:59:30' ingested_at
            FROM VALUES ('r1','s1','p1',1), ('r1','s1','p2',2), ('r2','s2','p1',1)
            AS t(recommendation_event_id, anonymous_session_id, product_id, ranking_position)""")
        cls.choices = cls.spark.sql("""SELECT 'synthetic_demo' data_source, 'r1' recommendation_event_id,
            's1' anonymous_session_id, 'p1' product_id, 1 ranking_position,
            true whether_customization_brief_generated,
            timestamp'2026-08-09 00:02:00' event_time, timestamp'2026-08-11 00:02:30' ingested_at""")
        cls.dim = cls.spark.sql("SELECT * FROM VALUES ('p1'),('p2') AS t(product_id)")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def base(self, cutoff="2026-08-12T02:00:00Z", dimension=None):
        return prepare(self.items, self.choices, self.dim if dimension is None else dimension, parse_as_of(cutoff))

    def test_denominators_and_cross_day_attribution(self):
        row = aggregate(self.base(), []).first()
        self.assertEqual(str(row.metric_date), "2026-08-08")
        self.assertEqual((row.recommendation_item_count, row.recommendation_count, row.selection_count), (3, 2, 1))
        self.assertEqual(str(row.selection_rate), "0.333333")
        self.assertEqual(str(row.recommendation_conversion_rate), "0.500000")

    def test_unselected_product_kept_with_zero(self):
        row = aggregate(self.base(), ["product_id"]).filter("product_id = 'p2'").first()
        self.assertEqual(row.selection_count, 0)
        self.assertEqual(row.recommendation_item_count, 1)
        self.assertEqual(str(row.selection_rate), "0.000000")

    def test_late_selection_excluded_and_rate_suppressed(self):
        row = aggregate(self.base("2026-08-09T02:00:00Z"), []).first()
        self.assertEqual(row.selection_count, 0)
        self.assertFalse(row.is_window_complete)
        self.assertIsNone(row.selection_rate)
        self.assertIsNone(row.recommendation_conversion_rate)

    def test_exact_maturity_boundary(self):
        row = aggregate(self.base("2026-08-12T00:59:00Z"), []).first()
        self.assertTrue(row.is_window_complete)
        self.assertEqual(row.selection_count, 1)

    def test_duplicate_dimension_rejected(self):
        with self.assertRaisesRegex(ValueError, "商品维度键重复"):
            self.base(dimension=self.dim.union(self.dim))

    def test_unmatched_selection_rejected(self):
        with self.assertRaisesRegex(ValueError, "无法匹配推荐"):
            prepare(self.items, self.choices.withColumn("product_id", F.lit("unknown")), self.dim, parse_as_of("2026-08-12T02:00:00Z"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
