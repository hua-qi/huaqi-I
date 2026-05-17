# Plan: world-news-enhance

> 优化世界新闻采集产出内容：中英对照 + 链接 + 摘要 + TELOS 个性化重点关注建议。

**Goal:** 让 `huaqi world fetch` 产出的 `world/{date}.md` 包含原文链接、中英对照、结构化摘要，以及基于用户 TELOS 画像的个性化重点关注建议。同时优化报告系统的展示。
**Architecture:** 4 个 Task，自上而下：数据源（加链接）→ 增强器（改 prompt + 注入用户画像）→ CLI（加载 TELOS）→ 报告层（智能提取）
**Spec:** `docs/specs/world-news-enhance.md`

---

## 背景阅读

实施前必读：
- `docs/specs/world-news-enhance.md` — 功能规格
- `huaqi_src/layers/data/world/sources/rss_source.py` — RSS 源（加链接）
- `huaqi_src/layers/capabilities/world_news_enricher.py` — LLM 增强器（改 prompt + 注入用户画像）
- `huaqi_src/cli/commands/world.py` — CLI 命令（加载 TELOS 并传入 enricher）
- `huaqi_src/layers/capabilities/reports/providers/world.py` — 报告提供者（智能提取）
- `huaqi_src/layers/data/world/storage.py` — 存储格式（不改，仅阅读了解）
- `huaqi_src/layers/growth/telos/manager.py` — TelosManager（读取用户画像）
- `huaqi_src/layers/growth/telos/context.py` — TelosContextBuilder（build_telos_snapshot）

运行已有测试确认基线：
```bash
pytest tests/unit/layers/data/world/ tests/unit/cli/commands/test_world_command.py -x --tb=short
```

---

## Task 1: RSSSource — 原文链接加入 content

**AC 覆盖:** AC-1

**Files:**
- Modify: `huaqi_src/layers/data/world/sources/rss_source.py`
- Create: `tests/unit/layers/data/world/test_rss_source.py`

### Step 1: 写失败测试

```python
# tests/unit/layers/data/world/test_rss_source.py
import datetime
from unittest.mock import patch, MagicMock
from huaqi_src.layers.data.world.sources.rss_source import RSSSource

class TestRSSSource:
    def test_content_contains_link(self):
        """AC-1: RSS 条目 content 包含原文链接行。"""
        mock_entry = MagicMock()
        mock_entry.configure_mock(
            title="Test News",
            link="https://example.com/news/1",
            summary="Summary text",
            published_parsed=datetime.datetime(2026, 5, 15, 8, 0).timetuple(),
        )
        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        with patch("feedparser.parse", return_value=mock_feed):
            source = RSSSource(url="https://example.com/feed", name="TestSource")
            docs = source.fetch()
            assert len(docs) == 1
            assert "**链接**" in docs[0].content
            assert "https://example.com/news/1" in docs[0].content

    def test_content_contains_title(self):
        """内容仍然以标题开头。"""
        mock_entry = MagicMock()
        mock_entry.configure_mock(
            title="Breaking News",
            link="https://example.com/news/2",
            summary="Some summary",
            published_parsed=None,
        )
        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        with patch("feedparser.parse", return_value=mock_feed):
            source = RSSSource(url="https://example.com/feed", name="TS")
            docs = source.fetch()
            assert docs[0].content.startswith("# Breaking News")
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/layers/data/world/test_rss_source.py -v
```

期望：`test_content_contains_link` 失败，错误信息为 `AssertionError`

### Step 3: 写实现

修改 `rss_source.py` 的 `fetch()` 方法，在 `full_content` 中加入链接行：

```python
# 改前
full_content = f"# {title}\n\n{content}"

# 改后
url = entry.get("link", "")
full_content = f"# {title}\n\n{content}\n\n**链接**：{url}"
```

### Step 4: 运行确认通过

```bash
pytest tests/unit/layers/data/world/test_rss_source.py -v
```

期望：2 个测试全部通过

### Step 5: 冒烟测试沉淀

在 `tests/smoke_test.py` 末尾追加 `TestWorldNewsEnhance` 类，添加 AC-1 冒烟测试。

---

## Task 2: WorldNewsEnricher — 重构增强 prompt + 注入用户画像

**AC 覆盖:** AC-2, AC-3, AC-5, AC-6

