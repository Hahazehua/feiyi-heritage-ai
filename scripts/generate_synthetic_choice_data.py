"""Generate deterministic anonymous analytics data for local demonstrations only."""

from __future__ import annotations

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from heritagelink.analytics_models import (  # noqa: E402
    FinalRequirementRecord,
    RecommendationEvent,
    SelectionEvent,
    SessionRecord,
)
from heritagelink.repositories.sqlite_choice_repository import (  # noqa: E402
    SQLiteChoiceRepository,
)

DEFAULT_DATABASE = ROOT / ".local" / "heritagelink_analytics_demo.db"
SCENES = ("anniversary", "business_gifting", "wedding", "teacher_appreciation")
RECIPIENTS = ("business_partner", "elder", "teacher", "friend")
BUDGETS = (380.0, 680.0, 980.0, 1280.0, 2200.0)
PRODUCTS = tuple(f"prod_demo_{index:03d}" for index in range(1, 21))


def generate(database: Path, *, sessions: int, seed: int) -> dict[str, int | str]:
    if sessions < 1:
        raise ValueError("sessions 必须大于 0")
    database.parent.mkdir(parents=True, exist_ok=True)
    repository = SQLiteChoiceRepository(database)
    rng = random.Random(seed)
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    selection_count = 0
    for index in range(sessions):
        session_id = f"anon_{uuid5(NAMESPACE_URL, f'synthetic:{seed}:{index}').hex}"
        started = base_time + timedelta(hours=index * 3)
        scene = SCENES[index % len(SCENES)]
        recipient = RECIPIENTS[index % len(RECIPIENTS)]
        budget = BUDGETS[index % len(BUDGETS)]
        recommended = tuple(rng.sample(PRODUCTS, 3))
        recommendation_id = str(uuid5(NAMESPACE_URL, f"{session_id}:recommend"))
        selected = rng.random() < 0.78
        completed = started + timedelta(minutes=5 + index % 8) if selected else None
        repository.save_session(
            SessionRecord(
                session_id,
                started,
                completed,
                1 + index % 5,
                "synthetic_generator",
                "synthetic-demo",
                consent_version="synthetic-demo-v1",
                consented_at=started,
                data_source="synthetic_demo",
            )
        )
        repository.save_final_requirement(
            FinalRequirementRecord(
                session_id,
                recipient,
                scene,
                "per_item",
                budget,
                None,
                1 + index % 30,
                ("elegant",) if index % 2 else ("grand",),
                ("heritage",),
                ("logo",) if index % 3 == 0 else (),
                index % 3 == 0,
                "overseas" if index % 4 == 0 else None,
                None,
                "bilingual" if index % 4 == 0 else "zh",
                ("recipient", "scene", "budget_per_item"),
                ("style_preferences",),
            )
        )
        recommendation = RecommendationEvent(
            recommendation_id,
            session_id,
            f"synthetic-signature-{index}",
            recommended,
            (1, 2, 3),
            (88.0, 78.0, 68.0),
            started + timedelta(minutes=3),
        )
        repository.save_recommendation(recommendation)
        if selected:
            rank = rng.choices((1, 2, 3), weights=(6, 3, 1), k=1)[0]
            product_id = recommended[rank - 1]
            repository.save_selection(
                SelectionEvent(
                    str(uuid5(NAMESPACE_URL, f"{recommendation_id}:select:{product_id}")),
                    recommendation_id,
                    session_id,
                    product_id,
                    rank,
                    completed or started,
                    "customization_brief_generated" if index % 3 == 0 else "selected",
                    index % 3 == 0,
                )
            )
            selection_count += 1
    return {
        "database": str(database),
        "sessions": sessions,
        "selections": selection_count,
        "seed": seed,
        "data_source": "synthetic_demo",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--sessions", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260730)
    args = parser.parse_args()
    result = generate(args.database, sessions=args.sessions, seed=args.seed)
    print(
        "已生成 {sessions} 个匿名合成会话和 {selections} 个选择事件。\n"
        "data_source={data_source}\n数据库：{database}".format(**result)
    )
    print("当前数据仅用于演示，不代表真实客户偏好。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
