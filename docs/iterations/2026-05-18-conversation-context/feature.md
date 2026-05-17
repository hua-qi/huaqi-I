# 对话上下文机制 (Conversation Context Assembly)

## 1. 概述 (Overview)

Huaqi (花旗) 作为一个追求“懂你”的长期数字同伴，其核心能力在于 Agent 在回复用户时能够**全面参考与用户相关的所有历史和即时信息**。
为了避免每次对话仅仅基于短期聊天记录，系统采用了“**被动上下文组装 + 被动记忆关联 + 主动工具检索**”的三层机制，确保大语言模型 (LLM) 能够感知用户的长期画像、当前情绪状态、过往经历以及特定记录。

## 2. 设计思路 (Design)

上下文的组装并非一次性将所有数据塞给大模型（这会导致 Context 溢出且注意力分散），而是通过 LangGraph 工作流中不同的节点分层处理：

1. **底层潜意识 (被动注入)**：将经过后台提炼的长期事实、偏好，以及用户当下的情绪状态，直接编译进 System Prompt 中。这构成了 Agent 的“潜意识”和“直觉”。
2. **近期记忆联想 (被动关联)**：通过向量数据库 (Chroma + BM25)，根据当前用户的发言，自动召回最近、最相关的几条历史对话。这构成了 Agent 的“短期联想”。
3. **深层查阅翻阅 (主动探索)**：当用户提及更久远、更具体的事物（例如某篇特定的日记、某个具体的技能练习记录）时，由于前两层可能无法覆盖这些长尾细节，Agent 拥有调用外部工具 (Tool Calling) 的能力，去直接检索 Markdown 文件并提取内容。

## 3. 实现细节 (Implementation details)

在 LangGraph 的每次对话循环中，上下文的构建与应用具体分为以下几个关键步骤：

### 3.1 被动注入：多维画像与当前状态组装 (`build_context` 节点)

在生成回复前，`build_context` 节点会将各类静态和动态数据拼装成 **系统提示词 (System Prompt)**：
- **长期用户画像 (User Profile)**：通过 `profile_manager.get_system_prompt_addition()` 获取。这部分包含了系统在后台悄悄提取并沉淀的关于用户的**事实、立场、偏好话题**等长期记忆。
- **短期动态理解 (Adaptive Insight)**：通过 `adaptive_understanding` 获取。系统会分析用户上一句话的**情绪状态、能量水平、焦虑度以及深层意图**，让 Agent 能感知用户“当下”的状态。
- **Agent 自身设定 (Personality)**：Agent 当前的人格设定（如陪伴者、导师等）以及语气要求。

### 3.2 被动关联：混合记忆检索 (`retrieve_memories` 节点)

- 提取用户最新的一句话作为 Query，去底层 Chroma 向量数据库 + BM25 文本库中进行**混合检索**。
- 检索到的最相关的 Top N 条历史对话记录（Recent Memories），会被直接追加到系统提示词的尾部，作为额外参考信息（如：“相关记忆：- 用户昨天提到过... - Huaqi 回复过...”）。

### 3.3 主动探索：Agentic Tool Calling (最新引入的特性)

当“被动”注入的信息无法回答具体问题时（例如用户问：“我去年写日记提到的 kaleido 是什么？”），单靠向量检索前几条对话可能查不到：
- 此时，绑定在 LLM 节点上的 `search_diary_tool` 等工具开始发挥作用。
- LLM 根据用户的问题主动生成 Tool Call，LangGraph 将流程路由至 `ToolNode`。
- `ToolNode` 在本地 Markdown 日记或成长记录中进行精准搜索，并将搜索结果返回给 LLM。
- LLM 最终综合所有的上下文（系统提示词、短期联想记忆、主动搜索得到的工具结果），生成最终的自然语言回复。

## 4. 总结与效果 (Conclusion)

工作流示意图：
```text
用户说话 
  ↓ 
分析情绪意图 (Adaptive Understanding)
  ↓ 
组装用户画像 (User Profile + Personality)
  ↓ 
向量搜索相似对话 (Chroma + BM25)
  ↓ 
交给 LLM
  ↓ 
（如需要则 LLM 主动调用搜索工具查日记/技能）
  ↓ 
LLM 综合所有上下文生成最终回复 
  ↓ 
提取新画像并保存
```

这种多层次的上下文组装设计，使得 Agent 既有“潜意识”的长期画像和情绪感知，又有“翻阅记忆”的主动检索能力，从而在有限的 Context Window 下实现了深度且连贯的陪伴体验。

## 5. 相关文件 (Related files)

- `huaqi_src/agent/nodes/chat_nodes.py`: `build_context` 和 `retrieve_memories` 的实现节点。
- `huaqi_src/agent/tools.py`: 主动检索工具的定义。
- `huaqi_src/core/adaptive_understanding.py`: 获取用户短期动态理解。
- `huaqi_src/core/profile_manager.py`: 获取用户长期画像系统提示词。

---
**文档版本**: v1.0
**生成时间**: 2026-03-29
