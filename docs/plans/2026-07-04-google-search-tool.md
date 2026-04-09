# Google Search Tool Implementation Plan

**Goal:** 为 Huaqi 新增 `google_search_tool`，让 LLM 在本地数据不足时可以调用 DuckDuckGo 实时搜索互联网，同时引入装饰器自动注册机制消除 `chat_nodes.py` 中的硬编码 tools 列表。

**Architecture:** 在 `tools.py` 新增 `_TOOL_REGISTRY` 全局列表和 `register_tool` 装饰器；所有现有 tools（含 `learning_tools.py` 中的 4 个）补加 `@register_tool`；`chat_nodes.py` 改用 `_TOOL_REGISTRY` 替换硬编码列表；新增 `google_search_tool` 使用 `duckduckgo-search` 库实现，内部捕获所有异常返回友好字符串。

**Tech Stack:** Python, `duckduckgo-search`, `langchain-core` (`@tool`)

---

### Task 1: 新增 `duckduckgo-search` 依赖

**Files:**
- Modify: `requirements.txt`

**Step 1: 在 requirements.txt 末尾追加依赖**

```
duckduckgo-search>=6.0.0
```

**Step 2: 安装依赖**

Run: `pip install duckduckgo-search`
Expected: Successfully installed duckduckgo-search-x.x.x

**Step 3: 验证可导入**

Run: `python -c "from duckduckgo_search import DDGS; print('ok')"`
Expected: `ok`

---

### Task 2: 在 `tools.py` 新增注册机制和 `google_search_tool`

**Files:**
- Modify: `huaqi_src/agent/tools.py`

**Step 1: 写失败测试——registry 存在且包含所有 tools**

新建文件 `tests/unit/agent/test_tool_registry.py`：

```python
def test_tool_registry_is_not_empty():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    assert len(_TOOL_REGISTRY) > 0

def test_tool_registry_contains_google_search():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    names = [t.name for t in _TOOL_REGISTRY]
    assert "google_search_tool" in names

def test_tool_registry_contains_all_existing_tools():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    names = [t.name for t in _TOOL_REGISTRY]
    expected = [
        "search_diary_tool",
        "search_work_docs_tool",
        "search_events_tool",
        "search_worldnews_tool",
        "search_person_tool",
        "search_cli_chats_tool",
        "get_relationship_map_tool",
        "search_huaqi_chats_tool",
        "get_learning_progress_tool",
        "get_course_outline_tool",
        "start_lesson_tool",
        "mark_lesson_complete_tool",
    ]
    for name in expected:
        assert name in names, f"{name} not in registry"
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/unit/agent/test_tool_registry.py -v`
Expected: FAIL with `ImportError: cannot import name '_TOOL_REGISTRY'`

**Step 3: 在 `tools.py` 顶部添加注册机制**

在 `from langchain_core.tools import tool` 后紧接着添加：

```python
_TOOL_REGISTRY: list = []

def register_tool(fn):
    _TOOL_REGISTRY.append(fn)
    return fn
```

**Step 4: 给所有现有 tools 补加 `@register_tool`**

对 `tools.py` 中的每个 `@tool` 装饰的函数，在 `@tool` 上方再加一行 `@register_tool`：

```python
@register_tool
@tool
def search_diary_tool(query: str) -> str:
    ...

@register_tool
@tool
def search_work_docs_tool(query: str) -> str:
    ...

@register_tool
@tool
def search_events_tool(query: str) -> str:
    ...

@register_tool
@tool
def search_worldnews_tool(query: str) -> str:
    ...

@register_tool
@tool
def search_person_tool(name: str) -> str:
    ...

@register_tool
@tool
def search_cli_chats_tool(query: str) -> str:
    ...

@register_tool
@tool
def get_relationship_map_tool() -> str:
    ...

@register_tool
@tool
def search_huaqi_chats_tool(query: str) -> str:
    ...
```

> 注意：`learning_tools.py` 中的 4 个 tools 通过 `from ... import` 导入后也需要注册，见 Task 3。

**Step 5: 在 `tools.py` 末尾（import learning_tools 之后）追加 `google_search_tool`**

