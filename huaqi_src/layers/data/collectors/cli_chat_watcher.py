import datetime
import hashlib
import time
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from huaqi_src.layers.data.collectors.cli_chat_parser import (
    parse_cli_chat_session,
    CLIChatSession,
)
from huaqi_src.layers.data.collectors.document import HuaqiDocument
from huaqi_src.config.manager import ConfigManager

_SYNC_MAX_FILE_BYTES = 1 * 1024 * 1024
_SYNC_MAX_DAYS = 30


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
        paths = []
        codeflicker_projects = Path("~/.codeflicker/projects").expanduser()
        if codeflicker_projects.exists():
            for project_dir in codeflicker_projects.iterdir():
                if project_dir.is_dir():
                    paths.append({"type": "codeflicker", "path": str(project_dir)})
        return paths

    def is_enabled(self) -> bool:
        return self._config.is_enabled("cli_chat")

    def process_file(self, file_path: Path, tool_type: str) -> list[HuaqiDocument]:
        session = parse_cli_chat_session(file_path, tool_type=tool_type)
        if session is None or not session.messages:
            return []

        if tool_type == "codeflicker":
            return self._process_codeflicker_session(session, file_path)

        content_lines = [f"[{m.role}]: {m.content}" for m in session.messages]
        content = "\n".join(content_lines)
        now = datetime.datetime.now()
        month_key = now.strftime("%Y-%m")
        out_dir = self._data_dir / "memory" / "cli_chats" / month_key
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{tool_type}-{file_path.stem}.md"
        out_file.write_text(f"# {tool_type} 对话记录: {file_path.name}\n\n{content}\n", encoding="utf-8")
        doc_id = hashlib.md5(f"cli_chat:{tool_type}:{file_path.name}:{len(session.messages)}".encode()).hexdigest()[:12]
        return [HuaqiDocument(
            doc_id=doc_id,
            doc_type="cli_chat",
            source=f"cli_chat:{tool_type}:{file_path.name}",
            content=content,
            timestamp=now,
            metadata={"tool_type": tool_type, "file": str(file_path)},
        )]

    def _process_codeflicker_session(
        self, session: CLIChatSession, file_path: Path
    ) -> list[HuaqiDocument]:
        date_str = _date_from_iso(session.time_start) if session.time_start else \
            datetime.datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d")

        year, month, day = date_str[:4], date_str[5:7], date_str[8:10]
        out_dir = self._data_dir / "memory" / "cli_chats" / "codeflicker" / year / month / day
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{session.session_id}.md"

        frontmatter = (
            f"---\n"
            f"session_id: {session.session_id}\n"
            f"date: {date_str}\n"
            f"time_start: {session.time_start or ''}\n"
            f"time_end: {session.time_end or ''}\n"
            f"project: {Path(session.project_dir).name if session.project_dir else ''}\n"
            f"git_branch: {session.git_branch or ''}\n"
            f"---\n\n"
        )

        content_lines = []
        for m in session.messages:
            prefix = f"[{_format_ts(m.timestamp)}] " if m.timestamp else ""
            content_lines.append(f"{prefix}[{m.role}]: {m.content}")
        content = "\n".join(content_lines)

        out_file.write_text(frontmatter + content + "\n", encoding="utf-8")

        if session.time_start:
            from huaqi_src.layers.data.collectors.work_log_writer import WorkLogWriter
            WorkLogWriter(data_dir=self._data_dir).write(
                messages=session.messages,
                thread_id=session.session_id,
                time_start=session.time_start,
                time_end=session.time_end or session.time_start,
            )
        else:
            import datetime as _dt
            from huaqi_src.layers.data.collectors.work_log_writer import WorkLogWriter
            now_iso = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            WorkLogWriter(data_dir=self._data_dir).write(
                messages=session.messages,
                thread_id=session.session_id,
                time_start=now_iso,
                time_end=now_iso,
            )

        doc_id = hashlib.md5(
            f"codeflicker:{session.session_id}:{date_str}".encode()
        ).hexdigest()[:12]

        full_content = frontmatter + content
        return [HuaqiDocument(
            doc_id=doc_id,
            doc_type="cli_chat",
            source=f"codeflicker:{session.session_id}:{date_str}",
            content=full_content,
            timestamp=datetime.datetime.now(),
            metadata={
                "tool_type": "codeflicker",
                "session_id": session.session_id,
                "date": date_str,
                "git_branch": session.git_branch or "",
                "project": Path(session.project_dir).name if session.project_dir else "",
                "file": str(file_path),
            },
        )]

    def sync_all(self) -> list[HuaqiDocument]:
        all_docs = []
        cutoff = time.time() - _SYNC_MAX_DAYS * 86400
        for watch_cfg in self._watch_paths:
            tool_type = watch_cfg.get("type", "custom")
            path = Path(watch_cfg.get("path", "")).expanduser()
            if not path.exists():
                continue
            files = (
                list(path.glob("*.md"))
                + list(path.glob("*.json"))
                + list(path.glob("*.jsonl"))
            )
            for f in files:
                try:
                    stat = f.stat()
                    if stat.st_mtime < cutoff:
                        continue
                    if stat.st_size > _SYNC_MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
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


def _date_from_iso(ts: str) -> str:
    return ts[:10]


def _format_ts(ts: Optional[str]) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts[:19]


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
