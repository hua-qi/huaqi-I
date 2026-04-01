# Huaqi 跨 Session 记忆召回 Implementation Plan

**Goal:** 让 huaqi 能记住并检索所有历史对话（包括当天的），无论是否在同一 session 内。

**Architecture:** 双轨制——自动层在每次对话开始时将语义相关历史注入 system prompt（Chroma 向量库 + 今天的 Markdown 文件直接扫描）；工具层新增 `search_huaqi_chats_tool` 供 LLM 按需深度搜索。两层改动都发生在现有的 LangGraph 工作流内，不引入新的依赖。

**Tech Stack:** Python, LangGraph, Chroma (已有), MarkdownMemoryStore (已有), pytest

---

## 背景：为什么今天的对话找不到

1. `retrieve_memories` 只查 Chroma 向量库，但向量库在 `save_conversation` 节点（对话**结束**时）才写入，所以**同一天内**其他 session 的对话不存在于向量库里。
2. 没有任何工具覆盖 `memory/conversations/` 目录（huaqi 自身对话存储路径）。
3. `search_events_tool` 搜索的是 CLI 命令事件库，不是 huaqi 对话。

---

## Task 1: 新增 `search_huaqi_chats_tool`

**Files:**
- Modify: `huaqi_src/agent/tools.py`
- Modify: `huaqi_src/agent/graph/chat.py`（注册工具）
- Test: `tests/agent/test_tools.py`

---

### Step 1: 写失败测试

在 `tests/agent/test_tools.py` 末尾追加：

```python
def test_search_huaqi_chats_tool_returns_string_when_no_data(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from importlib import reload
    import huaqi_src.agent.tools as tools_module
    reload(tools_module)
    from huaqi_src.agent.tools import search_huaqi_chats_tool
    result = search_huaqi_chats_tool.invoke({"query": "犯错"})
    assert isinstance(result, str)
    assert "未找到" in result


def test_search_huaqi_chats_tool_finds_content(tmp_path):
    import os
    from datetime import datetime
    from huaqi_src.memory.storage.markdown_store import MarkdownMemoryStore
    from huaqi_src.core import config_paths

    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    config_paths._USER_DATA_DIR = tmp_path

    store = MarkdownMemoryStore(tmp_path / "memory" / "conversations")
    store.save_conversation(
        session_id="test_session",
        timestamp=datetime.now(),
        turns=[{"user_message": "我犯错了", "assistant_response": "没关系的"}],
    )

    from importlib import reload
    import huaqi_src.agent.tools as tools_module
    reload(tools_module)
    from huaqi_src.agent.tools import search_huaqi_chats_tool
    result = search_huaqi_chats_tool.invoke({"query": "犯错"})
    assert isinstance(result, str)
    assert "犯错" in result or "找到" in result
```

### Step 2: 跑测试，确认失败

```bash
pytest tests/agent/test_tools.py::test_search_huaqi_chats_tool_returns_string_when_no_data -v
```

期望：`FAILED` — `ImportError: cannot import name 'search_huaqi_chats_tool'`

### Step 3: 实现工具

在 `huaqi_src/agent/tools.py` 末尾（`get_relationship_map_tool` 之后）追加：

```python
@tool
def search_huaqi_chats_tool(query: str) -> str:
    """搜索用户与 Huaqi 的历史对话记录。
    当用户询问「我之前说过什么」「你还记得...吗」「上次我们聊了什么」
    「今天我有没有提到...」等涉及过往 huaqi 对话的问题时使用。
    支持自然语言查询，也支持「今天」「昨天」「上周」等时间描述。
    """
    from pathlib import Path
    from huaqi_src.core.config_paths import get_data_dir
    from huaqi_src.memory.storage.markdown_store import MarkdownMemoryStore

    data_dir = get_data_dir()
    if data_dir is None:
        return f"未找到与 Huaqi 的历史对话（数据目录未设置）。"

    conversations_dir = Path(data_dir) / "memory" / "conversations"
    if not conversations_dir.exists():
        return f"未找到包含 '{query}' 的 Huaqi 对话记录。"

    store = MarkdownMemoryStore(conversations_dir)

    # 先尝试向量库（语义相关，覆盖久远记录）
    vector_results = []
    try:
        from huaqi_src.memory.vector import get_hybrid_search
        search = get_hybrid_search(use_vector=True, use_bm25=True)
        hits = search.search(query, top_k=3, doc_type="conversation")
        for h in hits:
            content = h.get("content", "")
            date = h.get("metadata", {}).get("date", "")
            if content:
                vector_results.append(f"[{date}]\n{content[:300]}")
    except Exception:
        pass

    # 全文搜索 Markdown（补充当天未入库的对话）
    markdown_results = []
    try:
        hits = store.search_conversations(query)
        for h in hits[:5]:
            date = h.get("created_at", "")[:10]
            context = h.get("context", "")
            if context:
                markdown_results.append(f"[{date}]\n{context[:300]}")
    except Exception:
        pass

    # 合并去重（以 [date]\n content 为 key 粗略去重）
    seen = set()
    all_results = []
    for r in vector_results + markdown_results:
        key = r[:80]
        if key not in seen:
            seen.add(key)
            all_results.append(r)

    if not all_results:
        return f"未找到包含 '{query}' 的 Huaqi 对话记录。"

    return "找到以下与 Huaqi 的历史对话：\n\n" + "\n---\n".join(all_results[:5])
```

