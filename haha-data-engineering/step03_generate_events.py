"""第三课：从商品维度生成可复现的模拟会话、推荐与选择 JSONL。"""

import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
from uuid import NAMESPACE_URL, uuid5

from step02_product_dimension import ROOT, start_spark

DEFAULT_DIMENSION = ROOT / "output/step02_20260907_201837_082177/dim_product_snapshot"
KINDS = ("session", "recommendation", "selection")


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def generate_events(product_ids, *, sessions=10000, seed=42, start=date(2026, 8, 8), days=30):
    """逐条生成；只模拟行为，不调用线上推荐器，不代表真实客户偏好。"""
    product_ids = sorted(product_ids)
    if sessions < 1 or days < 1 or len(product_ids) < 3 or len(set(product_ids)) != len(product_ids):
        raise ValueError("会话数和天数必须为正，商品必须至少三个且编号唯一")
    rng = random.Random(seed)
    base = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    config = f"v1:{seed}:{start}:{days}:{','.join(product_ids)}"
    for index in range(sessions):
        uid = uuid5(NAMESPACE_URL, f"{config}:{index}").hex
        session_id, recommendation_id = "anon_" + uid, "rec_" + uid
        began = base + timedelta(seconds=rng.randrange(days * 86400 - 120))
        shown = began + timedelta(seconds=60)
        recommended = rng.sample(product_ids, 3)
        chosen = rng.random() < 0.65
        selected_at = shown + timedelta(seconds=rng.randint(60, 23 * 3600)) if chosen else None
        rank = rng.choices([1, 2, 3], weights=[6, 3, 1])[0] if chosen else None
        brief = chosen and rng.random() < 0.30
        scene = rng.choice(["business_gifting", "teacher_appreciation", "anniversary", "wedding"])
        budget = rng.choice([50000, 100000, 200000, 500000])

        def envelope(kind, event_id, at):
            # 每 20 个会话有一组日志晚到 48 小时，用于下一课练习事件时间与到达时间。
            received = at + timedelta(seconds=30, hours=48 if index % 20 == 0 else 0)
            return dict(schema_version="1", data_source="synthetic_demo", event_type=kind,
                        event_id=event_id, anonymous_session_id=session_id,
                        event_time=stamp(at), ingested_at=stamp(received))

        session = envelope("session", "ses_" + uid, began)
        session.update(session_started_at=stamp(began), scene=scene, budget_per_item_fen=budget,
                       entry_source="synthetic_generator", app_version="learning-v1")
        yield session
        rec = envelope("recommendation", recommendation_id, shown)
        rec.update(recommendation_event_id=recommendation_id,
                   recommendation_timestamp=stamp(shown), recommended_product_ids=recommended,
                   ranking_positions=[1, 2, 3], match_scores=[88.0, 78.0, 68.0])
        yield rec
        # 每 100 个会话模拟一次重复投递；事件 ID 和内容均保持一致。
        if index % 100 == 0:
            yield dict(rec)
        if chosen:
            selection = envelope("selection", "sel_" + uid, selected_at)
            selection.update(selection_event_id="sel_" + uid,
                             recommendation_event_id=recommendation_id,
                             selected_product_id=recommended[rank - 1], selected_rank_position=rank,
                             selected_at=stamp(selected_at),
                             whether_customization_brief_generated=bool(brief),
                             final_action="customization_brief_generated" if brief else "selected")
            yield selection


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_events(events, product_ids):
    """独立回读检查：重复必须完全相同，选择必须属于对应推荐，时间顺序有效。"""
    allowed = set(product_ids)
    unique, counts = {}, Counter()
    for event in events:
        kind = event["event_type"]
        if kind not in KINDS or event["data_source"] != "synthetic_demo":
            raise ValueError("事件类型或模拟标记不正确")
        if parse_time(event["ingested_at"]) < parse_time(event["event_time"]):
            raise ValueError("到达时间早于事件时间")
        counts[kind] += 1
        key = event["event_id"]
        if key in unique and unique[key] != event:
            raise ValueError("同一事件 ID 对应不同内容")
        unique[key] = event
    sessions = {e["anonymous_session_id"]: e for e in unique.values() if e["event_type"] == "session"}
    recs = {e["event_id"]: e for e in unique.values() if e["event_type"] == "recommendation"}
    selected = [e for e in unique.values() if e["event_type"] == "selection"]
    rec_sessions = Counter()
    selected_recs = set()
    for rec in recs.values():
        sid = rec["anonymous_session_id"]
        ids = rec["recommended_product_ids"]
        if (sid not in sessions or len(ids) != 3 or len(set(ids)) != 3 or not set(ids) <= allowed
                or rec["ranking_positions"] != [1, 2, 3] or len(rec["match_scores"]) != 3
                or rec["recommendation_event_id"] != rec["event_id"]
                or parse_time(rec["event_time"]) < parse_time(sessions[sid]["event_time"])):
            raise ValueError("推荐关联、数组或时间错误")
        rec_sessions[sid] += 1
    if set(rec_sessions) != set(sessions) or any(n != 1 for n in rec_sessions.values()):
        raise ValueError("本版每个会话必须有一次推荐，未选择会话也必须保留")
    for choice in selected:
        rec = recs.get(choice["recommendation_event_id"])
        rank = choice["selected_rank_position"]
        if (rec is None or choice["anonymous_session_id"] != rec["anonymous_session_id"]
                or rank not in (1, 2, 3) or choice["selected_product_id"] != rec["recommended_product_ids"][rank - 1]
                or not timedelta(0) <= parse_time(choice["event_time"]) - parse_time(rec["event_time"]) < timedelta(hours=24)
                or rec["event_id"] in selected_recs):
            raise ValueError("选择商品、排名、会话关联或时间错误")
        selected_recs.add(rec["event_id"])
    return dict(raw_rows=dict(counts), unique_events=len(unique), duplicate_rows=sum(counts.values()) - len(unique),
                sessions=len(sessions), recommendations=len(recs), selections=len(selected),
                sessions_without_selection=len(sessions) - len(selected),
                recommendation_item_rows=sum(len(r["recommended_product_ids"]) for r in recs.values()),
                customization_briefs=sum(e["whether_customization_brief_generated"] for e in selected),
                late_unique_events=sum(parse_time(e["ingested_at"]) - parse_time(e["event_time"]) >= timedelta(hours=48) for e in unique.values()),
                cross_day_selections=sum(e["event_time"][:10] != recs[e["recommendation_event_id"]]["event_time"][:10] for e in selected))


