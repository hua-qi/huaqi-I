import pytest
from unittest.mock import patch, MagicMock
import os


def _mock_store_with_course(tmp_path):
    from huaqi_src.layers.capabilities.learning.models import CourseOutline, LessonOutline
    from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore

    store = LearningProgressStore(tmp_path / "learning")
    course = CourseOutline(
        skill_name="Rust",
        slug="rust",
        lessons=[
            LessonOutline(index=1, title="所有权", status="completed"),
            LessonOutline(index=2, title="借用", status="in_progress"),
            LessonOutline(index=3, title="生命周期", status="pending"),
        ],
        current_lesson=2,
    )
    store.save_course(course)
    return store


def test_get_learning_progress_tool_returns_string(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.config import paths as config_paths
    config_paths._USER_DATA_DIR = tmp_path

    store = _mock_store_with_course(tmp_path)

    from importlib import reload
    import huaqi_src.layers.capabilities.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.layers.capabilities.learning.learning_tools._get_store", return_value=store):
        result = lt.get_learning_progress_tool.invoke({"skill": "Rust"})

    assert isinstance(result, str)
    assert "Rust" in result or "rust" in result


def test_get_learning_progress_tool_no_course(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.config import paths as config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore
    store = LearningProgressStore(tmp_path / "learning")

    from importlib import reload
    import huaqi_src.layers.capabilities.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.layers.capabilities.learning.learning_tools._get_store", return_value=store):
        result = lt.get_learning_progress_tool.invoke({"skill": "Go"})

    assert isinstance(result, str)
    assert "未找到" in result or "尚未" in result


def test_start_lesson_tool_saves_lesson_type(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.config import paths as config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore
    store = LearningProgressStore(tmp_path / "learning")

    mock_gen = MagicMock()
    mock_gen.generate_outline_with_types.return_value = [
        ("环境安装", "project"),
        ("变量类型", "quiz"),
        ("代码练习", "coding"),
    ]
    mock_gen.generate_lesson.return_value = "讲解内容"
    mock_gen.generate_quiz.return_value = "考题"

    from importlib import reload
    import huaqi_src.layers.capabilities.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.layers.capabilities.learning.learning_tools._get_store", return_value=store), \
         patch("huaqi_src.layers.capabilities.learning.learning_tools.CourseGenerator", return_value=mock_gen):
        lt.start_lesson_tool.invoke({"skill": "Python"})

    course = store.load_course("python")
    assert course.lessons[0].lesson_type == "project"
    assert course.lessons[1].lesson_type == "quiz"
    assert course.lessons[2].lesson_type == "coding"


def test_get_course_outline_tool_returns_chapters(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.config import paths as config_paths
    config_paths._USER_DATA_DIR = tmp_path

    store = _mock_store_with_course(tmp_path)

    from importlib import reload
    import huaqi_src.layers.capabilities.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.layers.capabilities.learning.learning_tools._get_store", return_value=store):
        result = lt.get_course_outline_tool.invoke({"skill": "Rust"})

    assert isinstance(result, str)
    assert "所有权" in result
    assert "借用" in result


def test_mark_lesson_complete_tool_advances_to_next(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.config import paths as config_paths
    config_paths._USER_DATA_DIR = tmp_path

    store = _mock_store_with_course(tmp_path)

    from importlib import reload
    import huaqi_src.layers.capabilities.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.layers.capabilities.learning.learning_tools._get_store", return_value=store):
        result = lt.mark_lesson_complete_tool.invoke({"skill": "Rust"})

    assert isinstance(result, str)
    assert "完成" in result or "第" in result
    course = store.load_course("rust")
    assert course.lessons[1].status == "completed"


def test_mark_lesson_complete_tool_all_done(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.config import paths as config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.layers.capabilities.learning.models import CourseOutline, LessonOutline
    from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore

    store = LearningProgressStore(tmp_path / "learning")
    course = CourseOutline(
        skill_name="Go",
        slug="go",
        lessons=[
            LessonOutline(index=1, title="基础语法", status="in_progress"),
        ],
        current_lesson=1,
    )
    store.save_course(course)

    from importlib import reload
    import huaqi_src.layers.capabilities.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.layers.capabilities.learning.learning_tools._get_store", return_value=store):
        result = lt.mark_lesson_complete_tool.invoke({"skill": "Go"})

    assert "完成" in result or "恭喜" in result


def test_mark_lesson_complete_tool_no_course(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.config import paths as config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore
    store = LearningProgressStore(tmp_path / "learning")

    from importlib import reload
    import huaqi_src.layers.capabilities.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.layers.capabilities.learning.learning_tools._get_store", return_value=store):
        result = lt.mark_lesson_complete_tool.invoke({"skill": "Rust"})

    assert "未找到" in result or "尚未" in result
