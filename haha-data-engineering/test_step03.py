"""第三课的可复现性、关联检查和文件保护测试。"""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from step03_generate_events import generate_events, read_events, validate_events, write_events


class SyntheticEventsTests(unittest.TestCase):
    ids = ["p1", "p2", "p3", "p4"]

    def events(self, seed=42):
        return list(generate_events(self.ids, sessions=100, seed=seed))

    def test_same_seed_and_sorted_catalog_are_reproducible(self):
        self.assertEqual(self.events(), list(generate_events(list(reversed(self.ids)), sessions=100)))
        self.assertNotEqual(self.events(), self.events(seed=7))

    def test_unselected_duplicates_and_late_events_are_present(self):
        report = validate_events(self.events(), self.ids)
        self.assertEqual(report["sessions"], 100)
        self.assertEqual(report["recommendations"], 100)
        self.assertEqual(report["recommendation_item_rows"], 300)
        self.assertEqual(report["duplicate_rows"], 1)
        self.assertGreater(report["sessions_without_selection"], 0)
        self.assertGreater(report["selections"], 0)
        self.assertGreater(report["late_unique_events"], 0)
        self.assertGreater(report["cross_day_selections"], 0)

    def test_wrong_selected_product_is_rejected(self):
        events = self.events()
        next(e for e in events if e["event_type"] == "selection")["selected_product_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "选择商品"):
            validate_events(events, self.ids)

    def test_conflicting_duplicate_is_rejected(self):
        events = self.events()
        conflicting = deepcopy(next(e for e in events if e["event_type"] == "recommendation"))
        conflicting["match_scores"] = [1, 2, 3]
        events.append(conflicting)
        with self.assertRaisesRegex(ValueError, "不同内容"):
            validate_events(events, self.ids)

    def test_bad_time_is_rejected(self):
        events = self.events()
        events[0]["ingested_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "到达时间"):
            validate_events(events, self.ids)

    def test_invalid_configuration_is_rejected(self):
        for config in ({"sessions": 0}, {"days": 0}):
            with self.assertRaises(ValueError):
                list(generate_events(self.ids, **config))
        with self.assertRaises(ValueError):
            list(generate_events(["p1", "p1", "p2"]))

    def test_jsonl_roundtrip_and_overwrite_protection(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "events"
            events = self.events()
            write_events(output, events)
            self.assertEqual(validate_events(read_events(output), self.ids), validate_events(events, self.ids))
            before = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*.jsonl")}
            with self.assertRaises(FileExistsError):
                write_events(output, events)
            self.assertEqual(before, {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*.jsonl")})


if __name__ == "__main__":
    unittest.main(verbosity=2)
