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
memory_retriever       混合检索历史记忆（Embedding bge-small-zh + BM25，top-3）
    │
    ▼
tools_node             LLM自发调用的交互工具节点（如 `search_diary_tool`, `search_events_tool`）
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

**关键约束**：必须用 `aiosqlite.connect()` 创建连接，不能用 `from_conn_string()`（后者返回 context manager 不是实例）；`aiosqlite` 版本需锁定 `<0.20`（0.20+ 移除了内部依赖的 `is_alive()` 方法）。

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
- `huaqi_src/agent/nodes/chat_nodes.py` - 全部节点实现
- `huaqi_src/agent/state.py` - AgentState TypedDict 定义
- `huaqi_src/cli/chat.py` - `run_langgraph_chat()` CLI 入口
- `huaqi_src/cli/__init__.py` - `--session`/`--list-sessions` 参数定义
- `spec/decisions/ADR-004-langgraph-default-mode.md` - 架构决策与踩坑记录

---

**文档版本**: v1.0  
**最后更新**: 2026-03-29
