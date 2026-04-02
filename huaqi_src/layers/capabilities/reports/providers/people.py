from pathlib import Path
from typing import Optional

from huaqi_src.layers.capabilities.reports.providers import DataProvider, DateRange, register


class PeopleProvider(DataProvider):
    name = "people"
    priority = 40
    supported_reports = ["*"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        people_dir = self._data_dir / "people"
        if not people_dir.exists():
            return None

        from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph
        graph = PeopleGraph(data_dir=self._data_dir)
        people = graph.list_people()
        if not people:
            return None

        active = [p for p in people if p.interaction_frequency > 0]
        if not active:
            active = people

        active.sort(key=lambda p: p.interaction_frequency, reverse=True)

        if report_type == "morning":
            lines = ["## 近期活跃关系人"]
            for p in active[:3]:
                line = f"- {p.name}（{p.relation_type}）"
                if p.notes:
                    line += f"：{p.notes}"
                lines.append(line)
        elif report_type == "daily":
            lines = ["## 关系网络动态"]
            for p in active[:5]:
                lines.append(f"- {p.name}（{p.relation_type}）：近30天互动 {p.interaction_frequency} 次")
        elif report_type == "weekly":
            lines = ["## 关系人概览"]
            for p in active[:8]:
                line = f"- {p.name}（{p.relation_type}）"
                if p.profile:
                    line += f"：{p.profile[:50]}"
                lines.append(line)
        else:
            lines = ["## 关系人全貌"]
            for p in sorted(people, key=lambda x: x.interaction_frequency, reverse=True):
                line = f"- {p.name}（{p.relation_type}，{p.emotional_impact}影响）"
                if p.profile:
                    line += f"：{p.profile[:80]}"
                lines.append(line)

        return "\n".join(lines)


try:
    from huaqi_src.config.paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(PeopleProvider(_data_dir))
except Exception:
    pass
