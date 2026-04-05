from pathlib import Path
from typing import Optional

from huaqi_src.layers.capabilities.reports.providers import DataProvider, DateRange, register


class WorldProvider(DataProvider):
    name = "world"
    priority = 10
    supported_reports = ["morning", "daily"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        today = date_range.end.isoformat()
        world_file = self._data_dir / "world" / f"{today}.md"
        if not world_file.exists():
            world_file = self._lazy_fetch(today)
        if world_file is None or not world_file.exists():
            return None
        content = world_file.read_text(encoding="utf-8")[:1000]
        return f"## 今日世界热点\n{content}"

    def _lazy_fetch(self, date_str: str) -> "Optional[Path]":
        try:
            from huaqi_src.layers.data.world.pipeline import WorldPipeline
            import datetime
            pipeline = WorldPipeline(data_dir=self._data_dir)
            target_date = datetime.date.fromisoformat(date_str)
            success = pipeline.run(date=target_date)
            if not success:
                return None
            return self._data_dir / "world" / f"{date_str}.md"
        except Exception as e:
            print(f"[WorldProvider] lazy 补采失败: {e}")
            return None


try:
    from huaqi_src.config.paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(WorldProvider(_data_dir))
except Exception:
    pass
