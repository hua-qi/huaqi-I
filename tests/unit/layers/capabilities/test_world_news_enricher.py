import pytest
from pathlib import Path
from unittest.mock import MagicMock


MOCK_SOURCE_CONTENT = """### 最相关：AI技术趋势报告

**原文链接**：https://example.com/ai
**为什么选这篇**：作为AI工程师，了解最新技术趋势对你的职业发展至关重要

2026年AI技术呈现多模态融合趋势，各大科技公司纷纷推出新一代模型。

中国市场在AI应用落地方面表现活跃，垂直领域应用不断涌现。

### 最相关：前端框架新动态

**原文链接**：https://example.com/frontend
**为什么选这篇**：前端核心技能，框架变化直接影响开发效率

React 19即将发布，带来全新的Server Components架构。

### 视野拓展：全球气候变化新协定

**原文链接**：https://example.com/climate
**为什么也值得了解**：气候政策影响全球经济和科技投资方向

联合国气候大会达成新减排协议，各主要经济体承诺加大清洁能源投资。"""

MOCK_AGGREGATE_CONTENT = """# 世界感知摘要 2026-05-15

## 领域概览
今日AI/科技领域持续活跃，宏观经济政策保持稳定。

## TestSource

""" + MOCK_SOURCE_CONTENT + """

## 综合推荐
基于用户AI工程师画像，建议重点关注AI技术趋势和前端框架动态。"""


# ═══ Prompt 测试 ═══

class TestEnricherPrompt:
    def test_prompt_has_source_placeholder(self):
        """prompt 包含 source_name 占位符。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _SOURCE_PROMPT
        assert "{source_name}" in _SOURCE_PROMPT
        assert "{article_list}" in _SOURCE_PROMPT
        assert "{user_context}" in _SOURCE_PROMPT

    def test_prompt_requires_two_most_relevant(self):
        """prompt 要求选出 2 篇最相关。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _SOURCE_PROMPT
        assert "2 篇与用户最相关的" in _SOURCE_PROMPT

    def test_prompt_requires_one_least_relevant(self):
        """prompt 要求选出 1 篇最不相关（视野拓展）。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _SOURCE_PROMPT
        assert "1 篇与用户最不相关的" in _SOURCE_PROMPT
        assert "视野拓展" in _SOURCE_PROMPT

    def test_prompt_requires_chinese_summary(self):
        """prompt 要求中文摘要。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _SOURCE_PROMPT
        assert "中文摘要" in _SOURCE_PROMPT
        assert "翻译为中文" in _SOURCE_PROMPT

    def test_prompt_has_link_requirement(self):
        """prompt 要求包含原文链接。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _SOURCE_PROMPT
        assert "原文链接" in _SOURCE_PROMPT

    def test_prompt_has_user_context_placeholder(self):
        """prompt 包含用户画像占位符。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _SOURCE_PROMPT
        assert "{user_context}" in _SOURCE_PROMPT


# ═══ 用户画像构建 ═══

class TestUserContextSection:
    def test_build_with_valid_snapshot(self):
        from huaqi_src.layers.capabilities.world_news_enricher import \
            _build_user_context_section

        snapshot = """## 核心认知（TELOS）

---
dimension: goals
layer: middle
---

## 当前认知
正在开发一个 AI 助手产品，关注 LLM 应用和 Agent 技术栈

---
dimension: challenges
layer: middle
---

## 当前认知
时间管理困难，需要在主业和副业之间找到平衡
"""
        result = _build_user_context_section(snapshot)
        assert len(result) > 0
        assert "AI 助手" in result or "Agent" in result

    def test_build_with_empty_snapshot(self):
        from huaqi_src.layers.capabilities.world_news_enricher import \
            _build_user_context_section

        assert _build_user_context_section("") == ""
        assert _build_user_context_section(None) == ""


# ═══ Parse Sources ═══