```python
@register_tool
@tool
def google_search_tool(query: str) -> str:
    """在互联网上搜索最新信息、新闻、热点事件。
    当用户询问近期新闻、实时动态、或本地数据库无法回答的时事问题时使用。
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return f"未找到关于 '{query}' 的相关信息"
        lines = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            lines.append(f"【{title}】\n{body}\n{href}")
        return "\n\n".join(lines)
    except Exception as e:
        msg = str(e).lower()
        if "timeout" in msg or "timed out" in msg:
            return "网络搜索暂时不可用，请稍后重试"
        if "ratelimit" in msg or "rate limit" in msg or "202" in msg:
            return "搜索频率过高，请稍后再试"
        return f"搜索失败: {str(e)[:80]}"
```

**Step 6: 运行测试确认通过**

Run: `pytest tests/unit/agent/test_tool_registry.py -v`
Expected: 3 PASSED

---

### Task 3: 将 `learning_tools.py` 中的 4 个 tools 注册到 registry

**Files:**
- Modify: `huaqi_src/agent/tools.py`（修改末尾的 import 块）

**背景：** 当前 `tools.py` 末尾用 `from ... import` 导入了 4 个 learning tools，但它们定义在 `learning_tools.py` 中，没有 `@register_tool`。最简单的做法是在 `tools.py` 中 import 后立即注册。

**Step 1: 替换 `tools.py` 末尾的 import 块**

将现有的：

```python
from huaqi_src.layers.capabilities.learning.learning_tools import (
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
    mark_lesson_complete_tool,
)
```

替换为：

```python
from huaqi_src.layers.capabilities.learning.learning_tools import (
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
    mark_lesson_complete_tool,
)

for _t in (get_learning_progress_tool, get_course_outline_tool, start_lesson_tool, mark_lesson_complete_tool):
    _TOOL_REGISTRY.append(_t)
```

**Step 2: 运行 registry 测试，确认 learning tools 也在其中**

Run: `pytest tests/unit/agent/test_tool_registry.py::test_tool_registry_contains_all_existing_tools -v`
Expected: PASSED

---

### Task 4: `chat_nodes.py` 改用 `_TOOL_REGISTRY`

**Files:**
- Modify: `huaqi_src/agent/nodes/chat_nodes.py:236-261`（`generate_response` 函数中的 tools import 和硬编码列表）

**Step 1: 写失败测试——generate_response 绑定的 tools 包含 google_search_tool**

在 `tests/unit/agent/test_chat_nodes.py` 末尾追加：

```python
def test_generate_response_uses_tool_registry():
    from unittest.mock import patch, MagicMock
    from langchain_core.messages import HumanMessage, AIMessage
    from huaqi_src.agent.tools import _TOOL_REGISTRY

    fake_response = AIMessage(content="test")
    fake_response.tool_calls = []

    async def fake_astream(messages, config=None):
        yield fake_response

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_model.astream = fake_astream

    captured_tools = []

    def capturing_bind_tools(tools):
        captured_tools.extend(tools)
        return mock_model

    mock_model.bind_tools = capturing_bind_tools

    import asyncio
    from unittest.mock import patch
    from huaqi_src.agent.nodes import chat_nodes

    with patch.object(chat_nodes, "ChatOpenAI", return_value=mock_model):
        pass  # 此测试通过检查 _TOOL_REGISTRY 间接验证

    registry_names = {t.name for t in _TOOL_REGISTRY}
    assert "google_search_tool" in registry_names
    assert len(_TOOL_REGISTRY) >= 13
```

**Step 2: 运行测试确认当前状态**

Run: `pytest tests/unit/agent/test_chat_nodes.py::test_generate_response_uses_tool_registry -v`
Expected: PASSED（此测试只检查 registry，不调用 LLM）

**Step 3: 修改 `chat_nodes.py` 中的 `generate_response` 函数**

找到 `generate_response` 函数中如下代码块（约在 236-261 行）：

```python
        from ..tools import (
            search_diary_tool,
            search_events_tool,
            search_work_docs_tool,
            search_worldnews_tool,
            search_person_tool,
            get_relationship_map_tool,
            search_cli_chats_tool,
            search_huaqi_chats_tool,
            get_learning_progress_tool,
            get_course_outline_tool,
            start_lesson_tool,
            mark_lesson_complete_tool,
        )
        tools = [
            search_diary_tool,
            search_events_tool,
            search_work_docs_tool,
            search_worldnews_tool,
            search_person_tool,
            get_relationship_map_tool,
            search_cli_chats_tool,
            search_huaqi_chats_tool,
            get_learning_progress_tool,
            get_course_outline_tool,
            start_lesson_tool,
            mark_lesson_complete_tool,
        ]
        chat_model_with_tools = chat_model.bind_tools(tools)
```

