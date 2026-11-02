"""验证关联不会因重复键扩大行数，也不会静默丢失找不到维度的商品。"""

import unittest

from step02_product_dimension import join_dimension, start_spark


class DimensionJoinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = start_spark()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def setUp(self):
        self.products = self.spark.sql(
            "SELECT 'p1' product_id, 'm1' merchant_id, 'h1' heritage_id, 98000 price_min_fen"
        )
        self.merchants = self.spark.sql("SELECT 'm1' merchant_id, 'Merchant' merchant_name_zh")
        self.heritage = self.spark.sql("SELECT 'h1' heritage_id, 'Craft' heritage_name_zh")

    def test_valid_join_preserves_product_and_adds_names(self):
        row = join_dimension(self.products, self.merchants, self.heritage).collect()
        self.assertEqual(len(row), 1)
        self.assertEqual(row[0].price_min_fen, 98000)
        self.assertEqual(row[0].merchant_name_zh, "Merchant")
        self.assertEqual(row[0].heritage_name_zh, "Craft")

    def test_duplicate_merchant_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "重复主键"):
            join_dimension(self.products, self.merchants.union(self.merchants), self.heritage)

    def test_missing_merchant_is_rejected(self):
        merchant = self.spark.sql("SELECT 'other' merchant_id, 'Other' merchant_name_zh")
        with self.assertRaisesRegex(ValueError, "找不到对应商家"):
            join_dimension(self.products, merchant, self.heritage)

    def test_missing_heritage_is_rejected(self):
        heritage = self.spark.sql("SELECT 'other' heritage_id, 'Other' heritage_name_zh")
        with self.assertRaisesRegex(ValueError, "找不到对应非遗项目"):
            join_dimension(self.products, self.merchants, heritage)


if __name__ == "__main__":
    unittest.main(verbosity=2)
