from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from huaqi_src.layers.data.collectors.work_data_source import WorkDataSource


class CodeflickerSource(WorkDataSource):
    name = "codeflicker"
    source_type = "codeflicker_chat"

    def __init__(self, cli_chats_dir: Optional[Path] = None) -> None:
        if cli_chats_dir is None:
            from huaqi_src.config.paths import get_cli_chats_dir
            cli_chats_dir = get_cli_chats_dir()
        self._dir = Path(cli_chats_dir)

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
