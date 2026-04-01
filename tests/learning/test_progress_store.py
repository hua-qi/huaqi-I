import pytest
from pathlib import Path
from datetime import datetime


def test_create_course(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore
    from huaqi_src.learning.models import CourseOutline, LessonOutline

    store = LearningProgressStore(tmp_path)
    course = CourseOutline(
        skill_name="Rust",
        slug="rust",
        lessons=[LessonOutline(index=1, title="所有权"), LessonOutline(index=2, title="借用")],
    )
    store.save_course(course)

    outline_path = tmp_path / "courses" / "rust" / "outline.yaml"
    assert outline_path.exists()


def test_load_course(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore
    from huaqi_src.learning.models import CourseOutline, LessonOutline

    store = LearningProgressStore(tmp_path)
    course = CourseOutline(
        skill_name="Python",
        slug="python",
        lessons=[LessonOutline(index=1, title="基础")],
    )
    store.save_course(course)

    loaded = store.load_course("python")
    assert loaded is not None
    assert loaded.skill_name == "Python"
    assert len(loaded.lessons) == 1


def test_load_course_returns_none_when_not_exists(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore

    store = LearningProgressStore(tmp_path)
    result = store.load_course("nonexistent-skill")
    assert result is None


def test_list_courses(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore
    from huaqi_src.learning.models import CourseOutline, LessonOutline

    store = LearningProgressStore(tmp_path)
    for skill in ["rust", "python"]:
        store.save_course(CourseOutline(skill_name=skill.capitalize(), slug=skill, lessons=[]))

    courses = store.list_courses()
    assert len(courses) == 2
    slugs = [c.slug for c in courses]
    assert "rust" in slugs
    assert "python" in slugs


def test_mark_lesson_complete(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore
    from huaqi_src.learning.models import CourseOutline, LessonOutline

    store = LearningProgressStore(tmp_path)
    course = CourseOutline(
        skill_name="Go",
        slug="go",
        lessons=[
            LessonOutline(index=1, title="入门"),
            LessonOutline(index=2, title="并发"),
        ],
    )
    store.save_course(course)
    store.mark_lesson_complete("go", lesson_index=1)

    loaded = store.load_course("go")
    assert loaded.lessons[0].status == "completed"
    assert loaded.lessons[0].completed_at is not None
    assert loaded.current_lesson == 2


def test_save_session_markdown(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore

    store = LearningProgressStore(tmp_path)
    store.save_session(
        skill_slug="rust",
        lesson_index=1,
        lesson_title="所有权",
        content="所有权是 Rust 的核心概念...",
        quiz="以下哪段代码会报编译错误？",
        user_answer="选项 A",
        feedback="正确！",
        timestamp=datetime(2026, 3, 31, 21, 0, 0),
    )

    session_path = tmp_path / "sessions" / "20260331_rust.md"
    assert session_path.exists()
    content = session_path.read_text(encoding="utf-8")
    assert "所有权" in content
    assert "选项 A" in content


def test_slugify():
    from huaqi_src.learning.progress_store import slugify

    assert slugify("Rust") == "rust"
    assert slugify("Python 3") == "python-3"
    assert slugify("C++") == "c"
    assert slugify("  Golang  ") == "golang"
