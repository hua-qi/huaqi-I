from pathlib import Path
from huaqi_src.layers.data.collectors.cli_chat_parser import CLIChatMessage
from huaqi_src.layers.data.collectors.work_log_writer import WorkLogWriter


def _make_messages():
    return [
        CLIChatMessage(role="user", content="帮我设计 watchdog 监听方案"),
        CLIChatMessage(role="assistant", content="选择 on_created 事件，解决了 asyncio 线程安全问题"),
    ]


def test_write_creates_file_in_correct_directory(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    messages = _make_messages()
    file_path = writer.write(
        messages=messages,
        thread_id="abc123",
        time_start="2026-05-04T10:00:00Z",
        time_end="2026-05-04T10:30:00Z",
    )

    assert file_path is not None
    assert file_path.exists()
    work_logs_dir = tmp_path / "work_logs" / "2026-05"
    assert file_path.parent == work_logs_dir


def test_write_file_contains_yaml_frontmatter(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    messages = _make_messages()
    file_path = writer.write(
        messages=messages,
        thread_id="abc123",
        time_start="2026-05-04T10:00:00Z",
        time_end="2026-05-04T10:30:00Z",
    )

    content = file_path.read_text(encoding="utf-8")
    assert "---" in content
    assert "thread_id: abc123" in content
    assert "source: codeflicker" in content
    assert "time_start: 2026-05-04T10:00:00Z" in content
    assert "time_end: 2026-05-04T10:30:00Z" in content


def test_write_file_contains_summary_body(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    messages = _make_messages()
    file_path = writer.write(
        messages=messages,
        thread_id="abc123",
        time_start="2026-05-04T10:00:00Z",
        time_end="2026-05-04T10:30:00Z",
    )

    content = file_path.read_text(encoding="utf-8")
    assert len(content.split("---")) >= 3
    body = content.split("---", 2)[2].strip()
    assert len(body) > 0


def test_write_returns_none_for_empty_messages(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    result = writer.write(
        messages=[],
        thread_id="abc123",
        time_start="2026-05-04T10:00:00Z",
        time_end="2026-05-04T10:30:00Z",
    )
    assert result is None


def test_write_filename_contains_thread_id(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    messages = _make_messages()
    file_path = writer.write(
        messages=messages,
        thread_id="mythread42",
        time_start="2026-05-04T14:00:00Z",
        time_end="2026-05-04T14:30:00Z",
    )

    assert "mythread42" in file_path.name
