import pytest
from typer.testing import CliRunner


def test_study_list_empty(tmp_path):
    import os
    from huaqi_src.config import paths as config_paths
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.cli.commands.study import study_app
    runner = CliRunner()
    result = runner.invoke(study_app, ["--list"])
    assert result.exit_code == 0
    assert "暂无" in result.output or "课程" in result.output


def test_study_reset_nonexistent(tmp_path):
    import os
    from huaqi_src.config import paths as config_paths
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.cli.commands.study import study_app
    runner = CliRunner()
    result = runner.invoke(study_app, ["--reset", "rust"])
    assert result.exit_code == 0
    assert "未找到" in result.output or "不存在" in result.output


def test_study_list_with_courses(tmp_path):
    import os
    from huaqi_src.config import paths as config_paths
    from huaqi_src.layers.capabilities.learning.models import CourseOutline, LessonOutline
    from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore

    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    config_paths._USER_DATA_DIR = tmp_path

    store = LearningProgressStore(tmp_path / "learning")
    store.save_course(CourseOutline(
        skill_name="Rust", slug="rust",
        lessons=[LessonOutline(index=1, title="所有权", status="completed")],
    ))

    from huaqi_src.cli.commands.study import study_app
    runner = CliRunner()
    result = runner.invoke(study_app, ["--list"])
    assert result.exit_code == 0
    assert "Rust" in result.output
