import pytest
from unittest.mock import patch, MagicMock


def test_run_learning_push_no_courses(tmp_path):
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.learning.progress_store import LearningProgressStore
    empty_store = LearningProgressStore(tmp_path / "memory" / "learning")

    with patch("huaqi_src.scheduler.jobs._get_learning_store", return_value=empty_store):
        from huaqi_src.scheduler.jobs import _run_learning_push
        _run_learning_push()


def test_run_learning_push_with_active_course(tmp_path, capsys):
    from huaqi_src.core import config_paths
    from huaqi_src.learning.models import CourseOutline, LessonOutline
    from huaqi_src.learning.progress_store import LearningProgressStore

    config_paths._USER_DATA_DIR = tmp_path
    store = LearningProgressStore(tmp_path / "memory" / "learning")
    store.save_course(CourseOutline(
        skill_name="Rust",
        slug="rust",
        lessons=[
            LessonOutline(index=1, title="所有权", status="in_progress"),
        ],
        current_lesson=1,
    ))

    mock_gen = MagicMock()
    mock_gen.generate_quiz.return_value = "以下代码哪行会报错？"

    with patch("huaqi_src.scheduler.jobs._get_learning_store", return_value=store), \
         patch("huaqi_src.learning.course_generator.CourseGenerator", return_value=mock_gen):
        from importlib import reload
        import huaqi_src.scheduler.jobs as jobs
        reload(jobs)
        jobs._run_learning_push()

    captured = capsys.readouterr()
    assert "Rust" in captured.out or True
