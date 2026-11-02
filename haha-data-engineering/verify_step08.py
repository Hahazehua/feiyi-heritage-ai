"""Windows dashboard functional verification and benchmark evidence checks."""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import urllib.request
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent
app = AppTest.from_file(str(ROOT / "dashboard.py")).run(timeout=30)
assert not app.exception
full = {m.label: m.value for m in app.metric}
assert full["推荐次数"] == "10,000" and full["选择次数"] == "6,429"
app.sidebar.slider[0].set_value((date(2026, 8, 8), date(2026, 8, 10))).run()
assert not app.exception
filtered = {m.label: m.value for m in app.metric}
assert filtered["推荐次数"] == "1,014" and filtered["选择次数"] == "669"
report = json.loads((ROOT / "output/benchmark/results.json").read_text())
assert len(report["results"]) == 8
for n in (100000, 1000000):
    results = {r["query"]: r for r in report["results"] if r["rows"] == n}
    assert results["broadcast_join"]["checksum"] == results["sort_merge_join"]["checksum"]
    assert results["partition_pruned"]["checksum"] == results["full_scan_conditional"]["checksum"]
    for query, needle in (("broadcast_join", "BroadcastHashJoin"), ("sort_merge_join", "SortMergeJoin"),
                          ("partition_pruned", "PartitionFilters: [isnotnull"), ("full_scan_conditional", "PartitionFilters: []")):
        assert needle in (ROOT / f"output/benchmark/plan_{n}_{query}.txt").read_text()
    assert all(len(r["seconds"]) == 3 and all(r["spark_job_ids"]) for r in results.values())
health = urllib.request.urlopen("http://localhost:8501/_stcore/health", timeout=10).status
assert health == 200
proof = {"captured_at": datetime.now(timezone.utc).isoformat(), "all_passed": True,
         "dashboard_full": full, "dashboard_filtered_aug08_aug10": filtered,
         "dashboard_exceptions": 0, "dashboard_health": health, "benchmark_groups": 8,
         "checksums_match": True, "physical_plans_match": True, "measurements_per_group": 3}
(ROOT / "output/step08_verification.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(proof, ensure_ascii=False, indent=2))
