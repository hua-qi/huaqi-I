# Agent 记忆检索 (Agentic Memory Retrieval)

## 1. 概述 (Overview)

为了解决旧版基于规则匹配意图的僵化问题（如正则匹配遗漏、多维数据查询无法合并），引入了基于 **Tool Calling（工具调用）** 的 **Agentic Memory Retrieval**。
该方案允许 Agent（基于 LangGraph 的大语言模型节点）在对话中通过自主路由并调用检索工具，动态获取用户的多维历史数据（如日记、技能追踪、内容流水线），从而解决“记忆断层”现象，实现更加智能、连贯的同伴陪伴体验。

## 2. 设计思路 (Design)

采用 LangGraph 的 **ToolNode 范式**，摒弃或降级了原本独立且死板的 `classify_intent`（意图识别节点）。
核心设计：
1. 将本地检索工具（如 `search_diary_tool`）通过 `.bind_tools()` 方法绑定给主 LLM 节点。
2. LLM 会根据用户的当前输入与上下文，自主判断是否需要补充历史记忆。
3. 如果需要，LLM 返回对应的 `tool_calls`。LangGraph 中的条件路由（`tools_condition`）会拦截并进入 `ToolNode`。
4. `ToolNode` 执行具体的本地 Python 搜索逻辑后，将工具结果（ToolMessage）返回。
5. 工作流从 `tools` 节点环回 LLM 节点（`generate_response`），LLM 综合刚刚检索到的记忆内容，生成最终自然语言回复。

此设计的关键在于，**如何兼顾大语言模型在工具调用前与工具调用后、以及正常对话时的实时流式（Streaming）体验**。

## 3. 实现细节 (Implementation details)

1. **检索工具的封装 (`huaqi_src/agent/tools.py`)**：
   - 编写了 `search_diary_tool(query: str) -> str`。
   - 利用 `DiaryStore` 直接对 Markdown 文件进行检索。
   - 使用 `@tool` 装饰器使其成为 LangChain/LangGraph 兼容工具，并在 docstring 中提供详细的触发引导（例如“当用户询问过去发生的事情、特定的回忆或关键词（如 kaleido）时使用”）。

2. **流式输出与工具调用共存 (`huaqi_src/agent/nodes/chat_nodes.py`)**：
   - 放弃了仅为了简便而使用的 `ainvoke` 阻塞调用，保留了原有的 `chat_model.astream` 流式遍历。
   - 在迭代 `chunk` 时，不仅通过原有的 `LangChain` 事件总线进行流式抛出，同时利用 `AIMessageChunk` 的重载加法运算符 `+=` 将所有的 `chunk` 累加：
     ```python
     response_msg = None
     async for chunk in chat_model_with_tools.astream(full_messages, config=config):
         if response_msg is None:
             response_msg = chunk
         else:
             response_msg += chunk
     ```
   - 这样做的优势是：它既收集了纯文本流（`chunk.content`），也完美拼接并收集了流式工具调用片段（`chunk.tool_call_chunks`），使 LangGraph 可以正确识别完整的 `tool_calls`。

3. **LangGraph 路由构建 (`huaqi_src/agent/graph/chat.py`)**：
   - 引入 `ToolNode` 与 `tools_condition`。
   - **坑点与解决方案**：在应用 `tools_condition` 作为条件路由时，如果 LLM 没有决定调用工具，它默认会流向 `__end__`。为了不破坏我们原有的业务管道（生成回复后需要抽取画像与保存对话），我们**必须在映射表中显式地重写 `__end__`**，将其引导至下一步 `extract_user_info`：
     ```python
     workflow.add_conditional_edges(
         "chat_response",
         tools_condition,
         {
             "tools": "tools",
             "__end__": "extract_user_info"
         }
     )
     ```

## 4. 相关文件 (Related files)

- **核心实现**:
  - `huaqi_src/agent/tools.py`（工具定义）
  - `huaqi_src/agent/nodes/chat_nodes.py`（工具绑定与流式输出）
  - `huaqi_src/agent/graph/chat.py`（ToolNode 注册与条件路由）
- **单元测试**:
  - `tests/agent/test_tools.py`
  - `tests/agent/test_chat_nodes.py`
  - `tests/agent/test_graph.py`

---
> Version: 0.2.0-Agentic (2026-03-29)
