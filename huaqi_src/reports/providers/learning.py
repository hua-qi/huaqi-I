import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class LearningProvider(DataProvider):
    name = "learning"
    priority = 30
    supported_reports = ["daily", "weekly", "quarterly"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        learning_dir = self._data_dir / "learning"
        if not learning_dir.exists():
            return None

        from huaqi_src.learning.progress_store import LearningProgressStore
        store = LearningProgressStore(base_dir=learning_dir)
        courses = store.list_courses()
        if not courses:
            return None

        lines = ["## 学习进度"]
        for course in courses:
            completed = sum(1 for l in course.lessons if l.status == "completed")
            total = course.total_lessons
            current_lesson = next(
                (l for l in course.lessons if l.index == course.current_lesson), None
            )
            current_title = current_lesson.title if current_lesson else "—"
            lines.append(
                f"- **{course.skill_name}**：{completed}/{total} 章完成，当前：{current_title}"
            )

        sessions_dir = learning_dir / "sessions"
        if sessions_dir.exists() and report_type in ("daily", "weekly"):
            recent_sessions = []
            current = date_range.end
            while current >= date_range.start:
                date_str = current.strftime("%Y%m%d")
                for f in sessions_dir.glob(f"{date_str}_*.md"):
                    recent_sessions.append(f.read_text(encoding="utf-8")[:200])
                current -= datetime.timedelta(days=1)
            if recent_sessions:
                lines.append("\n## 近期学习记录")
                lines.extend(recent_sessions[:3])

        return "\n".join(lines)


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(LearningProvider(_data_dir))
except Exception:
    pass
