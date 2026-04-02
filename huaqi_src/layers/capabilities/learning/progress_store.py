import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from .models import CourseOutline, LessonOutline


def slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name


class LearningProgressStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.courses_dir = self.base_dir / "courses"
        self.sessions_dir = self.base_dir / "sessions"

    def _course_dir(self, slug: str) -> Path:
        return self.courses_dir / slug

    def _outline_path(self, slug: str) -> Path:
        return self._course_dir(slug) / "outline.yaml"

    def save_course(self, course: CourseOutline) -> None:
        course_dir = self._course_dir(course.slug)
        course_dir.mkdir(parents=True, exist_ok=True)
        (course_dir / "lessons").mkdir(exist_ok=True)
        with open(self._outline_path(course.slug), "w", encoding="utf-8") as f:
            yaml.dump(course.to_dict(), f, allow_unicode=True, default_flow_style=False)

    def load_course(self, slug: str) -> Optional[CourseOutline]:
        path = self._outline_path(slug)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return CourseOutline.from_dict(data)

    def list_courses(self) -> List[CourseOutline]:
        if not self.courses_dir.exists():
            return []
        result = []
        for slug_dir in sorted(self.courses_dir.iterdir()):
            if slug_dir.is_dir():
                course = self.load_course(slug_dir.name)
                if course:
                    result.append(course)
        return result

    def mark_lesson_complete(self, slug: str, lesson_index: int) -> None:
        course = self.load_course(slug)
        if course is None:
            return
        for lesson in course.lessons:
            if lesson.index == lesson_index:
                lesson.status = "completed"
                lesson.completed_at = datetime.now().isoformat()
                break
        next_lesson = lesson_index + 1
        for lesson in course.lessons:
            if lesson.index == next_lesson:
                course.current_lesson = next_lesson
                break
        self.save_course(course)

    def save_session(
        self,
        skill_slug: str,
        lesson_index: int,
        lesson_title: str,
        content: str,
        quiz: str,
        user_answer: str,
        feedback: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        if timestamp is None:
            timestamp = datetime.now()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        date_str = timestamp.strftime("%Y%m%d")
        session_path = self.sessions_dir / f"{date_str}_{skill_slug}.md"
        lines = [
            f"# 学习会话：{skill_slug} - 第{lesson_index}章 {lesson_title}",
            f"",
            f"**时间：** {timestamp.strftime('%Y-%m-%d %H:%M')}",
            f"",
            f"## 讲解内容",
            f"",
            content,
            f"",
            f"## 考题",
            f"",
            quiz,
            f"",
            f"## 你的回答",
            f"",
            user_answer,
            f"",
            f"## 反馈",
            f"",
            feedback,
        ]
        with open(session_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n\n---\n\n")
