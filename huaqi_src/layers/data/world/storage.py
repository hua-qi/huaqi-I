import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.layers.data.collectors.document import HuaqiDocument


class WorldNewsStorage:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self.world_dir = Path(data_dir) / "world"
        else:
            from huaqi_src.config.paths import get_world_dir
            self.world_dir = get_world_dir()
        self.world_dir.mkdir(parents=True, exist_ok=True)

    def save(self, docs: list[HuaqiDocument], date: Optional[datetime.date] = None):
        if not docs:
            return
        if date is None:
            date = datetime.date.today()
        file_path = self.world_dir / f"{date.isoformat()}.md"
        lines = [f"# 世界感知摘要 {date.isoformat()}\n"]
        for doc in docs:
            lines.append(f"## {doc.metadata.get('feed_name', doc.source)}\n")
            lines.append(f"{doc.content}\n")
            lines.append("---\n")
        file_path.write_text("\n".join(lines), encoding="utf-8")

    def search(self, query: str, days: int = 7) -> list[str]:
        query_lower = query.lower()
        results = []
        for md_file in sorted(self.world_dir.glob("*.md"), reverse=True)[:days]:
            content = md_file.read_text(encoding="utf-8")
            for section in content.split("---"):
                if query_lower in section.lower():
                    results.append(section.strip())
        return results
