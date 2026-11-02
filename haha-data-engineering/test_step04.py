"""第四步关键边界：重复、数组对齐、选择关联和跨天归因。"""

import unittest
from pyspark.sql import functions as F
from step02_product_dimension import start_spark
from step04_event_details import deduplicate, expand_recommendations, link_selections


class EventDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = start_spark()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def recommendation(self):
        return self.spark.sql("""SELECT 'r1' event_id, 'r1' recommendation_event_id,
            's1' anonymous_session_id, 'synthetic_demo' data_source,
            timestamp'2026-08-08 23:59:00' recommendation_timestamp,
            array('p1','p2','p3') recommended_product_ids,
            array(1,2,3) ranking_positions, array(88D,78D,68D) match_scores""")

    def choice(self):
        return self.spark.sql("""SELECT 'r1' recommendation_event_id, 's1' anonymous_session_id,
            'synthetic_demo' data_source, 'p2' selected_product_id, 2 selected_rank_position,
            timestamp'2026-08-09 00:02:00' event_time""")

    def test_identical_duplicate_removed(self):
        rec = self.recommendation()
        self.assertEqual(deduplicate(rec.union(rec)).count(), 1)

    def test_conflicting_duplicate_rejected(self):
        rec = self.recommendation()
        other = rec.withColumn("match_scores", F.array(F.lit(1.), F.lit(2.), F.lit(3.)))
        with self.assertRaisesRegex(ValueError, "内容冲突"):
            deduplicate(rec.union(other))

    def test_arrays_expand_with_correct_pairing(self):
        result = expand_recommendations(self.recommendation()).orderBy("ranking_position").collect()
        self.assertEqual([(r.product_id, r.ranking_position, r.match_score) for r in result],
                         [("p1", 1, 88.), ("p2", 2, 78.), ("p3", 3, 68.)])

    def test_unequal_arrays_rejected(self):
        rec = self.recommendation().withColumn("match_scores", F.array(F.lit(88.)))
        with self.assertRaisesRegex(ValueError, "推荐数组"):
            expand_recommendations(rec)

    def test_wrong_rank_rejected(self):
        choice = self.choice().withColumn("selected_rank_position", F.lit(1))
        with self.assertRaisesRegex(ValueError, "找不到匹配"):
            link_selections(choice, expand_recommendations(self.recommendation()))

    def test_cross_day_selection_keeps_recommendation_date(self):
        result = link_selections(self.choice(), expand_recommendations(self.recommendation())).collect()
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result[0].recommendation_date), "2026-08-08")

    def test_outside_attribution_window_rejected(self):
        choice = self.choice().withColumn("event_time", F.expr("timestamp'2026-08-09 23:59:00'"))
        with self.assertRaisesRegex(ValueError, "24 小时"):
            link_selections(choice, expand_recommendations(self.recommendation()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