**核心变更：**
1. `enrich_file()` 新增可选参数 `user_context: str | None = None`
2. `_ENRICH_PROMPT` 重写，包含用户画像占位符 `{user_context}`
3. 用户画像不为空时，要求 LLM 以「这条新闻与你有什么关系」为标准判断关注优先级；为空时回退到通用判断
4. 新增 `_build_user_context_section()` 辅助函数，将 TELOS snapshot 转为 prompt 可用的简短段落

**Files:**
- Modify: `huaqi_src/layers/capabilities/world_news_enricher.py`
- Create: `tests/unit/layers/capabilities/test_world_news_enricher.py`

### Step 1: 写失败测试

```python
# tests/unit/layers/capabilities/test_world_news_enricher.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from huaqi_src.layers.capabilities.world_news_enricher import (
    WorldNewsEnricher,
    _extract_markdown,
    _build_user_context_section,
)

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

此次发布的模型支持 128K 上下文窗口，代码生成能力较上一代提升 40%。业界普遍认为这将是 AI 领域的一个重要里程碑。

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
        from huaqi_src.layers.capabilities.world_news_enricher import _ENRICH_PROMPT
        assert "英文原标题" in _ENRICH_PROMPT or "英文" in _ENRICH_PROMPT
        assert "链接" in _ENRICH_PROMPT
        assert "摘要" in _ENRICH_PROMPT

    def test_prompt_requests_suggestions_section(self):
        """AC-3: prompt 要求重点关注建议板块。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _ENRICH_PROMPT
        assert "重点关注建议" in _ENRICH_PROMPT
        assert ("分类" in _ENRICH_PROMPT or "领域" in _ENRICH_PROMPT)

    def test_prompt_requests_chinese_source_handling(self):
        """AC-5: prompt 要求中文源保留原文并扩展。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _ENRICH_PROMPT
        assert "中文" in _ENRICH_PROMPT

    def test_prompt_has_user_context_placeholder(self):
        """prompt 包含用户画像占位符。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _ENRICH_PROMPT
        assert "{user_context}" in _ENRICH_PROMPT


class TestUserContextSection:
    def test_build_with_valid_snapshot(self):
        """有效 TELOS snapshot 生成简短用户画像段落。"""
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
        assert "努力成为" not in result  # 不是默认兜底文案
        assert len(result) > 0

    def test_build_with_empty_snapshot(self):
        """空 snapshot 返回空字符串。"""
        assert _build_user_context_section("") == ""
        assert _build_user_context_section(None) == ""

    def test_build_with_minimal_snapshot(self):
        """简短但有效的 snapshot 能正常处理。"""
        result = _build_user_context_section("## 核心认知（TELOS）\n\n无数据")
        assert len(result) > 0


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
        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(temp_file)
        assert result is True
        new_content = temp_file.read_text(encoding="utf-8")
        assert "重点关注建议" in new_content
        assert "**链接**" in new_content

    def test_enrich_file_with_user_context(self, mock_llm, temp_file):
        """user_context 不为空时，注入到 prompt 中。"""
        enricher = WorldNewsEnricher(mock_llm)
        user_ctx = "用户是 AI 工程师，关注 LLM Agent 技术栈"
        result = enricher.enrich_file(temp_file, user_context=user_ctx)
        assert result is True
        # 验证 prompt 包含了用户画像
        call_args = mock_llm.quick_chat.call_args[0][0]
        assert user_ctx in call_args

    def test_enrich_file_without_user_context(self, mock_llm, temp_file):
        """user_context 为空时，正常执行（回退到通用判断）。"""
        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(temp_file)
        assert result is True

    def test_enrich_file_empty(self, mock_llm):
        """AC-6: 空文件不调用 LLM，返回 False。"""
        f = Path("/tmp/empty_test_world.md")
        f.write_text("", encoding="utf-8")
        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(f)
        assert result is False
        mock_llm.quick_chat.assert_not_called()

    def test_enrich_file_llm_failure(self, tmp_path):
        """AC-6: LLM 调用失败时返回 False。"""
        mock_llm = MagicMock()
        mock_llm.quick_chat.side_effect = RuntimeError("API error")
        f = tmp_path / "fail.md"
        f.write_text("# test\n\ncontent\n", encoding="utf-8")
        enricher = WorldNewsEnricher(mock_llm)
        result = enricher.enrich_file(f)
        assert result is False


class TestExtractMarkdown:
    def test_extract_from_code_block(self):
        text = "Here is the result:\n```markdown\n# Title\n\nContent\n```\nDone."
        result = _extract_markdown(text)
        assert result == "# Title\n\nContent"

    def test_extract_from_heading(self):
        text = "Some preface text\n\n# Real Title\n\nReal content"
        result = _extract_markdown(text)
        assert result == "# Real Title\n\nReal content"

    def test_extract_plain_text(self):
        text = "Just plain text without any markdown markers."
        result = _extract_markdown(text)
        assert result == text.strip()
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/layers/capabilities/test_world_news_enricher.py -v
```

期望：prompt 相关测试失败（旧 prompt 不含「重点关注建议」「英文原标题」等关键词，且 `enrich_file` 不接受 `user_context` 参数）

### Step 3: 写实现

**3a. 新增 `_build_user_context_section()` 辅助函数：**

```python
def _build_user_context_section(telos_snapshot: str | None) -> str:
    """将 TELOS snapshot 转为 prompt 可用的简短用户画像段落。"""
    if not telos_snapshot or not telos_snapshot.strip():
        return ""
    # 提取关键维度（目标、挑战、信念），过滤掉 markdown frontmatter 噪音
    lines = []
    for line in telos_snapshot.split("\n"):
        line = line.strip()
        if line.startswith("---") or line.startswith("dimension:") or \
           line.startswith("layer:") or line.startswith("confidence:") or \
           line.startswith("update_count:") or line.startswith("is_active:"):
            continue
        if line and not line.startswith("#"):
            lines.append(line)
    summary = " ".join(lines)
    # 限制长度，避免 prompt 过长
    if len(summary) > 1500:
        summary = summary[:1500].rsplit("。", 1)[0] + "。"
    return summary
