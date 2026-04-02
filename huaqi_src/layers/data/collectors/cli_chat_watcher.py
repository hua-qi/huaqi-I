import datetime
import hashlib
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from huaqi_src.layers.data.collectors.cli_chat_parser import parse_cli_chat_file
from huaqi_src.layers.data.collectors.document import HuaqiDocument
from huaqi_src.config.manager import ConfigManager


class CLIChatWatcher:
    def __init__(
        self,
        watch_paths: Optional[list[dict]] = None,
        data_dir: Optional[Path] = None,
    ):
        if data_dir is None:
            from huaqi_src.config.paths import require_data_dir
            data_dir = require_data_dir()
        self._data_dir = Path(data_dir)
        self._watch_paths = watch_paths or self._load_watch_paths_from_config()
        self._observer: Optional[Observer] = None
        self._config = ConfigManager(self._data_dir)

    def _load_watch_paths_from_config(self) -> list[dict]:
        return []

    def is_enabled(self) -> bool:
        return self._config.is_enabled("cli_chat")

    def process_file(self, file_path: Path, tool_type: str) -> list[HuaqiDocument]:
        messages = parse_cli_chat_file(file_path, tool_type=tool_type)
        if not messages:
            return []

        content_lines = [
            f"[{m.role}]: {m.content}" for m in messages
        ]
        content = "\n".join(content_lines)

        now = datetime.datetime.now()
        month_key = now.strftime("%Y-%m")
        out_dir = self._data_dir / "memory" / "cli_chats" / month_key
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / f"{tool_type}-{file_path.stem}.md"
        header = f"# {tool_type} 对话记录: {file_path.name}\n\n"
        out_file.write_text(header + content + "\n", encoding="utf-8")

        doc_id = hashlib.md5(f"cli_chat:{tool_type}:{file_path.name}:{len(messages)}".encode()).hexdigest()[:12]
        return [
            HuaqiDocument(
                doc_id=doc_id,
                doc_type="cli_chat",
                source=f"cli_chat:{tool_type}:{file_path.name}",
                content=content,
                timestamp=now,
                metadata={"tool_type": tool_type, "file": str(file_path)},
            )
        ]

    def sync_all(self) -> list[HuaqiDocument]:
        all_docs = []
        for watch_cfg in self._watch_paths:
            tool_type = watch_cfg.get("type", "custom")
            path = Path(watch_cfg.get("path", "")).expanduser()
            if not path.exists():
                continue
            for f in sorted(path.rglob("*.md")) + sorted(path.rglob("*.json")):
                docs = self.process_file(f, tool_type=tool_type)
                all_docs.extend(docs)
        return all_docs

    def start(self):
        if not self.is_enabled():
            return
        self.sync_all()
        self._observer = Observer()
        for watch_cfg in self._watch_paths:
            tool_type = watch_cfg.get("type", "custom")
            path = Path(watch_cfg.get("path", "")).expanduser()
            if not path.exists():
                continue
            handler = _FileChangeHandler(self, tool_type=tool_type)
            self._observer.schedule(handler, str(path), recursive=True)
        self._observer.start()

    def stop(self):
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()


class _FileChangeHandler(FileSystemEventHandler):
    def __init__(self, watcher: CLIChatWatcher, tool_type: str):
        self._watcher = watcher
        self._tool_type = tool_type

    def on_created(self, event: FileCreatedEvent):
        if not event.is_directory:
            self._watcher.process_file(Path(event.src_path), self._tool_type)

    def on_modified(self, event: FileModifiedEvent):
        if not event.is_directory:
            self._watcher.process_file(Path(event.src_path), self._tool_type)
