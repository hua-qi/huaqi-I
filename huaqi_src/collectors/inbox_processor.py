import datetime
import hashlib
import shutil
from pathlib import Path
from typing import Optional

from .document import HuaqiDocument

SUPPORTED_EXTENSIONS = {".md", ".txt"}


class InboxProcessor:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self.data_dir = Path(data_dir)
            self.inbox_dir = self.data_dir / "inbox" / "work_docs"
            self.archive_dir = self.data_dir / "memory" / "work_docs"
        else:
            from huaqi_src.core.config_paths import require_data_dir, get_inbox_work_docs_dir, get_work_docs_dir
            self.data_dir = require_data_dir()
            self.inbox_dir = get_inbox_work_docs_dir()
            self.archive_dir = get_work_docs_dir()

    def sync(self) -> list[HuaqiDocument]:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        docs = []
        for file_path in sorted(self.inbox_dir.iterdir()):
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            doc = self._process_file(file_path)
            if doc:
                docs.append(doc)
                self._archive(file_path)
        return docs

    def _process_file(self, file_path: Path) -> Optional[HuaqiDocument]:
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return None

        doc_id = hashlib.md5(f"{file_path.name}{content[:50]}".encode()).hexdigest()[:12]
        return HuaqiDocument(
            doc_id=doc_id,
            doc_type="work_doc",
            source=f"file:{file_path}",
            content=content,
            timestamp=datetime.datetime.now(),
        )

    def _archive(self, file_path: Path):
        dest = self.archive_dir / file_path.name
        if dest.exists():
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            dest = self.archive_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"
        shutil.move(str(file_path), str(dest))
