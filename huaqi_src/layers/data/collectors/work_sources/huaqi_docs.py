from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from huaqi_src.layers.data.collectors.work_data_source import WorkDataSource


class HuaqiDocsSource(WorkDataSource):
    name = "huaqi_docs"
    source_type = "huaqi_docs"

    def __init__(self, docs_dir: Optional[Path] = None) -> None:
        if docs_dir is None:
            docs_dir = Path(__file__).parents[5] / "docs"
        self._dir = Path(docs_dir)

    def fetch_documents(self, since: Optional[datetime] = None) -> List[str]:
        if not self._dir.exists():
            return []
        since_utc = since.astimezone(timezone.utc) if since is not None else None
        docs = []
        for f in sorted(self._dir.rglob("*.md")):
            if since_utc is not None:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime <= since_utc:
                    continue
            try:
                docs.append(f.read_text(encoding="utf-8"))
            except OSError:
                pass
        return docs
