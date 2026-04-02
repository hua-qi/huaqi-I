import json
from huaqi_src.layers.data.collectors.cli_chat_parser import parse_cli_chat_file


def test_parse_codeflicker_markdown(tmp_path):
    md_file = tmp_path / "session.md"
    md_file.write_text(
        "# 关于 Python 的讨论\n\n"
        "**User:** 如何使用 watchdog？\n\n"
        "**Assistant:** watchdog 是一个文件系统监听库。\n",
        encoding="utf-8",
    )
    messages = parse_cli_chat_file(md_file, tool_type="codeflicker")
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert "watchdog" in messages[0].content
    assert messages[1].role == "assistant"


def test_parse_claude_json(tmp_path):
    json_file = tmp_path / "session.json"
    data = {
        "messages": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮你的？"},
        ]
    }
    json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    messages = parse_cli_chat_file(json_file, tool_type="claude")
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "你好"


def test_parse_unknown_format_returns_empty(tmp_path):
    f = tmp_path / "session.xyz"
    f.write_text("some content")
    messages = parse_cli_chat_file(f, tool_type="custom")
    assert messages == []


def test_parse_markdown_skips_header_line(tmp_path):
    md_file = tmp_path / "session.md"
    md_file.write_text(
        "# 标题行应被跳过\n\n**User:** 问题\n\n**Assistant:** 答案\n",
        encoding="utf-8",
    )
    messages = parse_cli_chat_file(md_file, tool_type="codeflicker")
    assert len(messages) == 2
