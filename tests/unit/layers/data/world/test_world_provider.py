import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
from huaqi_src.layers.capabilities.reports.providers import DateRange


def _make_date_range(date_str: str):
    d = datetime.date.fromisoformat(date_str)
    return DateRange(start=d, end=d)


def test_world_provider_returns_content_when_file_exists(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "2026-05-04.md").write_text("# 世界新闻\n测试内容", encoding="utf-8")

    provider = WorldProvider(data_dir=tmp_path)
    result = provider.get_context("morning", _make_date_range("2026-05-04"))

    assert result is not None
    assert "世界热点" in result or "世界新闻" in result or "测试内容" in result


def test_world_provider_triggers_lazy_fetch_when_file_missing(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = True
        (tmp_path / "world").mkdir()
        (tmp_path / "world" / "2026-05-04.md").write_text("lazy 采集内容", encoding="utf-8")

        provider = WorldProvider(data_dir=tmp_path)

        world_file = tmp_path / "world" / "2026-05-04.md"
        world_file.unlink()

        def fake_run(**kwargs):
            world_file.write_text("lazy 采集内容", encoding="utf-8")
            return True

        MockPipeline.return_value.run.side_effect = fake_run
        result = provider.get_context("morning", _make_date_range("2026-05-04"))

        MockPipeline.return_value.run.assert_called_once()
        assert result is not None


def test_world_provider_returns_none_when_lazy_fetch_fails(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = False

        provider = WorldProvider(data_dir=tmp_path)
        result = provider.get_context("morning", _make_date_range("2026-05-04"))

        assert result is None


def test_world_provider_returns_none_when_lazy_fetch_raises(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.side_effect = RuntimeError("网络错误")

        provider = WorldProvider(data_dir=tmp_path)
        result = provider.get_context("morning", _make_date_range("2026-05-04"))

        assert result is None


def test_prioritizes_suggestions_section(tmp_path):
    """提取「今日精选」板块的标题和选择理由，不含其他内容。"""
    content = (
        "# 世界感知摘要 2026-05-15\n\n"
        + ("x" * 2000) + "\n\n"
        "## 领域粗筛结果\n\n"
        "AI/科技 2 篇，其余 0 篇。\n\n"
        "## 今日精选（3 篇）\n\n"
        "### 精选 1：OpenAI 发布新模型\n\n"
        "**来源**：BBC科技\n"
        "**领域**：AI/科技\n"
        "**链接**：https://example.com\n"
        "**英文原标题**：OpenAI Announces New Model\n\n"
        "**为什么选这篇**：与你目前的 AI 工程师工作直接相关\n\n"
        "OpenAI 今日发布了新模型，性能大幅提升。\n\n"
        "---\n\n"
        "不应该出现的无关内容"
    )
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "2026-05-15.md").write_text(content, encoding="utf-8")

    provider = WorldProvider(data_dir=tmp_path)
    result = provider.get_context("morning", _make_date_range("2026-05-15"))
    assert result is not None
    assert "OpenAI" in result
    assert "与你目前的 AI 工程师工作直接相关" in result
    assert "不应该出现的无关内容" not in result


def test_prioritizes_old_format_suggestions(tmp_path):
    """兼容旧格式「重点关注建议」板块。"""
    content = (
        "# 世界感知摘要 2026-05-15\n\n"
        "## 重点关注建议\n\n"
        "### AI/科技\n"
        "- **OpenAI 发布新模型**：关注理由：与你目前的工作直接相关\n\n"
        "---\n\n"
        "## 新闻详情\n\n"
        "不应该出现这些新闻详情内容"
    )
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "2026-05-15.md").write_text(content, encoding="utf-8")

    provider = WorldProvider(data_dir=tmp_path)
    result = provider.get_context("morning", _make_date_range("2026-05-15"))
    assert result is not None
    assert "重点关注建议" in result
    assert "与你目前的工作直接相关" in result
    assert "不应该出现这些新闻详情内容" not in result


def test_falls_back_to_truncation_when_no_suggestions(tmp_path):
    """无「重点关注建议」板块时，回退到前 N 字符截断。"""
    content = "# 世界感知摘要\n\n## TestSource\n\nSome news content here."
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "2026-05-15.md").write_text(content, encoding="utf-8")

    provider = WorldProvider(data_dir=tmp_path)
    result = provider.get_context("morning", _make_date_range("2026-05-15"))
    assert result is not None
    assert "Some news content here" in result
