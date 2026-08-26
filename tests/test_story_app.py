from __future__ import annotations

from streamlit.testing.v1 import AppTest

from heritagelink.story_models import StoryProjectStatus
from heritagelink.story_visual_models import VisualPackageStatus


def _button(app: AppTest, label: str):  # type: ignore[no-untyped-def]
    return [button for button in app.button if button.label == label][-1]


def test_artisan_can_generate_review_approve_and_export_story() -> None:
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "artisan"
    app.run(timeout=30)

    _button(app, "Story Studio").click().run(timeout=30)

    assert not app.exception
    assert any("把手艺人的真实故事变成可拍摄脚本" in str(item.value) for item in app.markdown)
    assert len(app.selectbox) >= 3

    _button(app, "生成脚本并运行 Guardian").click().run(timeout=30)

    project = app.session_state["story_project"]
    assert not app.exception
    assert project.status is StoryProjectStatus.AWAITING_HUMAN_APPROVAL
    assert project.script.total_duration_seconds == 60
    assert len(project.script.scenes) == 6
    assert any("审核通过" in str(item.value) for item in app.success)

    _button(app, "批准脚本").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["story_project"].status is StoryProjectStatus.APPROVED
    assert app.get("download_button")

    _button(app, "保存视觉设定并建立故事板").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["story_visual_package"].status is VisualPackageStatus.DRAFT

    _button(app, "生成全部缺失分镜图").click().run(timeout=30)

    visual_package = app.session_state["story_visual_package"]
    assert not app.exception
    assert visual_package.selected_count == 6
    assert visual_package.status is VisualPackageStatus.AWAITING_APPROVAL
    assert len(app.get("imgs") or app.get("image")) >= 6

    _button(app, "批准全部已选分镜图").click().run(timeout=30)

    assert not app.exception
    assert app.session_state["story_visual_package"].status is VisualPackageStatus.APPROVED
    assert len(app.get("download_button")) >= 2
