import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.layers.capabilities.reports.providers import DataProvider, DateRange, register


class WorkLogProvider(DataProvider):
    name = "work_log"
    priority = 25
    supported_reports = ["daily"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        target_date = date_range.end
        month_key = target_date.strftime("%Y-%m")
        date_prefix = target_date.strftime("%Y%m%d")

        work_logs_dir = self._data_dir / "work_logs" / month_key
        if not work_logs_dir.exists():
            return None

        session_files = sorted(work_logs_dir.glob(f"{date_prefix}_*.md"))
        if not session_files:
            return None

        snippets = []
        for f in session_files:
            raw = f.read_text(encoding="utf-8")
            parts = raw.split("---", 2)
            if len(parts) < 3:
                continue
            frontmatter = parts[1]
            body = parts[2].strip()

            time_start = ""
            time_end = ""
            for line in frontmatter.splitlines():
                if line.startswith("time_start:"):
                    time_start = line.split(":", 1)[1].strip()
                elif line.startswith("time_end:"):
                    time_end = line.split(":", 1)[1].strip()

            time_label = ""
            if time_start and time_end:
                start_hm = time_start[11:16] if len(time_start) >= 16 else time_start
                end_hm = time_end[11:16] if len(time_end) >= 16 else time_end
                time_label = f"### {start_hm}–{end_hm}\n"

            snippets.append(time_label + body)

        if not snippets:
            return None

        return "## 今日编程工作（来自 codeflicker）\n\n" + "\n\n".join(snippets)


try:
    from huaqi_src.config.paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(WorkLogProvider(_data_dir))
except Exception:
    pass