```

**3b. 修改 `WorldNewsEnricher.enrich_file()` 签名：**

```python
def enrich_file(self, file_path: Path, user_context: str | None = None) -> bool:
    """读取世界新闻文件，翻译并扩展内容，原地覆写。
    
    Args:
        file_path: 世界新闻 markdown 文件路径
        user_context: 可选的用户画像文本（来自 TELOS），用于个性化重点关注建议
    """
    raw_content = file_path.read_text(encoding="utf-8")
    if not raw_content.strip():
        return False

    user_section = _build_user_context_section(user_context)
    prompt = _ENRICH_PROMPT.format(raw_content=raw_content, user_context=user_section)
    ...
```

**3c. 重写 `_ENRICH_PROMPT`：**

```python
_ENRICH_PROMPT = """你是一位专业的新闻编辑，也是用户的个人 AI 伙伴。请处理以下世界新闻内容：

{raw_content}

{user_context}

## 输出结构

按以下结构输出 Markdown：

# 世界感知摘要 YYYY-MM-DD

## 重点关注建议

按以下领域分类，列出今日最值得**该用户**关注的新闻及关注理由（每类 1-3 条）：
- **AI/科技**：涉及 AI 技术突破、科技公司重大动态、开发者工具变化
- **宏观经济与政策**：涉及政策变化、市场趋势、国际关系、监管动态
- **行业动态**：涉及具体行业的重要变化

格式示例：
### AI/科技
- **新闻关键词**：关注理由（一句话说明为什么**这个用户**需要关注，而非泛泛而谈的新闻重要性）

**重要**：如果上面提供了用户画像信息，请基于用户的具体背景（职业、兴趣、目标、挑战）来判断哪些新闻值得关注，关注理由必须与用户的具体情况关联。如果没有用户画像，则基于新闻本身的重要性给出通用建议。

---

## 新闻详情

### 来源：{{来源名称}}

#### {{{{英文原标题}}}}
**中文标题**：{{中文翻译标题}}

**链接**：{{原文 URL}}

{{中文摘要，2-3 段，补充关键背景信息}}

---

## 内容要求

1. **中英对照**：每条新闻保留英文原标题（用 #### 标记），紧接着给出中文标题翻译
2. **链接必含**：每条新闻必须包含原文链接（**链接**：URL）
3. **摘要扩展**：每条新闻扩展为 2-3 段中文内容，补充关键背景信息（如相关事件、行业影响、历史背景），但不要编造事实
4. **中文源处理**：原本就是中文的新闻（如 36氪、虎嗅、少数派）保留原文内容并适当扩展细节，不强行翻译
5. **英文源处理**：英文新闻（如 BBC、CNN、路透社）翻译为流畅中文，保留英文原标题
6. **个性化建议**：重点关注建议需基于用户画像（如已提供），关注理由要说明「为什么跟你有关」
7. **只输出 Markdown**：不要加任何额外说明、前言或结语"""
```

### Step 4: 运行确认通过

```bash
pytest tests/unit/layers/capabilities/test_world_news_enricher.py -v
```

期望：全部测试通过

### Step 5: 冒烟测试沉淀

在 `tests/smoke_test.py` 的 `TestWorldNewsEnhance` 类中追加 AC-2、AC-3、AC-5、AC-6 冒烟测试。

---

## Task 3: CLI — 加载 TELOS 并传入 enricher

**目标：** 在 `huaqi world fetch` 命令中加载用户 TELOS 画像，传递给 `WorldNewsEnricher.enrich_file()`。

**Files:**
- Modify: `huaqi_src/cli/commands/world.py`
- Modify: `tests/unit/cli/commands/test_world_command.py`

### Step 1: 写失败测试

在 `test_world_command.py` 中追加：

```python
def test_fetch_cmd_passes_user_context_to_enricher(self, tmp_path, monkeypatch):
    """CLI fetch 命令将 TELOS 用户画像传递给 enricher。"""
    from unittest.mock import patch, MagicMock
    from huaqi_src.cli.commands.world import fetch_cmd

    # Mock pipeline 返回文件路径
    mock_file = tmp_path / "world" / "2026-05-15.md"
    mock_file.parent.mkdir(parents=True)
    mock_file.write_text("# test\n\ncontent\n\n**链接**：https://x.com\n", encoding="utf-8")

    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = mock_file

    mock_enricher = MagicMock()
    mock_enricher.enrich_file.return_value = True

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    with patch("huaqi_src.cli.commands.world.WorldPipeline", return_value=mock_pipeline), \
         patch("huaqi_src.cli.commands.world._build_enricher", return_value=mock_enricher):
        # 这里测试 _build_enricher 不变，重点是 fetch_cmd 中 load_telos 和传参逻辑
        pass  # 实际测试需要 mock typer 和 _load_user_context
