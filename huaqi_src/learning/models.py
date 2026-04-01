from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class LessonOutline:
    index: int
    title: str
    status: str = "pending"
    completed_at: Optional[str] = None
    lesson_type: str = "quiz"

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "title": self.title,
            "status": self.status,
            "completed_at": self.completed_at,
            "lesson_type": self.lesson_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LessonOutline":
        return cls(
            index=d["index"],
            title=d["title"],
            status=d.get("status", "pending"),
            completed_at=d.get("completed_at"),
            lesson_type=d.get("lesson_type", "quiz"),
        )


@dataclass
class CourseOutline:
    skill_name: str
    slug: str
    lessons: List[LessonOutline] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    current_lesson: int = 1

    def __post_init__(self):
        if self.lessons:
            for lesson in self.lessons:
                if lesson.status in ("pending", "in_progress"):
                    self.current_lesson = lesson.index
                    break

    @property
    def total_lessons(self) -> int:
        return len(self.lessons)

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "slug": self.slug,
            "created_at": self.created_at,
            "current_lesson": self.current_lesson,
            "total_lessons": self.total_lessons,
            "lessons": [l.to_dict() for l in self.lessons],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CourseOutline":
        lessons = [LessonOutline.from_dict(l) for l in d.get("lessons", [])]
        obj = cls(
            skill_name=d["skill_name"],
            slug=d["slug"],
            lessons=lessons,
            created_at=d.get("created_at", datetime.now().isoformat()),
            current_lesson=d.get("current_lesson", 1),
        )
        obj.current_lesson = d.get("current_lesson", 1)
        return obj