def read_events(output):
    for path in sorted(output.glob("*/ingest_date=*/*.jsonl")):
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                yield json.loads(line)


def write_events(output, events):
    output.mkdir(parents=True, exist_ok=False)
    with ExitStack() as stack:
        handles = {}
        for event in events:
            key = (event["event_type"], event["ingested_at"][:10])
            if key not in handles:
                folder = output / key[0] / ("ingest_date=" + key[1])
                folder.mkdir(parents=True)
                handles[key] = stack.enter_context((folder / "part-00000.jsonl").open("x", encoding="utf-8", newline="\n"))
            handles[key].write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="调度器指定的本次输出目录")
    parser.add_argument("--dimension", type=Path, default=DEFAULT_DIMENSION)
    parser.add_argument("--sessions", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 8, 8))
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    spark = start_spark()
    try:
        if not (args.dimension / "_SUCCESS").is_file():
            raise ValueError("需要第二步成功输出的商品维度")
        dim = spark.read.parquet(args.dimension.resolve().as_uri())
        # 只抽取少量维度 ID 到 Python；不把行为大表 collect 到驱动端。
        ids = sorted(r.product_id for r in dim.filter("catalog_role = 'recommendation_demo'").select("product_id").collect())
        output = args.output_dir.resolve() if args.output_dir else ROOT / "output" / ("step03_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        write_events(output, generate_events(ids, sessions=args.sessions, seed=args.seed, start=args.start_date, days=args.days))
        report = validate_events(read_events(output), ids)
        if report["sessions"] != args.sessions:
            raise ValueError("生成会话数与参数不一致")
        # Spark 实际读取每类 JSONL，核对公共时间字段和原始记录数。
        schema = "schema_version STRING, data_source STRING, event_type STRING, event_id STRING, anonymous_session_id STRING, event_time TIMESTAMP, ingested_at TIMESTAMP"
        spark_counts = {}
        for kind in KINDS:
            if not (output / kind).exists():
                spark_counts[kind] = 0
                continue
            frame = spark.read.schema(schema).option("mode", "FAILFAST").option("recursiveFileLookup", "true").json((output / kind).as_uri())
            count = frame.count()
            if count != report["raw_rows"].get(kind, 0) or frame.filter("event_id IS NULL OR event_time IS NULL OR ingested_at IS NULL").limit(1).count():
                raise ValueError("Spark 回读数量或字段解析错误")
            spark_counts[kind] = count
        report.update(data_source="synthetic_demo", schema_version="1", seed=args.seed,
                      start_date=args.start_date.isoformat(), days=args.days,
                      eligible_products=len(ids), product_ids=ids, dimension_input=str(args.dimension.resolve()),
                      spark_read_counts=spark_counts, validation_passed=True,
                      note="固定商品快照上的模拟行为；不代表历史真实目录、真实客户偏好或实际推荐算法表现",
                      files=[dict(path=str(p.relative_to(output)), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(output.glob("*/ingest_date=*/*.jsonl"))])
        (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "_SUCCESS").write_text("validated synthetic events\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k not in ("files", "product_ids")}, ensure_ascii=False, indent=2))
        print(f"第三步完成：{output}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
