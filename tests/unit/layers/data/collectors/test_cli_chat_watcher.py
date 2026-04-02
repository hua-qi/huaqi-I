from pathlib import Path
from huaqi_src.layers.data.collectors.cli_chat_watcher import CLIChatWatcher


def _make_md_session(path: Path, content: str = "**User:** 问题\n\n**Assistant:** 答案\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_process_file_creates_markdown_doc(tmp_path):
    conv_dir = tmp_path / "conversations"
    md_file = conv_dir / "session_001.md"
    _make_md_session(md_file)

    watch_paths = [{"type": "codeflicker", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    docs = watcher.process_file(md_file, tool_type="codeflicker")

    assert len(docs) == 1
    assert docs[0].doc_type == "cli_chat"
    assert docs[0].source.startswith("cli_chat:codeflicker:")


def test_process_file_writes_to_memory_dir(tmp_path):
    conv_dir = tmp_path / "conversations"
    md_file = conv_dir / "session_001.md"
    _make_md_session(md_file)

    watch_paths = [{"type": "codeflicker", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    watcher.process_file(md_file, tool_type="codeflicker")

    cli_chats_dir = tmp_path / "memory" / "cli_chats"
    md_files = list(cli_chats_dir.rglob("*.md"))
    assert len(md_files) == 1


def test_process_file_with_empty_messages_returns_empty(tmp_path):
    conv_dir = tmp_path / "conversations"
    md_file = conv_dir / "empty.md"
    _make_md_session(md_file, content="# 空文件\n\n没有对话内容\n")

    watch_paths = [{"type": "codeflicker", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    docs = watcher.process_file(md_file, tool_type="codeflicker")
    assert docs == []


def test_sync_all_processes_existing_files(tmp_path):
    conv_dir = tmp_path / "conversations"
    for i in range(3):
        _make_md_session(conv_dir / f"session_{i:03d}.md")

    watch_paths = [{"type": "codeflicker", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    docs = watcher.sync_all()
    assert len(docs) == 3