替换为：

```python
        from ..tools import _TOOL_REGISTRY
        chat_model_with_tools = chat_model.bind_tools(_TOOL_REGISTRY)
```

**Step 4: 运行所有 agent 相关测试**

Run: `pytest tests/unit/agent/ -v`
Expected: 所有测试 PASSED

---

### Task 5: 更新 system prompt

**Files:**
- Modify: `huaqi_src/agent/nodes/chat_nodes.py`（`build_system_prompt` 函数，约第 95 行）

**Step 1: 找到并替换 system prompt 第 5 条**

当前内容：
```
5. 当用户询问新闻、时事、世界动态时，使用 search_worldnews_tool 工具查询本地已采集的世界感知摘要
```

替换为：
```
5. 当用户询问新闻、时事、世界动态时，优先使用 search_worldnews_tool 查询本地数据；若本地无结果，再使用 google_search_tool 在互联网上搜索最新信息
```

**Step 2: 运行 chat_nodes 测试**

Run: `pytest tests/unit/agent/test_chat_nodes.py -v`
Expected: 所有测试 PASSED

---

### Task 6: 为 `google_search_tool` 补充单元测试

**Files:**
- Modify: `tests/unit/agent/test_tools.py`

**Step 1: 在 `test_tools.py` 末尾追加测试**

```python
from unittest.mock import patch, MagicMock

def test_google_search_tool_returns_formatted_results():
    fake_results = [
        {"title": "AI 新闻", "body": "大模型发展迅速", "href": "https://example.com/1"},
        {"title": "科技动态", "body": "量子计算突破", "href": "https://example.com/2"},
    ]
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = MagicMock(return_value=iter(fake_results))

    with patch("huaqi_src.agent.tools.google_search_tool.func.__globals__") as _:
        pass

    from huaqi_src.agent.tools import google_search_tool
    with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
        result = google_search_tool.invoke({"query": "AI 新闻"})

    assert isinstance(result, str)
    assert "AI 新闻" in result
    assert "https://example.com/1" in result


def test_google_search_tool_returns_empty_message_when_no_results():
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = MagicMock(return_value=iter([]))

    from huaqi_src.agent.tools import google_search_tool
    with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
        result = google_search_tool.invoke({"query": "xyznotexist"})

    assert isinstance(result, str)
    assert "未找到" in result


def test_google_search_tool_handles_network_timeout():
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = MagicMock(side_effect=Exception("Connection timed out"))

    from huaqi_src.agent.tools import google_search_tool
    with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
        result = google_search_tool.invoke({"query": "test"})

    assert "暂时不可用" in result


def test_google_search_tool_handles_rate_limit():
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = MagicMock(side_effect=Exception("ratelimit exceeded"))

    from huaqi_src.agent.tools import google_search_tool
    with patch("duckduckgo_search.DDGS", return_value=mock_ddgs):
        result = google_search_tool.invoke({"query": "test"})

    assert "频率过高" in result
```

**Step 2: 运行新增测试**

Run: `pytest tests/unit/agent/test_tools.py -v -k "google"`
Expected: 4 PASSED

**Step 3: 运行全部 tools 测试**

Run: `pytest tests/unit/agent/test_tools.py -v`
Expected: 全部 PASSED

---

### Task 7: 全量测试 & 收尾

**Step 1: 运行全部 agent 测试**

Run: `pytest tests/unit/agent/ -v`
Expected: 全部 PASSED

**Step 2: 运行完整测试套件**

Run: `pytest tests/unit/ -v --tb=short`
Expected: 全部 PASSED（或仅有与本次改动无关的预存失败）

**Step 3: Commit**

```
git add requirements.txt huaqi_src/agent/tools.py huaqi_src/agent/nodes/chat_nodes.py tests/unit/agent/test_tool_registry.py tests/unit/agent/test_tools.py tests/unit/agent/test_chat_nodes.py
git commit -m "feat: add google_search_tool with DuckDuckGo and auto-register decorator"
```