### Step 4: 跑测试，确认通过

```bash
pytest tests/agent/test_tools.py::test_search_huaqi_chats_tool_returns_string_when_no_data tests/agent/test_tools.py::test_search_huaqi_chats_tool_finds_content -v
```

期望：`2 passed`

### Step 5: 注册工具到 Graph

在 `huaqi_src/agent/graph/chat.py` 中：

**位置 1** — 顶部 import 块，追加导入：
```python
from ..tools import (
    ...
    search_huaqi_chats_tool,   # 新增这一行
)
```

**位置 2** — `build_chat_graph()` 内的 `tools` 列表，追加：
```python
tools = [
    search_diary_tool,
    search_events_tool,
    search_work_docs_tool,
    search_worldnews_tool,
    search_person_tool,
    get_relationship_map_tool,
    search_cli_chats_tool,
    search_huaqi_chats_tool,   # 新增这一行
]
```

**位置 3** — `generate_response` 节点在 `chat_nodes.py` 里也有一个独立的工具绑定列表，同样追加：

在 `huaqi_src/agent/nodes/chat_nodes.py` 的 `generate_response` 函数内找到：
```python
from ..tools import search_diary_tool, search_events_tool
tools = [search_diary_tool, search_events_tool]
```
改为：
```python
from ..tools import search_diary_tool, search_events_tool, search_huaqi_chats_tool
tools = [search_diary_tool, search_events_tool, search_huaqi_chats_tool]
```

### Step 6: 跑全量工具测试

```bash
pytest tests/agent/test_tools.py -v
```

期望：全部 `passed`

---

## Task 2: 扩展自动层 `retrieve_memories`

**Files:**
- Modify: `huaqi_src/agent/nodes/chat_nodes.py`（`retrieve_memories` 函数）
- Test: `tests/agent/test_chat_nodes.py`

---

### Step 1: 查看现有测试文件

```bash
cat tests/agent/test_chat_nodes.py
```

了解现有测试的 fixture 结构，避免重复定义。

### Step 2: 写失败测试

在 `tests/agent/test_chat_nodes.py` 中追加（若文件不存在则创建）：

```python
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from langchain_core.messages import HumanMessage

from huaqi_src.agent.state import create_initial_state


def _make_state_with_query(query: str) -> dict:
    state = create_initial_state()
    state["messages"] = [HumanMessage(content=query)]
    return state


def test_retrieve_memories_includes_today_markdown(tmp_path):
    """当天的 Markdown 对话应被检索到，即使向量库为空"""
    from huaqi_src.memory.storage.markdown_store import MarkdownMemoryStore
    from huaqi_src.core import config_paths

    config_paths._USER_DATA_DIR = tmp_path

    store = MarkdownMemoryStore(tmp_path / "memory" / "conversations")
    store.save_conversation(
        session_id="today_session",
        timestamp=datetime.now(),
        turns=[{"user_message": "我合并错了分支", "assistant_response": "回滚即可"}],
    )

    # 向量库抛异常（模拟不可用）
    with patch("huaqi_src.agent.nodes.chat_nodes.get_hybrid_search", side_effect=Exception("no chroma")):
        from importlib import reload
        import huaqi_src.agent.nodes.chat_nodes as nodes
        reload(nodes)
        state = _make_state_with_query("我有没有说过合并分支的事")
        result = nodes.retrieve_memories(state)

    memories = result.get("recent_memories", [])
    assert len(memories) > 0
    assert any("合并" in m for m in memories)


def test_retrieve_memories_falls_back_gracefully(tmp_path):
    """当向量库和 Markdown 都不可用时，返回空列表而不报错"""
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path  # 空目录，无对话文件

    with patch("huaqi_src.agent.nodes.chat_nodes.get_hybrid_search", side_effect=Exception("no chroma")):
        from importlib import reload
        import huaqi_src.agent.nodes.chat_nodes as nodes
        reload(nodes)
        state = _make_state_with_query("随便什么内容")
        result = nodes.retrieve_memories(state)

    assert result == {"recent_memories": []}
```

### Step 3: 跑测试，确认失败

```bash
pytest tests/agent/test_chat_nodes.py::test_retrieve_memories_includes_today_markdown -v
```

期望：`FAILED` — `assert len(memories) > 0`（当前实现不扫描 Markdown）

### Step 4: 扩展 `retrieve_memories`

用以下代码**完整替换** `huaqi_src/agent/nodes/chat_nodes.py` 中的 `retrieve_memories` 函数：

