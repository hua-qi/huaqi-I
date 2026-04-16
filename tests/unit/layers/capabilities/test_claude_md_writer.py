from pathlib import Path
from unittest.mock import MagicMock
from huaqi_src.layers.capabilities.codeflicker.claude_md_writer import CLAUDEmdWriter


def _make_writer(tmp_path: Path) -> CLAUDEmdWriter:
    mock_mgr = MagicMock()
    mock_mgr.get_dimension_snippet.side_effect = lambda name: f"内容:{name}"
    agents_md = tmp_path / "AGENTS.md"
    return CLAUDEmdWriter(telos_manager=mock_mgr, agents_md_path=agents_md)


def test_sync_creates_file_if_not_exists(tmp_path):
    writer = _make_writer(tmp_path)
    writer.sync()
    agents_md = tmp_path / "AGENTS.md"
    assert agents_md.exists()
    assert "## My Work Style" in agents_md.read_text()


def test_sync_updates_existing_section(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "# 用户自定义规则\n\n旧规则内容\n\n## My Work Style\n\n旧风格\n\n## 其他段落\n\n保留内容\n"
    )
    writer = _make_writer(tmp_path)
    writer.sync()
    content = agents_md.read_text()
    assert "旧风格" not in content
    assert "内容:work_style" in content
    assert "保留内容" in content
    assert "旧规则内容" in content


def test_sync_preserves_other_content(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# 自定义\n\n我的规则\n")
    writer = _make_writer(tmp_path)
    writer.sync()
    content = agents_md.read_text()
    assert "我的规则" in content
    assert "## My Work Style" in content
