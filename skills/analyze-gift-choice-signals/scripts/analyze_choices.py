"""Print a privacy-safe aggregate gift choice report from local SQLite data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from heritagelink.choice_analysis import (  # noqa: E402
    ChoiceAnalysisRequest,
    ChoiceAnalysisService,
)

DEFAULT_DATABASE = ROOT / ".local" / "heritagelink_analytics_demo.db"


def _date(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _table(result: dict[str, Any]) -> str:
    funnel = result["overall_funnel"]
    lines = [
        "HeritageLink AI 匿名选择信号分析",
        "=" * 38,
        f"会话数: {funnel['sessions_started']}",
        f"产生推荐: {funnel['sessions_with_recommendations']}",
        f"产生选择: {funnel['sessions_with_selection']}",
        f"生成方案: {funnel['sessions_with_customization_brief']}",
        "",
        "产品指标",
        "product_id           recommended selected rate",
    ]
    for row in result["product_metrics"]:
        rate = "样本不足" if row["selection_rate"] is None else f"{row['selection_rate']:.1%}"
        lines.append(
            f"{row['product_id']:<20} {row['recommendation_count']:>11} "
            f"{row['selection_count']:>8} {rate}"
        )
    lines.extend(("", "排名指标", "rank recommended selected rate"))
    for row in result["rank_metrics"]:
        rate = "样本不足" if row["selection_rate"] is None else f"{row['selection_rate']:.1%}"
        lines.append(
            f"{row['rank_position']:>4} {row['recommendation_count']:>11} "
            f"{row['selection_count']:>8} {rate}"
        )
    average = result["conversation_metrics"]["average_turns_before_selection"]
    lines.extend(("", f"选择前平均对话轮数: {average if average is not None else '无数据'}"))
    if result["sample_size_warning"]:
        lines.append(result["sample_size_warning"])
    if result["synthetic_data_notice"]:
        lines.append(result["synthetic_data_notice"])
    lines.append("结果只描述匿名聚合相关关系，不代表因果关系。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--scene")
    parser.add_argument("--recipient")
    parser.add_argument("--budget-bucket")
    parser.add_argument("--product-id")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--minimum-sample-size", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        service = ChoiceAnalysisService.from_sqlite(args.database)
        result = service.build_summary(
            ChoiceAnalysisRequest(
                date_from=_date(args.date_from),
                date_to=_date(args.date_to),
                recipient=args.recipient,
                scene=args.scene,
                budget_bucket=args.budget_bucket,
                product_id=args.product_id,
                minimum_sample_size=args.minimum_sample_size,
            )
        ).to_dict()
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_table(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
