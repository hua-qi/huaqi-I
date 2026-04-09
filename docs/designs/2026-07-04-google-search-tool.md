# Google Search Tool（互联网搜索能力）

**Date:** 2026-07-04

## Context

当用户向 Huaqi 询问"上周 AI 领域的热点新闻"之类的问题时，现有的 `search_worldnews_tool` 只能查询**本地已采集**的新闻数据。若本地没有相关记录，Huaqi 会无力地回答"我在系统里没有找到相关记录"，体验很差。

目标是为 Huaqi 补充一个能实时搜索互联网的 tool，让 LLM 在本地数据不足时可以主动出击，获取最新信息。

## Discussion

### 触发时机

确定由 **LLM 自主判断**何时调用该 tool，而非硬编码触发条件（如"本地无结果时自动降级"或"用户明确要求时"）。将判断权交给模型，通过 system prompt 引导其优先用本地数据、fallback 到 Google 搜索。

### 搜索 API 选型

对比了两个免费方案：

| 方案 | 返回内容 | 稳定性 | 与项目契合度 |
|------|----------|--------|-------------|
| `googlesearch-python` | 仅 URL 列表，需二次爬取正文 | 有被封 IP 风险，不适合生产 | 中 |
| `duckduckgo-search` | 直接返回标题 + 摘要 + URL | 官方支持，速率限制宽松 | 高（langchain 有原生集成） |

**最终选择 DuckDuckGo**，因为返回内容开箱即用（无需爬页面），且项目已依赖 langchain，零额外学习成本。

### Tool 动态加载优化

现有代码中所有 tools 在 `chat_nodes.py` 里硬编码为列表，每次新增 tool 需同时修改 `tools.py` 和 `chat_nodes.py`，容易遗漏。

对比了两种优化方式：
- **模块级列表**（`ALL_TOOLS = [...]`）：改动最小，但仍需手动维护列表
- **装饰器自动注册**（`@register_tool`）：定义时即注册，`chat_nodes` 零感知

**最终选择装饰器方案**，以后新增 tool 只需加 `@register_tool`，其他地方完全不用改。

## Approach

1. 在 `tools.py` 引入 `_TOOL_REGISTRY` 全局列表和 `register_tool` 装饰器
2. 所有现有 tools（包括 `learning_tools.py` 中的 4 个）补上 `@register_tool`
3. 新增 `google_search_tool`，使用 `duckduckgo-search` 实现
4. `chat_nodes.py` 中将硬编码 tools 列表替换为 `_TOOL_REGISTRY`
5. 更新 system prompt，引导 LLM 先查本地、再用互联网搜索
6. `requirements.txt` 新增 `duckduckgo-search`

## Architecture

### Tool 注册机制

```python
# tools.py
_TOOL_REGISTRY: list = []

def register_tool(fn):
    _TOOL_REGISTRY.append(fn)
    return fn

@register_tool
@tool
def google_search_tool(query: str) -> str:
    """在互联网上搜索最新信息、新闻、热点事件。
    当用户询问近期新闻、实时动态、或本地数据库无法回答的时事问题时使用。
    """
    ...
```

### chat_nodes 侧变更

```python
# chat_nodes.py
from ..tools import _TOOL_REGISTRY
chat_model_with_tools = chat_model.bind_tools(_TOOL_REGISTRY)
```

### 数据流

```
用户消息
  → LLM 判断是否需要搜索
  → 调用 google_search_tool(query)
  → DuckDuckGo 返回 [标题, 摘要, URL] × top-5
  → 格式化为可读文本
  → LLM 综合结果回答用户
```

### 错误处理

与现有 tools 风格一致，内部捕获所有异常，返回友好字符串，不向上抛：

| 场景 | 返回内容 |
|------|----------|
| 网络超时 | `"网络搜索暂时不可用，请稍后重试"` |
| 速率限制 | `"搜索频率过高，请稍后再试"` |
| 结果为空 | `"未找到关于 '{query}' 的相关信息"` |
| 其他异常 | `"搜索失败: {简短错误信息}"` |

### System Prompt 调整

将原有第 5 条职责描述从：
> 当用户询问新闻、时事、世界动态时，使用 `search_worldnews_tool` 工具查询本地已采集的世界感知摘要

修改为：
> 当用户询问新闻、时事、世界动态时，优先使用 `search_worldnews_tool` 查询本地数据；若本地无结果，再使用 `google_search_tool` 在互联网上搜索最新信息

### 变更文件汇总

| 文件 | 改动类型 |
|------|----------|
| `requirements.txt` | 新增 `duckduckgo-search` |
| `huaqi_src/agent/tools.py` | 新增 `_TOOL_REGISTRY`、`register_tool`；现有 tools 补 `@register_tool`；新增 `google_search_tool` |
| `huaqi_src/agent/nodes/chat_nodes.py` | tools 列表改用 `_TOOL_REGISTRY`；更新 system prompt |
