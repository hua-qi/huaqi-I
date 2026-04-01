from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class GrowthProvider(DataProvider):
    name = "growth"
    priority = 50
    supported_reports = ["weekly", "quarterly"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        growth_file = self._data_dir / "memory" / "growth.yaml"
        if not growth_file.exists():
            return None

        import yaml
        with open(growth_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return None

        lines = ["## 成长目标与技能"]
        goals = data.get("goals", [])
        if goals:
            lines.append("### 目标")
            for g in goals:
                title = g.get("title", "")
                status = g.get("status", "")
                progress = g.get("progress", "")
                line = f"- {title}（{status}）"
                if progress:
                    line += f" {progress}"
                lines.append(line)

        skills = data.get("skills", [])
        if skills:
            lines.append("### 技能")
            for s in skills:
                lines.append(f"- {s.get('name', '')}：{s.get('level', '')}")

        return "\n".join(lines)


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(GrowthProvider(_data_dir))
except Exception:
    pass
