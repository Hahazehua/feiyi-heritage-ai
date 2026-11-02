"""Publication invariants, including retry/rerun and failure isolation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from step07_daily_publish import publish, digest, atomic_json, STORE


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        caches = [json.loads(p.read_text()) for p in (STORE / "cache").glob("*.json")]
        self.snapshot = max(caches, key=lambda x: x["identity"]["as_of"])
        self.cache = self.root / "cache.json"
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        self.snapshot["tables_sha256"] = digest(self.snapshot["tables"])
        atomic_json(self.cache, self.snapshot)

    def test_rerun_is_idempotent(self):
        first = publish(self.cache, "2026-08-08", store=self.root)
        second = publish(self.cache, "2026-08-08", store=self.root)
        self.assertEqual(first["catalog_sha256"], second["catalog_sha256"])
        self.assertEqual(second["changed"], [])
        self.assertEqual(len(list((self.root / "versions").glob("*.json"))), 1)

    def test_quality_failure_leaves_catalog_unchanged(self):
        publish(self.cache, "2026-08-08", store=self.root)
        before = (self.root / "catalog.json").read_bytes()
        row = next(r for r in self.snapshot["tables"]["dws_product_daily"] if r["metric_date"] == "2026-08-08")
        row["selection_count"] = 999999
        self.save()
        with self.assertRaises(ValueError):
            publish(self.cache, "2026-08-08", store=self.root)
        self.assertEqual(before, (self.root / "catalog.json").read_bytes())

    def test_older_cutoff_cannot_roll_back(self):
        publish(self.cache, "2026-08-08", store=self.root)
        self.snapshot["identity"]["as_of"] = "2026-08-09T00:00:00+00:00"
        self.save()
        result = publish(self.cache, "2026-08-08", store=self.root)
        self.assertEqual(result["stale_skipped"], ["2026-08-08"])

    def test_tampered_cache_rejected(self):
        self.snapshot["tables_sha256"] = "wrong"
        atomic_json(self.cache, self.snapshot)
        with self.assertRaises(ValueError):
            publish(self.cache, "2026-08-08", store=self.root)

    def test_fill_missing_historical_day(self):
        publish(self.cache, "2026-08-08", store=self.root)
        publish(self.cache, "2026-08-10", store=self.root)
        before = json.loads((self.root / "catalog.json").read_text())["days"]
        self.assertNotIn("2026-08-09", before)
        result = publish(self.cache, "2026-08-09", store=self.root)
        after = json.loads((self.root / "catalog.json").read_text())["days"]
        self.assertEqual(result["changed"], ["2026-08-09"])
        self.assertEqual(len(after), 3)
        self.assertEqual(before["2026-08-08"], after["2026-08-08"])

    def test_unclosed_window_hides_rate(self):
        early = min((json.loads(p.read_text()) for p in (STORE / "cache").glob("*.json")), key=lambda x: x["identity"]["as_of"])
        rows = early["tables"]["ads_daily_overview"]
        incomplete = [r for r in rows if not r["is_window_complete"]]
        self.assertTrue(incomplete)
        for row in incomplete:
            self.assertIsNone(row.get("selection_rate"))
            self.assertIsNone(row.get("recommendation_conversion_rate"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
