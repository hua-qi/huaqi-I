# Codeflicker Tool Calling Research Summary

## Overview

This research analyzes tool calling implementation in:
1. huaqi-growing project (Python + LangChain + LangGraph)
2. Codeflicker CLI (Node.js, architecture analysis)

## Key Findings

### 1. Tool Calling Architecture (3 Layers)

Layer 1: LLM Model Binding
  - chat_model.bind_tools(tools_registry)
  - Auto-generates JSON Schema for each tool
  - Injects tools array into API parameters

Layer 2: Tool Decision Making
  - LLM receives tools definition
  - Decides whether to call tools
  - Returns AIMessage with tool_calls field

Layer 3: Tool Execution & Result Injection
  - ToolNode executes tools automatically
  - Creates ToolMessage with results
  - Appends to message history

Layer 4: Response Generation
  - LLM sees complete message history
  - Generates final response with full context

### 2. Critical Code Pattern

File: huaqi_src/agent/nodes/chat_nodes.py (Line 244-265)

  chat_model_with_tools = chat_model.bind_tools(_TOOL_REGISTRY)
  
  async for chunk in chat_model_with_tools.astream(full_messages):
      response_msg = chunk if response_msg is None else response_msg + chunk
  
  return {
      'messages': [response_msg],  # Contains tool_calls if triggered
  }

### 3. How Tools Are Forced to Execute

NOT by hard parameters, but by System Prompt:

  'When user asks about news, MUST call search_worldnews_tool first;
   if result is empty, MUST call google_search_tool, DO NOT answer directly.'

This provides:
  ✓ Flexibility - LLM has agency
  ✓ Natural - Aligns with LLM design
  ✓ Debuggable - Easy to refine

### 4. Agent Loop Mechanism

File: huaqi_src/agent/graph/chat.py

  workflow.add_conditional_edges(
      'chat_response',
      tools_condition,  # Built-in LangGraph router
      {
          'tools': 'tools',             # If tool_calls exist
          '__end__': 'extract_user_info'  # Otherwise
      }
  )
  
  workflow.add_edge('tools', 'chat_response')  # Auto loop back

tools_condition automatically:
  - Checks if last message has tool_calls
  - Routes to tools node or ends
  - Prevents infinite loops

### 5. Tool Result Injection

Message evolution:

  Initial:  [SystemMessage, HumanMessage]
  
  After LLM:  [System, Human, AIMessage(tool_calls=[...])]
  
  After tools: [System, Human, AIMessage, ToolMessage(results)]
                                          ↑ Now visible to LLM
  
  Next LLM call: Uses complete history including tool results

### 6. Tool Registry Design

File: huaqi_src/agent/tools.py

  _TOOL_REGISTRY = []
  
  def register_tool(fn):
      _TOOL_REGISTRY.append(fn)
      return fn
  
  @register_tool
  @tool
  def search_diary_tool(query: str) -> str:
      """Search user's diary. Use when user asks about past."""
      # Implementation
      return results

13+ registered tools:
  - search_diary_tool
  - search_worldnews_tool
  - google_search_tool
  - search_person_tool
  - And more...

## Complete Tool Calling Loop Example

Input: 'search diary for kaleido'

Step 1: LLM Call
  Input: [System, HumanMessage]
  Output: AIMessage(tool_calls=[{name: search_diary_tool, args: {query: kaleido}}])

Step 2: tools_condition Check
  Has tool_calls? YES → route to tools node

Step 3: ToolNode Execution
  1. Find tool from registry: search_diary_tool
  2. Execute: search_diary_tool.invoke({query: kaleido})
  3. Create ToolMessage(content=results, tool_call_id=..., name=...)
  4. Append to messages

Step 4: tools_condition Check Again
  Has tool_calls? NO (last message is ToolMessage) → end routing

Step 5: Continue Flow
  Complete message history now visible to subsequent nodes

## Codeflicker CLI Architecture

Source: /usr/local/lib/node_modules/@ks-codeflicker/cli/
Status: Compiled to 9.3MB minified JavaScript

Likely implementation (based on design patterns):
  1. Tool Discovery: Internal registry + MCP protocol
  2. Schema Generation: JSON Schema from tool definitions
  3. API Integration: OpenAI/Claude function calling
  4. Tool Execution: Local (file ops) or remote RPC
  5. Result Injection: Tool Message → complete history

Similar concepts as huaqi-growing but in Node.js context.

## Key Parameters

| Parameter | Purpose | Current Setting |
|-----------|---------|-----------------|
| tools | API parameter with schemas | Auto-generated |
| tool_choice | LLM selection strategy | 'auto' (LLM decides) |
| system_prompt | Tool usage guidance | Natural language |
| tools_condition | Routing decision | LangGraph built-in |
| ToolNode | Tool execution | LangGraph built-in |

## Best Practices

1. Tool Definition
   ✓ Clear docstring (becomes schema description)
   ✓ Type hints define parameters
   ✓ Return string results
   ✓ Handle errors gracefully

2. System Prompt
   ✓ List all tools with purposes
   ✓ Specify when to call each
   ✓ Define error handling
   ✓ Keep concise and clear

3. Error Handling
   ✓ Never crash on execution failure
   ✓ Return error to ToolMessage
   ✓ Let LLM see and handle
   ✓ Implement retries if needed

## Conclusion

Tool calling in modern LLMs is about:
  1. Providing tools as capabilities
  2. Using prompts to guide intelligent usage
  3. Letting frameworks handle mechanics
  4. Maintaining complete conversation context

The huaqi-growing project exemplifies this perfectly with its:
  - Clean tool definitions (tools.py)
  - Explicit binding (bind_tools)
  - Natural language guidance (system prompt)
  - Automatic loop management (LangGraph)

Result: Flexible, maintainable, extensible agent system.

---
Research: 2026-08-04
Scope: huaqi-growing + Codeflicker CLI

