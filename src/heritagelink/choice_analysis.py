"""Privacy-safe aggregate analysis for consented gift choice events."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

SAMPLE_WARNING = "当前样本量不足，仅展示观察结果，不代表稳定偏好。"
SYNTHETIC_NOTICE = "当前结果基于合成演示数据，不代表真实客户偏好。"
SCENE_ALIASES = {"business": "business_gifting"}


@dataclass(frozen=True, slots=True)
class ChoiceAnalysisRequest:
    date_from: datetime | None = None
    date_to: datetime | None = None
    recipient: str | None = None
    scene: str | None = None
    budget_bucket: str | None = None
    product_id: str | None = None
    minimum_sample_size: int = 5
    requested_metrics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.minimum_sample_size < 1:
            raise ValueError("minimum_sample_size 必须大于 0")


@dataclass(frozen=True, slots=True)
class AnalysisDataset:
    sessions: tuple[dict[str, Any], ...]
    requirements: tuple[dict[str, Any], ...]
    recommendations: tuple[dict[str, Any], ...]
    selections: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ChoiceAnalysisResult:
    overall_funnel: dict[str, Any]
    product_metrics: tuple[dict[str, Any], ...]
    rank_metrics: tuple[dict[str, Any], ...]
    segment_metrics: tuple[dict[str, Any], ...]
    conversation_metrics: dict[str, Any]
    data_quality: dict[str, int]
    observations: tuple[str, ...]
    sample_size_warning: str | None
    limitations: tuple[str, ...]
    generated_at: str
    data_window: dict[str, str | None]
    data_sources: tuple[str, ...]
    synthetic_data_notice: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChoiceAnalysisService:
    def __init__(self, dataset: AnalysisDataset) -> None:
        self.dataset = dataset

    @classmethod
    def from_sqlite(cls, database_path: str | Path) -> ChoiceAnalysisService:
        path = Path(database_path)
        if not path.is_file():
            raise FileNotFoundError(f"分析数据库不存在：{path}")
        return cls(load_sqlite_dataset(path))

    def build_summary(self, request: ChoiceAnalysisRequest) -> ChoiceAnalysisResult:
        sessions, requirements, recommendations, selections = _filter_dataset(self.dataset, request)
        session_ids = {row["anonymous_session_id"] for row in sessions}
        recommendation_sessions = {row["anonymous_session_id"] for row in recommendations}
        selection_sessions = {row["anonymous_session_id"] for row in selections}
        brief_sessions = {
            row["anonymous_session_id"]
            for row in selections
            if row["whether_customization_brief_generated"]
        }
        minimum = request.minimum_sample_size
        overall = {
            "sessions_started": len(session_ids),
            "sessions_with_recommendations": len(recommendation_sessions),
            "sessions_with_selection": len(selection_sessions),
            "sessions_with_customization_brief": len(brief_sessions),
            "selection_rate": _safe_rate(len(selection_sessions), len(session_ids), minimum),
            "customization_brief_rate": _safe_rate(len(brief_sessions), len(session_ids), minimum),
            "recommendation_without_selection_rate": _safe_rate(
                len(recommendation_sessions - selection_sessions),
                len(recommendation_sessions),
                minimum,
            ),
        }
        unique_choices = _unique_product_choices(selections)
        product_metrics = _product_metrics(recommendations, unique_choices, minimum)
        rank_metrics = _rank_metrics(recommendations, unique_choices, minimum)
        segment_metrics = _segment_metrics(sessions, requirements, selection_sessions, minimum)
        conversation_metrics = _conversation_metrics(sessions, selection_sessions, minimum)
        data_sources = tuple(sorted({row.get("data_source", "consented_user") for row in sessions}))
        recommended_products = {
            (row["recommendation_event_id"], product_id)
            for row in recommendations
            for product_id in row["recommended_product_ids"]
        }
        unknown_products = sum(
            (row["recommendation_event_id"], row["selected_product_id"]) not in recommended_products
            for row in selections
        )
        total_events = len(sessions) + len(requirements) + len(recommendations) + len(selections)
        quality = {
            "total_events": total_events,
            "duplicate_events_ignored": 0,
            "invalid_events": 0,
            "events_without_consent": 0,
            "unknown_product_events": unknown_products,
        }
        sample_warning = SAMPLE_WARNING if len(session_ids) < minimum else None
        observations = _observations(overall, product_metrics, rank_metrics)
        timestamps = [row["session_started_at"] for row in sessions]
        return ChoiceAnalysisResult(
            overall_funnel=overall,
            product_metrics=product_metrics,
            rank_metrics=rank_metrics,
            segment_metrics=segment_metrics,
            conversation_metrics=conversation_metrics,
            data_quality=quality,
            observations=observations,
            sample_size_warning=sample_warning,
            limitations=(
                "结果仅描述已授权匿名事件中的相关关系，不代表因果关系。",
                "未授权会话不会进入偏好数据库，因此无法从该库估算未授权人数。",
            ),
            generated_at=datetime.now(UTC).isoformat(),
            data_window={
                "from": min(timestamps) if timestamps else None,
                "to": max(timestamps) if timestamps else None,
            },
            data_sources=data_sources,
            synthetic_data_notice=(SYNTHETIC_NOTICE if "synthetic_demo" in data_sources else None),
        )


def load_sqlite_dataset(database_path: str | Path) -> AnalysisDataset:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        required = {
            "sessions",
            "final_requirements",
            "recommendation_events",
            "selection_events",
        }
        if not required.issubset(tables):
            return AnalysisDataset((), (), (), ())
        sessions = tuple(dict(row) for row in connection.execute("SELECT * FROM sessions"))
        requirements = tuple(
            dict(row) for row in connection.execute("SELECT * FROM final_requirements")
        )
        recommendations = tuple(
            _decode_recommendation(dict(row))
            for row in connection.execute("SELECT * FROM recommendation_events")
        )
        selections = tuple(
            dict(row) for row in connection.execute("SELECT * FROM selection_events")
        )
    return AnalysisDataset(sessions, requirements, recommendations, selections)


def _decode_recommendation(row: dict[str, Any]) -> dict[str, Any]:
    for name in ("recommended_product_ids", "ranking_positions", "match_scores"):
        row[name] = tuple(json.loads(row[name]))
    return row


def _filter_dataset(
    dataset: AnalysisDataset, request: ChoiceAnalysisRequest
) -> tuple[
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    requirements_by_session = {row["anonymous_session_id"]: row for row in dataset.requirements}
    sessions: list[dict[str, Any]] = []
    for session in dataset.sessions:
        started = _aware(datetime.fromisoformat(session["session_started_at"]))
        assert started is not None
        requirement = requirements_by_session.get(session["anonymous_session_id"], {})
        date_from = _aware(request.date_from)
        date_to = _aware(request.date_to)
        if date_from and started < date_from:
            continue
        if date_to and started > date_to:
            continue
        if request.recipient and requirement.get("recipient") != request.recipient:
            continue
        scene = SCENE_ALIASES.get(request.scene or "", request.scene)
        if scene and requirement.get("scene") != scene:
            continue
        if request.budget_bucket and _budget_bucket(requirement) != request.budget_bucket:
            continue
        if request.product_id and not any(
            row["anonymous_session_id"] == session["anonymous_session_id"]
            and request.product_id in row["recommended_product_ids"]
            for row in dataset.recommendations
        ):
            continue
        sessions.append(session)
    ids = {row["anonymous_session_id"] for row in sessions}
    requirements = tuple(row for row in dataset.requirements if row["anonymous_session_id"] in ids)
    recommendations = tuple(
        row
        for row in dataset.recommendations
        if row["anonymous_session_id"] in ids
        and (not request.product_id or request.product_id in row["recommended_product_ids"])
    )
    recommendation_ids = {row["recommendation_event_id"] for row in recommendations}
    selections = tuple(
        row
        for row in dataset.selections
        if row["anonymous_session_id"] in ids
        and row["recommendation_event_id"] in recommendation_ids
        and (not request.product_id or row["selected_product_id"] == request.product_id)
    )
    return tuple(sessions), requirements, recommendations, selections


def _safe_rate(numerator: int, denominator: int, minimum: int) -> float | None:
    if denominator == 0 or denominator < minimum:
        return None
    return round(numerator / denominator, 4)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _unique_product_choices(
    selections: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in selections:
        key = (row["anonymous_session_id"], row["selected_product_id"])
        current = unique.get(key)
        if current is None or current["final_action"] != "selected":
            unique[key] = row
    return tuple(unique.values())


def _product_metrics(
    recommendations: tuple[dict[str, Any], ...],
    selections: tuple[dict[str, Any], ...],
    minimum: int,
) -> tuple[dict[str, Any], ...]:
    recommended: Counter[str] = Counter()
    recommendation_ranks: dict[str, list[int]] = defaultdict(list)
    for event in recommendations:
        for product_id, rank in zip(
            event["recommended_product_ids"], event["ranking_positions"], strict=True
        ):
            recommended[product_id] += 1
            recommendation_ranks[product_id].append(int(rank))
    selected = Counter(row["selected_product_id"] for row in selections)
    selected_ranks: dict[str, list[int]] = defaultdict(list)
    for row in selections:
        selected_ranks[row["selected_product_id"]].append(row["selected_rank_position"])
    return tuple(
        {
            "product_id": product_id,
            "recommendation_count": count,
            "selection_count": selected[product_id],
            "selection_rate": _safe_rate(selected[product_id], count, minimum),
            "average_recommended_rank": round(fmean(recommendation_ranks[product_id]), 2),
            "average_selected_rank": (
                round(fmean(selected_ranks[product_id]), 2) if selected_ranks[product_id] else None
            ),
            "sample_size_sufficient": count >= minimum,
        }
        for product_id, count in sorted(recommended.items())
    )


def _rank_metrics(
    recommendations: tuple[dict[str, Any], ...],
    selections: tuple[dict[str, Any], ...],
    minimum: int,
) -> tuple[dict[str, Any], ...]:
    recommended = Counter(int(rank) for row in recommendations for rank in row["ranking_positions"])
    selected = Counter(int(row["selected_rank_position"]) for row in selections)
    return tuple(
        {
            "rank_position": rank,
            "recommendation_count": count,
            "selection_count": selected[rank],
            "selection_rate": _safe_rate(selected[rank], count, minimum),
            "sample_size_sufficient": count >= minimum,
        }
        for rank, count in sorted(recommended.items())
    )


def _segment_metrics(
    sessions: tuple[dict[str, Any], ...],
    requirements: tuple[dict[str, Any], ...],
    selection_sessions: set[str],
    minimum: int,
) -> tuple[dict[str, Any], ...]:
    session_ids = {row["anonymous_session_id"] for row in sessions}
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in requirements:
        session_id = row["anonymous_session_id"]
        if session_id not in session_ids:
            continue
        values = {
            "recipient": row.get("recipient") or "unknown",
            "scene": row.get("scene") or "unknown",
            "budget_bucket": _budget_bucket(row),
            "customization_required": _customization_required(row),
            "logo_required": _bool_segment(row.get("logo_required")),
            "destination_region": _destination_region(row.get("destination")),
        }
        for dimension, value in values.items():
            groups[(dimension, value)].add(session_id)
    return tuple(
        {
            "dimension": dimension,
            "value": value,
            "session_count": len(ids),
            "selection_count": len(ids & selection_sessions),
            "selection_rate": _safe_rate(len(ids & selection_sessions), len(ids), minimum),
            "sample_size_sufficient": len(ids) >= minimum,
        }
        for (dimension, value), ids in sorted(groups.items())
    )


def _conversation_metrics(
    sessions: tuple[dict[str, Any], ...], selection_sessions: set[str], minimum: int
) -> dict[str, Any]:
    all_turns = [int(row["conversation_turn_count"]) for row in sessions]
    selected_turns = [
        int(row["conversation_turn_count"])
        for row in sessions
        if row["anonymous_session_id"] in selection_sessions
    ]
    buckets: dict[str, set[str]] = defaultdict(set)
    for row in sessions:
        turns = int(row["conversation_turn_count"])
        label = "0-1" if turns <= 1 else "2-3" if turns <= 3 else "4-5"
        buckets[label].add(row["anonymous_session_id"])
    return {
        "average_turns_before_recommendation": round(fmean(all_turns), 2) if all_turns else None,
        "average_turns_before_selection": (
            round(fmean(selected_turns), 2) if selected_turns else None
        ),
        "selection_rate_by_turn_bucket": tuple(
            {
                "turn_bucket": label,
                "session_count": len(ids),
                "selection_count": len(ids & selection_sessions),
                "selection_rate": _safe_rate(len(ids & selection_sessions), len(ids), minimum),
                "sample_size_sufficient": len(ids) >= minimum,
            }
            for label, ids in sorted(buckets.items())
        ),
    }


def _budget_bucket(requirement: dict[str, Any]) -> str:
    budget = requirement.get("budget_per_item")
    if budget is None:
        return "unknown"
    value = float(budget)
    if value < 500:
        return "under_500"
    if value < 1000:
        return "500_999"
    if value < 2000:
        return "1000_1999"
    return "2000_plus"


def _customization_required(requirement: dict[str, Any]) -> str:
    values = requirement.get("customization_types", "[]")
    if isinstance(values, str):
        values = json.loads(values)
    return "true" if values else "false"


def _bool_segment(value: Any) -> str:
    if value is None:
        return "unknown"
    return "true" if bool(value) else "false"


def _destination_region(destination: str | None) -> str:
    if not destination:
        return "unknown"
    lowered = destination.lower()
    if any(token in lowered for token in ("海外", "美国", "欧洲", "日本", "新加坡")):
        return "international"
    return "domestic_or_unspecified"


def _observations(
    overall: dict[str, Any],
    products: tuple[dict[str, Any], ...],
    ranks: tuple[dict[str, Any], ...],
) -> tuple[str, ...]:
    if not overall["sessions_started"]:
        return ("当前没有可分析的已授权匿名事件。",)
    observations = [
        f"共纳入 {overall['sessions_started']} 个匿名会话，"
        f"其中 {overall['sessions_with_selection']} 个产生选择。"
    ]
    observations.append(f"分析覆盖 {len(products)} 个被推荐产品和 {len(ranks)} 个排名位置。")
    return tuple(observations)