```python
def retrieve_memories(state: AgentState) -> Dict[str, Any]:
    """检索记忆节点

    来源 1: Chroma 向量库（语义相关，覆盖历史）
    来源 2: 当天 Markdown 文件直接扫描（覆盖向量库尚未收录的今日对话）
    合并去重后注入 system prompt。
    """
    messages = state.get("messages", [])

    query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    if not query:
        return {"recent_memories": []}

    memories: List[str] = []

    # --- 来源 1: Chroma 向量库 ---
    try:
        from ...memory.vector import get_hybrid_search

        search = get_hybrid_search(use_vector=True, use_bm25=True)
        results = search.search(query, top_k=3)

        for r in results:
            content = r.get("content", "")
            if content:
                memories.append(content[:300])
    except Exception as e:
        logger.debug(f"向量库检索失败: {e}")

    # --- 来源 2: 今天的 Markdown 文件扫描 ---
    try:
        from datetime import date as _date
        from ...core.config_paths import get_data_dir
        from ...memory.storage.markdown_store import MarkdownMemoryStore

        data_dir = get_data_dir()
        if data_dir is not None:
            conversations_dir = data_dir / "memory" / "conversations"
            store = MarkdownMemoryStore(conversations_dir)

            today_str = _date.today().strftime("%Y%m%d")
            today_dir = conversations_dir / _date.today().strftime("%Y/%m")

            if today_dir.exists():
                query_lower = query.lower()
                for md_file in sorted(today_dir.glob(f"{today_str}_*.md"), reverse=True)[:20]:
                    try:
                        content = md_file.read_text(encoding="utf-8")
                        if query_lower in content.lower():
                            # 提取命中片段（前后 2 行）
                            lines = content.split("\n")
                            snippet_lines: List[str] = []
                            for i, line in enumerate(lines):
                                if query_lower in line.lower():
                                    start = max(0, i - 2)
                                    end = min(len(lines), i + 3)
                                    snippet_lines.extend(lines[start:end])
                                    snippet_lines.append("...")
                                    if len(snippet_lines) > 15:
                                        break
                            snippet = "\n".join(snippet_lines[:15]).strip()
                            if snippet:
                                date_label = md_file.stem[:8]
                                memories.append(f"[今天 {date_label[4:6]}/{date_label[6:8]}]\n{snippet[:250]}")
                    except Exception:
                        continue
    except Exception as e:
        logger.debug(f"Markdown 今日记忆扫描失败: {e}")

    # 去重（按前 60 字符粗略去重）
    seen: set = set()
    unique_memories: List[str] = []
    for m in memories:
        key = m[:60]
        if key not in seen:
            seen.add(key)
            unique_memories.append(m)

    return {"recent_memories": unique_memories[:5]}
```

### Step 5: 跑测试，确认通过

```bash
pytest tests/agent/test_chat_nodes.py::test_retrieve_memories_includes_today_markdown tests/agent/test_chat_nodes.py::test_retrieve_memories_falls_back_gracefully -v
```

期望：`2 passed`

---

## Task 3: 注入格式优化（Token 防超限）

**Files:**
- Modify: `huaqi_src/agent/nodes/chat_nodes.py`（`generate_response` 函数内的 memory 注入逻辑）

**无需新测试**——这是格式调整，已有集成测试覆盖。

### Step 1: 修改注入格式

在 `generate_response` 函数内找到：

```python
if memories:
    memory_text = "\n\n相关记忆：\n" + "\n".join([f"- {m}" for m in memories])
    system_prompt += memory_text
```

替换为：

```python
if memories:
    # 每条截断到 200 字符，总量不超过 1000 字符
    trimmed = [m[:200] for m in memories]
    combined = "\n".join([f"- {m}" for m in trimmed])
    if len(combined) > 1000:
        combined = combined[:1000] + "\n...(记忆截断)"
    system_prompt += f"\n\n相关历史记忆（自动检索）：\n{combined}"
```

### Step 2: 跑完整 agent 测试

```bash
pytest tests/agent/ -v
```

期望：全部 `passed`

---

## Task 4: 回归验证

### Step 1: 跑全量测试

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```

期望：无新增失败项。

### Step 2: 手动冒烟测试

启动 huaqi，进行以下两步验证：

**验证自动层：**
1. 在 session A 聊：`今天我踩了一个 git 的坑`
2. 退出，开一个新 session B
3. 问：`我今天聊过什么`
4. 预期：花期能主动提到 git 的内容，无需用户追问

**验证工具层：**
1. 在新 session 问：`我之前有没有提到过合并分支的事`
2. 预期：花期调用 `search_huaqi_chats_tool` 并返回历史记录

---

## 改动范围汇总

| 文件 | 改动类型 | 关键变更 |
|------|---------|---------|
| `huaqi_src/agent/tools.py` | 新增函数 | `search_huaqi_chats_tool` |
| `huaqi_src/agent/graph/chat.py` | 追加一行 | 工具注册到 `ToolNode` |
| `huaqi_src/agent/nodes/chat_nodes.py` | 修改两处 | `retrieve_memories` 扩展 + `generate_response` 注入格式 + 工具导入 |
| `tests/agent/test_tools.py` | 追加测试 | 2 个新测试用例 |
| `tests/agent/test_chat_nodes.py` | 追加测试 | 2 个新测试用例 |

**不引入任何新的第三方依赖。**