```

### Step 2: 运行确认失败

期望：enricher.enrich_file 被调用时只传了 file_path，没有 user_context

### Step 3: 写实现

修改 `huaqi_src/cli/commands/world.py`：

```python
def _load_user_context() -> str | None:
    """从 TELOS 加载用户画像摘要，用于个性化新闻建议。"""
    try:
        from huaqi_src.config.paths import require_data_dir
        from huaqi_src.layers.growth.telos.manager import TelosManager

        data_dir = require_data_dir()
        telos_dir = data_dir / "telos"
        if not telos_dir.exists():
            return None
        manager = TelosManager(telos_dir=telos_dir, git_commit=False)
        active = manager.list_active()
        if not active:
            return None
        # 提取全部 8 个维度
        labels = {
            "beliefs": "核心信念", "models": "心理模型", "narratives": "自我叙事",
            "goals": "当前目标", "challenges": "当前挑战", "strategies": "应对策略",
            "learned": "最近所学", "shadows": "盲点/短板",
        }
        parts = []
        for dim in active:
            if dim.content.strip():
                label = labels.get(dim.name, dim.name)
                parts.append(f"{label}：{dim.content.strip()}")
        return "\n".join(parts) if parts else None
    except Exception:
        return None


@world_app.command("fetch")
def fetch_cmd(
    date: Optional[str] = typer.Option(None, "--date", help="采集日期 YYYY-MM-DD，默认今天"),
    no_enrich: bool = typer.Option(False, "--no-enrich", help="跳过 LLM 翻译/扩展"),
):
    target_date = ...
    pipeline = WorldPipeline()
    saved_path = pipeline.run(date=target_date)
    ...

    if not no_enrich:
        enricher = _build_enricher()
        if enricher:
            typer.echo("[World] 正在翻译和扩展新闻内容...")
            user_context = _load_user_context()  # 新增：加载用户画像
            if enricher.enrich_file(saved_path, user_context=user_context):
                typer.echo("[World] 内容增强完成")
            else:
                typer.echo("[World] 内容增强失败，保留原始内容")
        ...
