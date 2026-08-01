"""Skill 7 wrapper: on-demand aggregate analysis, never an online ranking update."""

from pathlib import Path

from heritagelink.choice_analysis import (
    AnalysisDataset,
    ChoiceAnalysisRequest,
    ChoiceAnalysisResult,
    ChoiceAnalysisService,
)


def execute(
    request: ChoiceAnalysisRequest,
    repository: ChoiceAnalysisService | AnalysisDataset | str | Path,
) -> ChoiceAnalysisResult:
    if isinstance(repository, ChoiceAnalysisService):
        service = repository
    elif isinstance(repository, AnalysisDataset):
        service = ChoiceAnalysisService(repository)
    else:
        service = ChoiceAnalysisService.from_sqlite(repository)
    return service.build_summary(request)
