import pytest
from datetime import datetime


def test_lesson_outline_to_dict():
    from huaqi_src.learning.models import LessonOutline
    lesson = LessonOutline(index=1, title="所有权（Ownership）")
    d = lesson.to_dict()
    assert d["index"] == 1
    assert d["title"] == "所有权（Ownership）"
    assert d["status"] == "pending"
    assert d["completed_at"] is None


def test_lesson_outline_from_dict():
    from huaqi_src.learning.models import LessonOutline
    d = {"index": 2, "title": "借用（Borrowing）", "status": "completed", "completed_at": "2026-03-31T10:00:00"}
    lesson = LessonOutline.from_dict(d)
    assert lesson.index == 2
    assert lesson.status == "completed"
    assert lesson.completed_at == "2026-03-31T10:00:00"


def test_course_outline_to_dict():
    from huaqi_src.learning.models import CourseOutline, LessonOutline
    course = CourseOutline(
        skill_name="Rust",
        slug="rust",
        lessons=[LessonOutline(index=1, title="所有权"), LessonOutline(index=2, title="借用")],
    )
    d = course.to_dict()
    assert d["skill_name"] == "Rust"
    assert d["slug"] == "rust"
    assert d["current_lesson"] == 1
    assert d["total_lessons"] == 2
    assert len(d["lessons"]) == 2


def test_course_outline_from_dict():
    from huaqi_src.learning.models import CourseOutline
    d = {
        "skill_name": "Python",
        "slug": "python",
        "created_at": "2026-03-31T00:00:00",
        "current_lesson": 2,
        "total_lessons": 3,
        "lessons": [
            {"index": 1, "title": "基础语法", "status": "completed", "completed_at": "2026-03-31T10:00:00"},
            {"index": 2, "title": "函数", "status": "in_progress", "completed_at": None},
            {"index": 3, "title": "类", "status": "pending", "completed_at": None},
        ],
    }
    course = CourseOutline.from_dict(d)
    assert course.skill_name == "Python"
    assert course.current_lesson == 2
    assert course.lessons[0].status == "completed"


def test_lesson_outline_has_lesson_type():
    from huaqi_src.learning.models import LessonOutline
    lesson = LessonOutline(index=1, title="所有权")
    assert lesson.lesson_type == "quiz"


def test_lesson_outline_lesson_type_serialization():
    from huaqi_src.learning.models import LessonOutline
    lesson = LessonOutline(index=1, title="项目实战", lesson_type="project")
    d = lesson.to_dict()
    assert d["lesson_type"] == "project"
    restored = LessonOutline.from_dict(d)
    assert restored.lesson_type == "project"


def test_lesson_outline_lesson_type_default_on_load():
    from huaqi_src.learning.models import LessonOutline
    lesson = LessonOutline.from_dict({"index": 1, "title": "基础语法"})
    assert lesson.lesson_type == "quiz"


def test_course_outline_current_lesson_property():
    from huaqi_src.learning.models import CourseOutline, LessonOutline
    course = CourseOutline(
        skill_name="Go",
        slug="go",
        lessons=[
            LessonOutline(index=1, title="入门", status="completed"),
            LessonOutline(index=2, title="并发", status="pending"),
        ],
    )
    assert course.current_lesson == 2