```

### Step 4: 运行确认通过

```bash
pytest tests/unit/cli/commands/test_world_command.py -v
```

### Step 5: 冒烟测试沉淀

在 `tests/smoke_test.py` 的 `TestWorldNewsEnhance` 类中追加相关冒烟测试。

---

## Task 4: WorldProvider — 智能提取报告内容

**AC 覆盖:** AC-4

**Files:**
- Modify: `huaqi_src/layers/capabilities/reports/providers/world.py`
- Modify: `tests/unit/layers/data/world/test_world_provider.py`

### Step 1: 写失败测试

在 `test_world_provider.py` 中追加：

```python
def test_world_provider_prioritizes_suggestions_section(self, tmp_path):
    """AC-4: 当文件包含「重点关注建议」时，优先展示该部分。"""
    from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
    from huaqi_src.layers.capabilities.reports.providers import DateRange
    import datetime

    content = (
        "# 世界感知摘要 2026-05-15\n\n"
        "## 重点关注建议\n\n"
        "### AI/科技\n"
        "- **OpenAI 发布新模型**：关注理由：与你目前的工作直接相关\n\n"
        "---\n\n"
        "## 新闻详情\n\n"
        "大量新闻内容..." + "x" * 2000
    )
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    world_file = world_dir / "2026-05-15.md"
    world_file.write_text(content, encoding="utf-8")

    provider = WorldProvider(data_dir=tmp_path)
    date_range = DateRange(
        start=datetime.date(2026, 5, 15),
        end=datetime.date(2026, 5, 15),
    )
    result = provider.get_context("morning", date_range)
    assert result is not None
    assert "重点关注建议" in result
    assert "与你目前的工作直接相关" in result


def test_world_provider_falls_back_to_truncation(self, tmp_path):
    """无「重点关注建议」板块时，回退到前 N 字符截断。"""
    from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
    from huaqi_src.layers.capabilities.reports.providers import DateRange
    import datetime

    content = "# 世界感知摘要\n\n## TestSource\n\nSome news content here."
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    world_file = world_dir / "2026-05-15.md"
    world_file.write_text(content, encoding="utf-8")

    provider = WorldProvider(data_dir=tmp_path)
    date_range = DateRange(
        start=datetime.date(2026, 5, 15),
        end=datetime.date(2026, 5, 15),
    )
    result = provider.get_context("morning", date_range)
    assert result is not None
    assert "Some news content here" in result
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/layers/data/world/test_world_provider.py::test_world_provider_prioritizes_suggestions_section -v
```

期望：失败（当前 `get_context` 只是 `[:1000]` 截断，不会优先提取「重点关注建议」）

### Step 3: 写实现

修改 `WorldProvider`，新增 `_extract_for_report()` 方法：

```python
import re

def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
    today = date_range.end.isoformat()
    world_file = self._data_dir / "world" / f"{today}.md"
    if not world_file.exists():
        world_file = self._lazy_fetch(today)
    if world_file is None or not world_file.exists():
        return None
    content = world_file.read_text(encoding="utf-8")
    extracted = self._extract_for_report(content)
    return f"## 今日世界热点\n{extracted}"

def _extract_for_report(self, content: str, max_chars: int = 1500) -> str:
    """从世界新闻文件中智能提取报告用内容。

    优先完整保留「重点关注建议」板块，剩余空间用于新闻摘要。
    无建议板块时回退到简单截断。
    """
    suggest_match = re.search(
        r'## 重点关注建议\n(.*?)(?=\n## 新闻详情|\n---\n## )',
        content, re.DOTALL
    )
    if suggest_match:
        suggestions = suggest_match.group(0).strip()
        if len(suggestions) <= max_chars:
            return suggestions
        return suggestions[:max_chars].rsplit("\n", 1)[0]

    return content[:max_chars]
```

### Step 4: 运行确认通过

```bash
pytest tests/unit/layers/data/world/test_world_provider.py -v
```

期望：全部测试通过

### Step 5: 冒烟测试沉淀

在 `tests/smoke_test.py` 的 `TestWorldNewsEnhance` 类中追加 AC-4 冒烟测试。

---

## Task 5: 集成验证

**覆盖:** 全量回归 + 冒烟测试全通过

### Step 1: 运行全量测试

```bash
pytest tests/ -x -m "not e2e" --tb=short
```

### Step 2: 运行冒烟测试

```bash
pytest tests/smoke_test.py -v
```

### Step 3: 验证冒烟测试新增

确认 `TestWorldNewsEnhance` 类包含所有 AC-1 ~ AC-6 对应的冒烟测试，且全部通过。
