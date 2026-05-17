import pytest
from pathlib import Path
from unittest.mock import MagicMock


MOCK_ENRICHED_CONTENT = """# 世界感知摘要 2026-05-15

## 重点关注建议

### AI/科技
- **OpenAI 发布新模型**：关注理由：与你目前的 AI 工程师工作直接相关，可能影响你的技术选型

### 宏观经济
- **美联储利率决议**：关注理由：影响全球资本市场

---

## 新闻详情

### 来源：BBC科技

#### OpenAI Announces GPT-5
**中文标题**：OpenAI 发布 GPT-5 模型

**链接**：https://example.com/gpt5

OpenAI 今日正式发布了 GPT-5 模型。该模型在推理能力、多模态理解等方面取得了显著突破。

此次发布的模型支持 128K 上下文窗口，代码生成能力较上一代提升 40%。

---

### 来源：36氪

#### 国内某科技公司完成新一轮融资
**链接**：https://example.com/funding

国内某科技公司近日完成了新一轮融资。该公司专注于企业级 AI 解决方案。

融资后将加速产品研发和市场拓展。
"""


class TestEnricherPrompt:
    def test_prompt_requests_bilingual_format(self):
        """AC-2: prompt 要求中英对照格式。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _ENRICH_FALLBACK
        assert "英文原标题" in _ENRICH_FALLBACK or "英文" in _ENRICH_FALLBACK
        assert "链接" in _ENRICH_FALLBACK
        assert "摘要" in _ENRICH_FALLBACK

    def test_prompt_requests_suggestions_section(self):
        """AC-3: prompt 要求重点关注建议板块。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _ENRICH_FALLBACK
        assert "重点关注建议" in _ENRICH_FALLBACK
        assert "分类" in _ENRICH_FALLBACK or "领域" in _ENRICH_FALLBACK

    def test_prompt_requests_chinese_source_handling(self):
        """AC-5: prompt 要求中文源保留原文并扩展。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _ENRICH_FALLBACK
        assert "中文" in _ENRICH_FALLBACK

    def test_prompt_has_user_context_placeholder(self):
        """prompt 包含用户画像占位符。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _ENRICH_FALLBACK
        assert "{user_context}" in _ENRICH_FALLBACK


class TestUserContextSection:
    def test_build_with_valid_snapshot(self):
        """有效 TELOS snapshot 生成简短用户画像段落。"""
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
        """空 snapshot 返回空字符串。"""
        from huaqi_src.layers.capabilities.world_news_enricher import \
            _build_user_context_section

        assert _build_user_context_section("") == ""
        assert _build_user_context_section(None) == ""


class TestEnricherFileOperations:
    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.quick_chat.return_value = MOCK_ENRICHED_CONTENT
        return llm

    @pytest.fixture
    def temp_file(self, tmp_path):
        f = tmp_path / "test_world.md"
        f.write_text(
            "# 世界感知摘要 2026-05-15\n\n"
            "## TestSource\n\n"
            "# Some Title\n\n"
            "Some content\n\n"
            "**链接**：https://example.com\n\n---\n",
            encoding="utf-8",
        )
        return f

    def test_enrich_file_success(self, mock_llm, temp_file):
        """AC-2: enrich 成功写入新内容。"""
        from huaqi_src.layers.capabilities.world_news_enricher import \
            WorldNewsEnricher

        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(temp_file)
        assert result is True
        new_content = temp_file.read_text(encoding="utf-8")
        assert "重点关注建议" in new_content
        assert "**链接**" in new_content

    def test_enrich_file_with_user_context(self, mock_llm, temp_file):
        """user_context 不为空时，注入到 prompt 中。"""
        from huaqi_src.layers.capabilities.world_news_enricher import \
            WorldNewsEnricher

        enricher = WorldNewsEnricher(mock_llm)
        user_ctx = "用户是 AI 工程师，关注 LLM Agent 技术栈"
        result = enricher.enrich_file(temp_file, user_context=user_ctx)
        assert result is True
        call_args = mock_llm.quick_chat.call_args[0][0]
        assert user_ctx in call_args

    def test_enrich_file_empty(self, mock_llm):
        """AC-6: 空文件不调用 LLM，返回 False。"""
        from huaqi_src.layers.capabilities.world_news_enricher import \
            WorldNewsEnricher

        f = Path("/tmp/empty_test_world.md")
        f.write_text("", encoding="utf-8")
        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(f)
        assert result is False
        mock_llm.quick_chat.assert_not_called()

    def test_enrich_file_llm_failure(self, tmp_path):
        """AC-6: LLM 调用失败时返回 False。"""
        from huaqi_src.layers.capabilities.world_news_enricher import \
            WorldNewsEnricher

        mock_llm = MagicMock()
        mock_llm.quick_chat.side_effect = RuntimeError("API error")
        f = tmp_path / "fail.md"
        f.write_text("# test\n\ncontent\n", encoding="utf-8")
        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(f)
        assert result is False


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
