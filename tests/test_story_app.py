from __future__ import annotations

from streamlit.testing.v1 import AppTest

from heritagelink.oral_story_models import OralClaimStatus, OralStoryStatus
from heritagelink.story_models import NarrativeTemplate, StoryProjectStatus
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
    assert any("海外多平台发布包" in str(item.value) for item in app.markdown)
    assert any(button.label == "导出四平台发布包 ZIP" for button in app.get("download_button"))

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


def test_artisan_can_turn_confirmed_oral_history_into_a_guardian_reviewed_script() -> None:
    app = AppTest.from_file("app.py")
    app.query_params["mode"] = "artisan"
    app.run(timeout=30)
    _button(app, "Story Studio").click().run(timeout=30)

    transcript = next(item for item in app.text_area if item.label == "口述或采访转写文本")
    transcript.input(
        "[00:05] 我叫李师傅，在芜湖做铁画。\n"
        "[00:18] 我从十八岁开始跟着父亲学艺。\n"
        "[00:42] 最难的是焊点既牢固又不能太重。\n"
        "[01:10] 我希望年轻人以后还能听见敲击声。\n"
        "[01:35] 有人叫我是国家级大师。"
    )
    _button(app, "提取故事事实").click().run(timeout=30)

    session = app.session_state["oral_story_session"]
    assert not app.exception
    assert session.status is OralStoryStatus.REVIEWING
    assert any(claim.status is OralClaimStatus.NEEDS_EVIDENCE for claim in session.claims)
    assert any("口述事实台账与人工确认" in str(item.value) for item in app.markdown)

    _button(app, "确认全部可公开口述，并排除高风险声明").click().run(timeout=30)

    session = app.session_state["oral_story_session"]
    assert not app.exception
    assert session.status is OralStoryStatus.READY_FOR_SCRIPT
    assert all(
        claim.status is OralClaimStatus.EXCLUDED
        for claim in session.claims
        if claim.requires_external_evidence
    )

    _button(app, "用已确认口述生成 60 秒剧本").click().run(timeout=30)

    project = app.session_state["story_project"]
    assert not app.exception
    assert project.script.story_core.template is NarrativeTemplate.ORAL_HISTORY
    assert project.status is StoryProjectStatus.AWAITING_HUMAN_APPROVAL
    assert project.guardian_review.approved is True
    assert project.script.total_duration_seconds == 60
    assert "国家级大师" not in "\n".join(scene.voiceover for scene in project.script.scenes)