class TestParseSources:
    def test_single_source(self):
        from huaqi_src.layers.capabilities.world_news_enricher import _parse_sources

        raw = (
            "# 世界感知摘要 2026-05-15\n\n"
            "## 36氪\n"
            "# Title 1\n\nContent 1\n\n**链接**：http://a.com\n\n---\n"
        )
        sources = _parse_sources(raw)
        assert "36氪" in sources
        assert len(sources["36氪"]) == 1
        assert "Title 1" in sources["36氪"][0]

    def test_multiple_sources(self):
        from huaqi_src.layers.capabilities.world_news_enricher import _parse_sources

        raw = (
            "# 世界感知摘要 2026-05-15\n\n"
            "## 36氪\n"
            "# Title 1\n\nContent 1\n\n**链接**：http://a.com\n\n---\n\n"
            "## BBC科技\n"
            "# Title 2\n\nContent 2\n\n**链接**：http://b.com\n\n---\n"
        )
        sources = _parse_sources(raw)
        assert len(sources) == 2
        assert "36氪" in sources
        assert "BBC科技" in sources
        assert len(sources["36氪"]) == 1
        assert len(sources["BBC科技"]) == 1

    def test_multiple_articles_same_source(self):
        from huaqi_src.layers.capabilities.world_news_enricher import _parse_sources

        raw = (
            "# 世界感知摘要 2026-05-15\n\n"
            "## 36氪\n"
            "# Title 1\n\nContent 1\n\n**链接**：http://a.com\n\n---\n\n"
            "## 36氪\n"
            "# Title 2\n\nContent 2\n\n**链接**：http://b.com\n\n---\n"
        )
        sources = _parse_sources(raw)
        assert len(sources) == 1
        assert len(sources["36氪"]) == 2
        assert "Title 1" in sources["36氪"][0]
        assert "Title 2" in sources["36氪"][1]


# ═══ 文件操作 ═══

class TestEnricherFileOperations:
    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.quick_chat.side_effect = [MOCK_SOURCE_CONTENT, MOCK_AGGREGATE_CONTENT]
        return llm

    @pytest.fixture
    def temp_file(self, tmp_path):
        f = tmp_path / "test_world.md"
        f.write_text(
            "# 世界感知摘要 2026-05-15\n\n"
            "## TestSource\n"
            "# Some Title\n\n"
            "Some content\n\n"
            "**链接**：https://example.com\n\n---\n",
            encoding="utf-8",
        )
        return f

    def test_enrich_file_success(self, mock_llm, temp_file):
        from huaqi_src.layers.capabilities.world_news_enricher import \
            WorldNewsEnricher

        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(temp_file)
        assert result is True
        new_content = temp_file.read_text(encoding="utf-8")
        assert "领域概览" in new_content
        assert "综合推荐" in new_content
        assert "AI技术趋势" in new_content

    def test_enrich_file_with_user_context(self, mock_llm, temp_file):
        from huaqi_src.layers.capabilities.world_news_enricher import \
            WorldNewsEnricher

        enricher = WorldNewsEnricher(mock_llm)
        user_ctx = "用户是 AI 工程师，关注 LLM Agent 技术栈"
        result = enricher.enrich_file(temp_file, user_context=user_ctx)
        assert result is True
        # 检查 source prompt 中包含 user_context
        source_call_args = mock_llm.quick_chat.call_args_list[0][0][0]
        assert user_ctx in source_call_args

    def test_enrich_file_empty(self, mock_llm):
        from huaqi_src.layers.capabilities.world_news_enricher import \
            WorldNewsEnricher

        f = Path("/tmp/empty_test_world.md")
        f.write_text("", encoding="utf-8")
        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(f)
        assert result is False
        mock_llm.quick_chat.assert_not_called()

    def test_enrich_file_llm_failure(self, tmp_path):
        from huaqi_src.layers.capabilities.world_news_enricher import \
            WorldNewsEnricher

        mock_llm = MagicMock()
        mock_llm.quick_chat.side_effect = RuntimeError("API error")
        f = tmp_path / "fail.md"
        f.write_text(
            "# 世界感知摘要 2026-05-15\n\n"
            "## TestSource\n"
            "# test\n\n"
            "content\n\n"
            "**链接**：https://x.com\n\n---\n",
            encoding="utf-8",
        )
        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(f)
        assert result is False


# ═══ Markdown 提取 ═══

class TestExtractMarkdown:
    def test_extract_from_code_block(self):
        from huaqi_src.layers.capabilities.world_news_enricher import \
            _extract_markdown

        text = "Here is the result:\n```markdown\n# Title\n\nContent\n```\nDone."
        result = _extract_markdown(text)
        assert result == "# Title\n\nContent"

    def test_extract_from_heading(self):
        from huaqi_src.layers.capabilities.world_news_enricher import \
            _extract_markdown

        text = "Some preface text\n\n# Real Title\n\nReal content"
        result = _extract_markdown(text)
        assert result == "# Real Title\n\nReal content"

    def test_extract_plain_text(self):
        from huaqi_src.layers.capabilities.world_news_enricher import \
            _extract_markdown

        text = "Just plain text without any markdown markers."
        result = _extract_markdown(text)
        assert result == text.strip()
