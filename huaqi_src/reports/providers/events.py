import sqlite3
import time
from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class EventsProvider(DataProvider):
    name = "events"
    priority = 60
    supported_reports = ["daily", "weekly"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        db_path = self._data_dir / "events.db"
        if not db_path.exists():
            return None

        import datetime as dt
        start_ts = int(dt.datetime.combine(date_range.start, dt.time.min).timestamp())
        end_ts = int(dt.datetime.combine(date_range.end, dt.time.max).timestamp())

        try:
            conn = sqlite3.connect(str(db_path))
            rows = conn.execute(
                "SELECT source, actor, content, timestamp FROM events "
                "WHERE timestamp >= ? AND timestamp <= ? "
                "ORDER BY timestamp DESC LIMIT 20",
                (start_ts, end_ts),
            ).fetchall()
            conn.close()
        except Exception:
            return None

        if not rows:
            return None

        lines = ["## 近期事件流"]
        for row in rows:
            source, actor, content, ts = row
            import datetime as dt2
            date_str = dt2.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
            lines.append(f"- [{date_str}] {source}/{actor}：{(content or '')[:100]}")

        return "\n".join(lines)


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(EventsProvider(_data_dir))
except Exception:
    pass
