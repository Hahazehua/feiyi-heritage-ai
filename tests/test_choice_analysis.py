from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from heritagelink.choice_analysis import ChoiceAnalysisRequest, ChoiceAnalysisService
from heritagelink.repositories.sqlite_choice_repository import SQLiteChoiceRepository

ROOT = Path(__file__).parents[1]
GENERATOR = ROOT / "scripts" / "generate_synthetic_choice_data.py"
CLI = ROOT / "skills" / "analyze-gift-choice-signals" / "scripts" / "analyze_choices.py"


def _generate(path: Path, sessions: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--database",
            str(path),
            "--sessions",
            str(sessions),
            "--seed",
            "42",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_empty_database_returns_valid_zero_summary(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    SQLiteChoiceRepository(path)

    result = ChoiceAnalysisService.from_sqlite(path).build_summary(ChoiceAnalysisRequest())

    assert result.overall_funnel["sessions_started"] == 0
    assert result.overall_funnel["selection_rate"] is None
    assert result.product_metrics == ()
    assert result.observations == ("当前没有可分析的已授权匿名事件。",)


def test_aggregate_product_rank_segment_budget_and_turn_metrics(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.db"
    generated = _generate(path)
    assert generated.returncode == 0

    result = ChoiceAnalysisService.from_sqlite(path).build_summary(
        ChoiceAnalysisRequest(minimum_sample_size=1)
    )

    assert result.overall_funnel["sessions_started"] == 10
    assert result.overall_funnel["sessions_with_recommendations"] == 10
    assert sum(row["recommendation_count"] for row in result.product_metrics) == 30
    assert (
        sum(row["selection_count"] for row in result.product_metrics)
        == result.overall_funnel["sessions_with_selection"]
    )
    assert {row["rank_position"] for row in result.rank_metrics} == {1, 2, 3}
    assert all(row["recommendation_count"] == 10 for row in result.rank_metrics)
    dimensions = {row["dimension"] for row in result.segment_metrics}
    assert {"recipient", "scene", "budget_bucket", "logo_required"} <= dimensions
    assert result.conversation_metrics["average_turns_before_recommendation"] == 3.0
    assert result.synthetic_data_notice is not None
    assert result.data_sources == ("synthetic_demo",)


def test_filters_nonselection_and_brief_rates_are_consistent(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.db"
    assert _generate(path, sessions=20).returncode == 0
    service = ChoiceAnalysisService.from_sqlite(path)

    all_result = service.build_summary(ChoiceAnalysisRequest(minimum_sample_size=1))
    scene_result = service.build_summary(
        ChoiceAnalysisRequest(scene="anniversary", minimum_sample_size=1)
    )
    budget_result = service.build_summary(
        ChoiceAnalysisRequest(budget_bucket="under_500", minimum_sample_size=1)
    )

    assert scene_result.overall_funnel["sessions_started"] == 5
    assert budget_result.overall_funnel["sessions_started"] == 4
    assert all_result.overall_funnel["recommendation_without_selection_rate"] is not None
    assert all_result.overall_funnel["customization_brief_rate"] is not None


def test_small_sample_suppresses_rates_and_warns(tmp_path: Path) -> None:
    path = tmp_path / "small.db"
    assert _generate(path, sessions=3).returncode == 0

    result = ChoiceAnalysisService.from_sqlite(path).build_summary(ChoiceAnalysisRequest())

    assert result.sample_size_warning
    assert result.overall_funnel["selection_rate"] is None
    assert all(row["selection_rate"] is None for row in result.rank_metrics)


@pytest.mark.parametrize("output_format", ["json", "table"])
def test_cli_outputs_aggregate_report_without_person_level_ids(
    tmp_path: Path, output_format: str
) -> None:
    path = tmp_path / "cli.db"
    assert _generate(path).returncode == 0
    completed = subprocess.run(
        [sys.executable, str(CLI), "--database", str(path), "--format", output_format],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "anon_" not in completed.stdout
    assert "postgresql://" not in completed.stdout
    if output_format == "json":
        payload = json.loads(completed.stdout)
        assert payload["overall_funnel"]["sessions_started"] == 10
    else:
        assert "产品指标" in completed.stdout
        assert "合成演示数据" in completed.stdout


def test_cli_missing_database_exits_safely_without_secret_output(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    completed = subprocess.run(
        [sys.executable, str(CLI), "--database", str(missing)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "不存在" in completed.stderr
    assert "password" not in completed.stderr.lower()
