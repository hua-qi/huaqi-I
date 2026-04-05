# LangGraph Agent 对话系统

## 概述

基于 LangGraph StateGraph 构建的对话流水线，替代原有的单文件 while 循环模式。支持意图识别、上下文构建、记忆检索、用户维度分析、流式回复、会话持久化（AsyncSqliteSaver）。

---

## 设计思路

传统 `chat_mode()` 将所有逻辑耦合在一个大循环中，难以独立测试和扩展。LangGraph 模式将对话拆分为独立节点，每个节点职责单一、可独立替换，状态通过 `AgentState` 在节点间传递，会话上下文通过 `AsyncSqliteSaver` 持久化到磁盘。

---

## 节点流水线

```
用户输入
    │
    ▼
intent_classifier      识别意图（规则匹配，默认 chat）
    │
    ▼
context_builder        构建系统提示词（5层：角色 + 人格 + 画像 + 状态 + 近期日记）
    │
    ▼
memory_retriever       双轨记忆检索（见下方"记忆检索"章节）
    │
    ▼
tools_node             LLM自发调用的交互工具节点（如 `search_diary_tool`, `search_huaqi_chats_tool`）
    │
    ▼
user_analyzer          维度分析（情绪/能量/焦虑/动机，写入 workflow_data）
    │
    ▼
chat_response          调用 LLM 生成回复（ChatOpenAI async，streaming=True）
    │
    ▼
save_conversation      持久化（Markdown 存档 + Chroma 向量索引）
    │
    ▼
[END]
```

---

## 实现细节

### ChatAgent

`huaqi_src/agent/chat_agent.py`

对外暴露同步接口，内部通过 `threading.Thread + queue.Queue` 桥接 async generator 和同步 generator：

```python
agent = ChatAgent()                    # 新建会话
agent = ChatAgent(thread_id="xxx")     # 恢复已有会话

for chunk in agent.stream("你好"):    # 流式输出
    print(chunk, end="", flush=True)

response = agent.run("你好")          # 非流式
```

会话元数据存储在 `{DATA_DIR}/sessions_index.yaml`，每轮对话后自动更新。

### AsyncSqliteSaver Checkpoint

每个节点执行后自动保存 `AgentState` 快照到 `{DATA_DIR}/checkpoints.db`。同一 `thread_id` 重启后可完整恢复上下文（含完整 messages 历史）。

**关键约束**：在 LangGraph >= 0.2.0 和最新的 langgraph-checkpoint-sqlite 中，**必须**使用 `AsyncSqliteSaver.from_conn_string(str(db_path))` 上下文管理器来初始化 checkpointer，不再支持直接传递 `aiosqlite.connect()` 实例。同时确保 `aiosqlite>=0.20.0`。

### 人机协同与中断恢复 (Human-in-the-loop)

支持在工作流的任意节点通过 `langgraph.types.interrupt` 抛出中断，将控制权交还给用户。
- 中断后状态会持久化保存在 Checkpointer 中。
- 用户通过 `huaqi resume <task_id> [response]` 命令恢复执行。
- 内部通过传递 `Command(resume=response)` 给 `astream_events` 来恢复对应的节点。

### generate_response 节点

必须是 `async def`，内部使用 `ChatOpenAI.ainvoke()`，才能被 `astream_events` 正确追踪。自定义 `LLMManager` 不是 LangChain Runnable，无法产生流式追踪事件。

LLM 配置从 `build_llm_manager()` 读取，转换为 `ChatOpenAI` 实例：

```python
active_name = llm_mgr.get_active_provider()   # 字符串 key
cfg = llm_mgr._configs[active_name]
chat_model = ChatOpenAI(
    model=cfg.model,
    api_key=cfg.api_key,
    base_url=cfg.api_base or None,
    temperature=1,           # 部分模型只支持 temperature=1
    max_tokens=cfg.max_tokens,
    streaming=True,
)
```

