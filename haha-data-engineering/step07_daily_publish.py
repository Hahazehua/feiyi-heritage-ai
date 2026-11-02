"""Fixed DWD snapshot -> as-of metrics -> immutable daily JSON serving versions."""
import argparse
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "output/airflow/bb864b1b9297e08e0143"
STORE = ROOT / "output/published"
TABLES = ("dws_product_daily", "ads_scene_budget_daily", "ads_daily_overview")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fingerprint():
    files = []
    for folder in (SOURCE / "step04_try1", SOURCE / "step02_try1/dim_product_snapshot"):
        if not (folder / "_SUCCESS").exists():
            raise ValueError("Fixed input snapshot is not complete")
        for p in sorted(folder.rglob("*.parquet")):
            files.append((str(p.relative_to(SOURCE)), hashlib.sha256(p.read_bytes()).hexdigest()))
    if not files:
        raise ValueError("Missing input files")
    return digest(files)


def compute(as_of):
    from step05_daily_metrics import build_metrics, parse_as_of
    from step02_product_dimension import start_spark
    cutoff = parse_as_of(as_of).isoformat()
    identity = {"input_sha256": fingerprint(), "as_of": cutoff, "logic_version": 1,
                "logic_sha256": hashlib.sha256((ROOT / "step05_daily_metrics.py").read_bytes()).hexdigest()}
    path = STORE / "cache" / (digest(identity) + ".json")
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing["identity"] != identity or existing["tables_sha256"] != digest(existing["tables"]):
            raise ValueError("Cached result integrity failure")
        return path
    spark = start_spark()
    base = None
    try:
        dwd = SOURCE / "step04_try1"
        base, frames = build_metrics(spark.read.parquet(str(dwd / "dwd_recommendation_item")),
                                    spark.read.parquet(str(dwd / "dwd_selection")),
                                    spark.read.parquet(str(SOURCE / "step02_try1/dim_product_snapshot")),
                                    parse_as_of(cutoff))
        tables = {name: sorted([json.loads(row) for row in frame.toJSON().collect()], key=canonical)
                  for name, frame in frames.items()}
        atomic_json(path, {"identity": identity, "tables": tables, "tables_sha256": digest(tables)})
        return path
    finally:
        if base is not None:
            base.unpersist()
        spark.stop()


def validate(tables):
    if set(tables) != set(TABLES):
        raise ValueError("Missing metric table")
    totals = []
    keys = {TABLES[0]: ["product_id"], TABLES[1]: ["scene", "budget_per_item_fen"], TABLES[2]: []}
    for name, rows in tables.items():
        seen = set()
        for row in rows:
            key = tuple(row[k] for k in ["metric_date", "data_source", *keys[name]])
            if key in seen:
                raise ValueError("Duplicate business key")
            seen.add(key)
            n, s, b = (row[k] for k in ("recommendation_item_count", "selection_count", "customization_brief_count"))
            if not 0 <= b <= s <= n or n != row["recommendation_count"] * (3 if name != TABLES[0] else 1):
                raise ValueError("Invalid metric counts")
            if row["data_source"] != "synthetic_demo":
                raise ValueError("Unexpected source")
        totals.append(tuple(sum(r[k] for r in rows) for k in ("recommendation_item_count", "selection_count", "customization_brief_count")))
    if len(set(totals)) != 1:
        raise ValueError("Cross-table reconciliation failed")


def publish(cache, business_date, refresh_days=1, store=STORE):
    import fcntl  # Linux single-host publication lock; Airflow also limits active runs.
    snapshot = json.loads(Path(cache).read_text(encoding="utf-8"))
    if snapshot["tables_sha256"] != digest(snapshot["tables"]):
        raise ValueError("Snapshot integrity failure")
    end = date.fromisoformat(business_date)
    if not 1 <= refresh_days <= 60:
        raise ValueError("Invalid refresh range")
    versions = {}
    for offset in range(refresh_days):
        day = (end - timedelta(days=offset)).isoformat()
        tables = {name: [r for r in snapshot["tables"][name] if r["metric_date"] == day] for name in TABLES}
        validate(tables)
        payload = {"business_date": day, "identity": snapshot["identity"], "tables": tables}
        version = digest(payload)
        versions[day] = (version, payload)
    store.mkdir(parents=True, exist_ok=True)
    with (store / ".publish.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        catalog_path = store / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {"days": {}}
        changed, unchanged, stale = [], [], []
        for day, (version, payload) in versions.items():
            old = catalog["days"].get(day)
            if old and old["as_of"] > snapshot["identity"]["as_of"]:
                stale.append(day)
                continue
            if old and old["version"] == version:
                unchanged.append(day)
                continue
            target = store / "versions" / (version + ".json")
            if not target.exists():
                atomic_json(target, payload)
            elif digest(json.loads(target.read_text(encoding="utf-8"))) != version:
                raise ValueError("Published version was modified")
            catalog["days"][day] = {"version": version, "as_of": snapshot["identity"]["as_of"]}
            changed.append(day)
        if changed:
            atomic_json(catalog_path, catalog)  # all three tables/dates become visible together
        return {"changed": changed, "unchanged": unchanged, "stale_skipped": stale,
                "catalog_sha256": digest(catalog)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    print("CACHE_PATH=" + str(compute(args.as_of)))
