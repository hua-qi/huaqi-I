# 学习章节完成标记与实操支持

**Date:** 2026-01-04

## Context

当前学习助手 (`start_lesson_tool`) 只负责展示章节内容和练习题，但不会自动更新学习进度。用户即使学了大量内容，系统进度依然停在第 1 章（`0/9`）。根本原因是缺少一个让 Agent 和用户都能调用的「标记章节完成」机制。

## Discussion

**触发方式**

探讨了「用户主动说」、「答题后自动」、「两种都支持」三个选项，最终确定：**两种都支持**——Agent 可在评分通过后自动调用，用户也可随时手动触发。

**自动标记的条件**

讨论了「考题评分通过」、「只要回答了就算」、「用户自判」三种条件。最终确定：**考题评分通过（LLM 返回 `[PASS]` 标记）后自动标记**，但用户永远保有手动完成的权利。

**实操场景的处理**

对于需要项目实操的章节（如环境配置、实战项目），LLM 无法可靠地自动验证完成情况。探讨了三种思路：
1. 代码提交评审（LLM Code Review）
2. 用户自述完成（信任用户）
3. 章节类型区分，不同类型走不同判定逻辑

最终决定采用**思路 3 + 用户自判兜底**：按章节类型区分判定逻辑，但任何类型的章节用户都可以手动标记完成。

## Approach

引入 `mark_lesson_complete_tool` 作为独立工具，同时：

1. `generate_feedback` 在返回文本末尾附加 `[PASS]` 或 `[FAIL]` 标记，让 Agent 可靠判断是否通过
2. `LessonOutline` 新增 `lesson_type` 字段，大纲生成时同步生成每章类型
3. Agent 的 system prompt 约束调用时机，工具本身只负责标记，不做判断
4. 用户说「完成本章」「我会了」「下一章」等均可触发手动标记

**核心原则：用户永远有最终决定权。**

## Architecture

### 章节类型与完成判定矩阵

| 章节类型 | 自动触发（Agent 判定） | 手动触发（用户自判） |
|---------|----------------------|------------------|
| `quiz` 知识点 | 回答练习题，LLM 返回 `[PASS]` | 说「完成本章/我会了/下一章」 |
| `coding` 代码练习 | 粘贴代码，LLM Code Review 返回 `[PASS]` | 同上 |
| `project` 实操项目 | 不自动判定 | 同上（唯一方式） |

### 数据流

```
路径1（自动）：
  用户回答/粘贴代码
    → Agent 调用 generate_feedback
    → LLM 返回含 [PASS]/[FAIL] 的文本
    → Agent 解析到 [PASS] → 调用 mark_lesson_complete_tool(skill)

路径2（手动）：
  用户说「完成本章」「下一章」「我会了」等
    → Agent 直接调用 mark_lesson_complete_tool(skill)
```

### `mark_lesson_complete_tool` 接口

```python
@tool
def mark_lesson_complete_tool(skill: str) -> str:
    """标记当前章节为已完成，并自动推进到下一章。
    当满足以下任一条件时调用：
    1. 用户回答练习题且反馈包含 [PASS]
    2. 用户明确说「完成本章」「下一章」「继续」等
    """
```

返回示例：
```
✅ 第2章已完成！
下一章：第3章《列表推导式练习》
说「继续学」开始下一章
```

### 模型变更

`LessonOutline` 新增字段：
- `lesson_type: str`，枚举值 `quiz` / `coding` / `project`，默认 `quiz`（向后兼容）

`generate_outline` 需同步返回每章类型，例如：
```
第1章：Python 环境安装        → project
第2章：变量与数据类型          → quiz
第3章：列表推导式练习          → coding
第4章：文件读写实战项目        → project
```

### 涉及文件

| 文件 | 变更内容 |
|------|---------|
| `huaqi_src/learning/models.py` | `LessonOutline` 新增 `lesson_type` 字段 |
| `huaqi_src/learning/course_generator.py` | `generate_outline` 返回类型信息；`generate_feedback` 末尾附加 `[PASS]/[FAIL]` |
| `huaqi_src/learning/learning_tools.py` | 新增 `mark_lesson_complete_tool` |
| `huaqi_src/agent/tools.py` | 导出新工具 |
| `huaqi_src/agent/graph/chat.py` | 注册新工具到 `tools` 列表 |
| `huaqi_src/agent/nodes/chat_nodes.py` | `bind_tools` 中注册新工具 |