### save_conversation 节点

每次对话结束后执行双写入：

1. **Markdown**：`MarkdownMemoryStore.save_conversation()` → `{DATA_DIR}/memory/conversations/YYYY/MM/`
2. **Chroma**：`EmbeddingService.encode()` + `ChromaClient.add()` → `{DATA_DIR}/vector_db/`，每个对话回合作为一条向量记录

---

### 记忆检索（双轨制）

**问题背景**：Chroma 向量库在 `save_conversation`（对话结束）时才写入，因此同一天内其他 session 的对话不在向量库中，导致当日记忆"断层"。

**解决方案**：`memory_retriever` 节点采用双轨检索：

| 来源 | 覆盖范围 | 机制 |
|------|---------|------|
| Chroma 向量库 | 历史全量（跨天） | Embedding bge-small-zh + BM25 混合检索，top-3 |
| 今日 Markdown 扫描 | 当天所有 session | 2-gram 关键词宽松匹配，扫描 `YYYYMMDD_*.md` |

两路结果按前 60 字符去重，合并后取 top-5 注入 system prompt（每条截断 200 字、总量上限 1000 字）。

**工具层补充**：新增 `search_huaqi_chats_tool`，LLM 可在对话中按需调用，支持深度检索全部历史 Huaqi 对话（向量库 + Markdown 全文），适用于"你还记得...吗"类问题。

---

## Agent 工具列表

当前注册到 ToolNode 的全部工具：

| 工具名 | 触发语义 |
|--------|---------|
| `search_diary_tool` | 搜索历史日记 |
| `search_events_tool` | 搜索 CLI 交互事件记录 |
| `search_work_docs_tool` | 搜索工作文档 |
| `search_worldnews_tool` | 搜索近期世界新闻 |
| `search_person_tool` | 查询某人画像 |
| `get_relationship_map_tool` | 获取关系网络全图 |
| `search_cli_chats_tool` | 搜索与 CLI 工具的历史对话 |
| `search_huaqi_chats_tool` | 搜索与 Huaqi 的历史对话 |
| `get_learning_progress_tool` | 查询某技术的学习进度 |
| `get_course_outline_tool` | 获取某技术的课程大纲 |
| `start_lesson_tool` | 开始/继续学习某技术当前章节 |

---

## 接口与使用

### CLI 命令

```bash
huaqi                          # 新建会话（LangGraph 默认）
huaqi chat                     # 同上
huaqi chat --legacy            # 回退传统模式
huaqi chat -l                  # 列出最近 10 条历史会话
huaqi chat -s <thread_id>      # 恢复指定会话
```

### 对话中命令

| 命令 | 说明 |
|------|------|
| `/reset` | 新建会话（保留图实例，更换 thread_id） |
| `/state` | 查看当前会话 ID 和轮数 |
| `/clear` | 清屏 |
| `/help` | 显示帮助 |
| `exit` / `quit` | 退出 |

---

## 相关文件

- `huaqi_src/agent/chat_agent.py` - ChatAgent 主类（流式 + 会话管理）
- `huaqi_src/agent/graph/chat.py` - StateGraph 构建与编译（AsyncSqliteSaver）
- `huaqi_src/agent/nodes/chat_nodes.py` - 全部节点实现（含双轨记忆检索）
- `huaqi_src/agent/tools.py` - Agent 工具集（全部 @tool 定义与 re-export）
- `huaqi_src/agent/state.py` - AgentState TypedDict 定义
- `huaqi_src/cli/chat.py` - `run_langgraph_chat()` CLI 入口
- `huaqi_src/cli/__init__.py` - `--session`/`--list-sessions` 参数定义
- `huaqi_src/learning/learning_tools.py` - 学习助手工具（3 个 @tool）
- `docs/design/adr/ADR-004-langgraph-default-mode.md` - 架构决策与踩坑记录

---

**文档版本**: v1.2
**最后更新**: 2026-03-31
