from pathlib import Path
from typing import Optional

from huaqi_src.layers.capabilities.reports.providers import DataProvider, DateRange, register


class WeeklyReportsProvider(DataProvider):
    name = "weekly_reports"
    priority = 70
    supported_reports = ["quarterly"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        weekly_dir = self._data_dir / "reports" / "weekly"
        if not weekly_dir.exists():
            return None

        weekly_files = sorted(weekly_dir.glob("*.md"), reverse=True)[:13]
        if not weekly_files:
            return None

        snippets = []
        for f in weekly_files:
            snippets.append(f"### {f.stem}\n{f.read_text(encoding='utf-8')[:200]}")

        return "## 本季度周报摘要\n" + "\n\n".join(snippets)


try:
    from huaqi_src.config.paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(WeeklyReportsProvider(_data_dir))
except Exception:
    pass
