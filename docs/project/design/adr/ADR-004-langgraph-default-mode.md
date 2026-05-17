# ADR-004: LangGraph Agent 作为默认对话模式

**状态**: 已采纳  
**日期**: 2026-03-29

## 背景

Phase 11 重构后，项目同时存在两套对话实现：

- **传统模式**（`chat_mode()`）：单文件 while 循环，直接调用自定义 `LLMManager`，流式输出通过 `chat_stream()` 实现，每次退出时保存对话
- **LangGraph 模式**（`run_langgraph_chat()`）：基于 `StateGraph` 的节点流水线，已有完整的意图识别、上下文构建、记忆检索、维度分析节点，但 `ChatAgent` 类未实现、`save_conversation` 为占位、`MemorySaver` 内存 checkpoint 重启丢失

需要决策：是否将 LangGraph 模式升级为默认，以及如何补全缺口。

## 决策

**将 LangGraph 模式设为默认**，补全以下缺口：

1. 实现 `ChatAgent` 类（流式输出 + 会话管理）
2. 将 `MemorySaver` 替换为 `AsyncSqliteSaver`（磁盘持久化）
3. 实现 `save_conversation` 节点（Markdown + Chroma 双写入）
4. `generate_response` 节点改用 LangChain `ChatOpenAI`（支持 `astream_events` 追踪）
5. 新增 `analyze_user_understanding` 节点
6. 激活 `memory_retriever` 的向量检索（`use_vector=True`）
7. CLI 新增 `--session`/`--list-sessions` 参数支持会话恢复

`huaqi` 和 `huaqi chat` 两个入口统一走 LangGraph 模式，通过 `--legacy` 参数可回退传统模式。

## 关键实现决策与踩坑

### AsyncSqliteSaver 的正确使用方式

`SqliteSaver`（同步版）不支持 LangGraph 的 async 方法（`aget_tuple`），必须用 `AsyncSqliteSaver`。

**错误用法：**
```python
# from_conn_string 返回 context manager，不是 AsyncSqliteSaver 实例
checkpointer = AsyncSqliteSaver.from_conn_string("path/to/db")  # ❌
```

**正确用法：**
```python
async with aiosqlite.connect(str(db_path)) as conn:
    checkpointer = AsyncSqliteSaver(conn)  # ✅
    graph = workflow.compile(checkpointer=checkpointer)
```

### aiosqlite 版本锁定

`aiosqlite >= 0.20` 移除了 `is_alive()` 方法，而 `langgraph-checkpoint-sqlite` 内部依赖此方法，导致 `AttributeError`。

锁定版本：`aiosqlite>=0.17.0,<0.20`

### async generator 与同步 CLI 的桥接

`ChatAgent.stream()` 是同步 generator（供 CLI 的 for 循环消费），内部需要驱动 `_astream()` 这个 async generator。

**错误用法（两种）：**
```python
# 方式 A：run_until_complete 无法驱动 async generator
yield from loop.run_until_complete(self._astream(user_input))  # ❌

# 方式 B：逐步 __anext__ 会导致 Event loop stopped before Future completed
chunk = loop.run_until_complete(agen.__anext__())  # ❌
```

**正确用法：在独立线程里跑完整 asyncio 事件循环，通过 Queue 传递 chunk：**
```python
def stream(self, user_input: str) -> Iterator[str]:
    _sentinel = object()
    q: queue.Queue = queue.Queue()

    async def _run():
        try:
            async for chunk in self._astream(user_input):
                q.put(chunk)
        finally:
            q.put(_sentinel)

    t = threading.Thread(target=lambda: asyncio.run(_run()), daemon=True)
    t.start()
    while True:
        item = q.get()
        if item is _sentinel:
            break
        yield item
    t.join()
```

### generate_response 节点必须用 LangChain Runnable

`astream_events` 只能追踪 LangChain 原生 Runnable（如 `ChatOpenAI`）产生的事件。自定义 `LLMManager` 不是 Runnable，不会产生 `on_chat_model_stream` 事件。

此外，节点必须是 **`async def`**，才能在内部 `await chat_model.ainvoke()`，让 LangGraph 正确追踪事件。

```python
async def generate_response(state: AgentState) -> Dict[str, Any]:
    chat_model = ChatOpenAI(streaming=True, ...)
    response = await chat_model.ainvoke(full_messages)  # ✅ async + LangChain Runnable
```

### on_chat_model_stream 事件的 fallback

在某些环境下（Python 3.9 + 特定 LangGraph 版本），即使节点正确调用了 `ChatOpenAI.ainvoke()`，`on_chat_model_stream` 事件也可能不被触发。需要 fallback 到 `on_chain_end` 取完整输出：

```python
async for event in graph.astream_events(...):
    kind = event.get("event", "")
    if kind == "on_chat_model_stream":
        # 优先：逐 token 流式输出
        yield chunk.content
    elif kind == "on_chain_end" and event.get("name") == "chat_response":
        # fallback：一次性输出完整回复
        if not collected_chunks:
            yield out.get("response", "")
```

### LLMManager 属性说明

- `_active_provider`：`BaseLLMProvider` 实例（对象），**不是**字符串
- `get_active_provider()`：返回当前激活的 provider 名称（字符串），用于查 `_configs`

```python
active_name = llm_mgr.get_active_provider()  # ✅ 字符串
cfg = llm_mgr._configs[active_name]           # ✅ 取配置
```

## 备选方案

**方案 A：继续用传统模式，仅修复「今天聊了什么」问题**  
不采纳。传统模式缺乏节点化的可扩展性，未来引入意图路由、记忆检索优化时改造成本更高。

**方案 B：用 SqliteSaver（同步版）**  
不采纳。LangGraph 内部使用 async 方法访问 checkpointer，同步版会抛出 `NotImplementedError`。

## 结果

- `huaqi` / `huaqi chat` 默认走 LangGraph 模式，流式输出正常
- 对话通过 `AsyncSqliteSaver` 持久化到 `{DATA_DIR}/checkpoints.db`，重启后会话可恢复
- 新增 `huaqi chat -l` 查看历史会话，`-s <thread_id>` 恢复指定会话
- `save_conversation` 节点同步写入 Markdown 存档和 Chroma 向量库
- `memory_retriever` 激活 Embedding 向量检索（`bge-small-zh`）

---

**文档版本**: v1.0  
**最后更新**: 2026-03-29
