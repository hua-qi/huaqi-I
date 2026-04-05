with open("huaqi_src/layers/capabilities/reports/providers/diary.py", "w", encoding="utf-8") as f:
    f.write('import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.layers.capabilities.reports.providers import DataProvider, DateRange, register


class DiaryProvider(DataProvider):
    name = "diary"
    priority = 20
    supported_reports = ["*"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        diary_dir = self._data_dir / "memory" / "diary"
        if not diary_dir.exists():
            return None

        if report_type == "daily":
            month_str = date_range.end.strftime("%Y-%m")
            diary_file = diary_dir / month_str / f"{date_range.end.isoformat()}.md"
            if not diary_file.exists():
                diary_file = diary_dir / f"{date_range.end.isoformat()}.md"
            if not diary_file.exists():
                return None
            content = diary_file.read_text(encoding="utf-8")[:800]
            return f"## 今日日记\n{content}"

        snippets = []
        current = date_range.end
        while current >= date_range.start:
            month_str = current.strftime("%Y-%m")
            f = diary_dir / month_str / f"{current.isoformat()}.md"
            if not f.exists():
                f = diary_dir / f"{current.isoformat()}.md"
            
            if f.exists():
                content = f.read_text(encoding="utf-8")[:300]
                snippets.append(f"### {current.isoformat()}\n{content}")
            
            current -= datetime.timedelta(days=1)
            if len(snippets) >= 7:
                break

        if not snippets:
            return None
        label = "近期日记片段" if report_type == "morning" else "本周日记片段"
        return f"## {label}\n" + "\n\n".join(snippets)


try:
    from huaqi_src.config.paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(DiaryProvider(_data_dir))
except Exception:
    pass
')
