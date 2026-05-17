# 学习助手

## 概述

让用户通过对话或 CLI 触发系统性技术学习：LLM 自动生成课程大纲，逐章讲解，出题考察，进度持久化到本地 YAML 文件，并每晚定时推送复习题。用户回答练习题后，Agent 自动识别通过/失败状态并标记章节完成。

---

## 设计思路

用户学习技术时缺乏系统性引导——零散问 AI 效率低，记不住进度。学习助手将"学什么 → 讲解 → 考察 → 自动推进"封装为一个闭环：

- **大纲生成**：LLM 一次性生成 6-10 章由浅入深的课程大纲，并推断每章类型（quiz/coding/project），存入 YAML
- **按章推进**：每次对话只推进一章，降低认知负担
- **出题考察**：讲完立即出题，反馈末尾附加 `[PASS]`/`[FAIL]` 标记供 Agent 解析
- **自动标记**：Agent 检测到 `[PASS]` 或用户说"完成/下一章"时，调用 `mark_lesson_complete_tool` 自动推进
- **进度持久化**：章节状态（pending / in_progress / completed）落盘，跨 session 保持

---

## 模块结构

```
huaqi_src/learning/
├── __init__.py              # 导出 LessonOutline, CourseOutline, LearningProgressStore, slugify
├── models.py                # 数据模型（dataclass）
├── progress_store.py        # YAML 进度存储 + 会话 Markdown 归档
├── course_generator.py      # LLM 封装（5 个生成方法）
└── learning_tools.py        # 4 个 LangChain @tool，注册到 Agent
```

---

## 实现细节

### 数据模型（models.py）

```python
@dataclass
class LessonOutline:
    index: int
    title: str
    status: str = "pending"        # pending / in_progress / completed
    completed_at: Optional[str] = None
    lesson_type: str = "quiz"      # quiz / coding / project

@dataclass
class CourseOutline:
    skill_name: str
    slug: str
    lessons: List[LessonOutline]
    created_at: str
    current_lesson: int = 1        # __post_init__ 自动推断第一个未完成章节
```

两个类均实现 `to_dict()` / `from_dict()` 用于 YAML 序列化。`lesson_type` 向后兼容：旧 YAML 无此字段时默认 `"quiz"`。

### 进度存储（progress_store.py）

数据目录结构：

```
{data_dir}/learning/
├── courses/
│   └── <slug>/
│       ├── outline.yaml       # 课程大纲 + 章节进度
│       └── lessons/           # 预留（单章扩展内容）
└── sessions/
    └── YYYYMMDD_<slug>.md     # 每次学习会话的追加记录
```

核心方法：

| 方法 | 说明 |
|------|------|
| `save_course(course)` | 序列化为 YAML 写入 |
| `load_course(slug)` | 从 YAML 反序列化 |
| `list_courses()` | 列出全部课程 |
| `mark_lesson_complete(slug, index)` | 标记完成并推进 `current_lesson` |
| `save_session(...)` | 追加写入学习会话 Markdown |
| `slugify(name)` | 技术名称转 slug（`Python 3` → `python-3`）|

### LLM 生成器（course_generator.py）

封装 5 个 `ChatOpenAI.invoke()` 调用，均通过构造时注入 `llm` 参数（方便测试 Mock）：

| 方法 | Prompt 作用 |
|------|------------|
| `generate_outline(skill)` | 生成 6-10 章大纲，返回 `List[str]` |
| `generate_outline_with_types(skill)` | 同上并推断章节类型，返回 `List[tuple[str, str]]` |
| `generate_lesson(skill, chapter)` | 讲解一章，≤300 字 |
| `generate_quiz(skill, chapter)` | 出一道考题 |
| `generate_feedback(skill, chapter, quiz, answer, passed=None)` | 批改回答，100-150 字；`passed=True` 末尾追加 `[PASS]`，`passed=False` 追加 `[FAIL]` |

`generate_outline_with_types` 内置关键词推断规则：
- **project**：含"实战/项目/project/部署/安装/环境配置/搭建"
- **coding**：含"练习/coding/代码/编写/实现/写一个/刷题"
- **quiz**：默认（其余）

大纲解析支持两种格式：`第1章：标题` 和 `1. 标题`，均自动清理前缀。

### Agent 工具（learning_tools.py）

4 个 `@tool` 已注册到 LangGraph ToolNode：

| 工具名 | 触发语义 | 行为 |
|--------|---------|------|
| `get_learning_progress_tool` | 「我 Rust 学到哪了」 | 展示进度 + 章节列表 |
| `get_course_outline_tool` | 「Rust 课程有哪些章节」 | 展示大纲 |
| `start_lesson_tool` | 「继续学 Rust」「学 Python」 | 首次自动生成大纲（含 lesson_type）；推进当前章节，返回讲解 + 考题 |
| `mark_lesson_complete_tool` | 「完成本章」「下一章」「继续」；或反馈含 `[PASS]` | 标记当前章节完成，推进到下一章并提示 |

**工具注册位置（3 处需同步）：**
1. `huaqi_src/agent/tools.py` — re-export
2. `huaqi_src/agent/graph/chat.py` — `tools` 列表传入 `ToolNode`
3. `huaqi_src/agent/nodes/chat_nodes.py` — `bind_tools` 工具列表

---

## 接口与使用

### 通过 Agent 对话

```
用户：帮我开始学 Rust
→ Agent 调用 start_lesson_tool(skill="Rust")
→ 自动生成大纲，讲解第一章，给出考题

用户：[回答考题]
→ Agent 调用 generate_feedback(..., passed=True/False)
→ 反馈末尾含 [PASS] → Agent 自动调用 mark_lesson_complete_tool(skill="Rust")
→ 提示第1章完成，展示下一章信息

用户：我 Rust 学到哪了
→ Agent 调用 get_learning_progress_tool(skill="Rust")
→ 返回当前章节 + 进度列表
```

### CLI 命令

```bash
# 列出所有课程及进度
huaqi study --list

# 开始/继续学习（首次自动生成大纲）
huaqi study rust
huaqi study "Python 3"

# 重置课程进度（删除本地 YAML）
huaqi study --reset rust
```

### 定时推送

每晚 21:00，`learning_daily_push` 任务自动为进行中的课程（最多 2 门）生成复习题并打印。需通过 `huaqi daemon start` 启动后台服务。

---

## 相关文件

- `huaqi_src/learning/models.py` - 数据模型（含 `lesson_type`）
- `huaqi_src/learning/progress_store.py` - YAML 持久化 + Markdown 会话归档
- `huaqi_src/learning/course_generator.py` - LLM 5 个生成方法
- `huaqi_src/learning/learning_tools.py` - 4 个 @tool
- `huaqi_src/cli/commands/study.py` - `huaqi study` CLI 命令
- `huaqi_src/agent/tools.py` - 工具注册（末尾 re-export）
- `huaqi_src/agent/graph/chat.py` - ToolNode 工具列表
- `huaqi_src/agent/nodes/chat_nodes.py` - bind_tools 工具列表
- `huaqi_src/scheduler/jobs.py` - `_run_learning_push` + cron 注册
- `tests/learning/` - 全量单元测试（38 cases）

---

**文档版本**: v1.2
**最后更新**: 2026-01-04

让用户通过对话或 CLI 触发系统性技术学习：LLM 自动生成课程大纲，逐章讲解，出题考察，进度持久化到本地 YAML 文件，并每晚定时推送复习题。

---

## 设计思路

用户学习技术时缺乏系统性引导——零散问 AI 效率低，记不住进度。学习助手将"学什么 → 讲解 → 考察 → 记录"封装为一个闭环：

- **大纲生成**：LLM 一次性生成 6-10 章由浅入深的课程大纲，存入 YAML
- **按章推进**：每次对话只推进一章，降低认知负担
- **出题考察**：讲完立即出题，学完给反馈，形成记忆强化
- **进度持久化**：章节状态（pending / in_progress / completed）落盘，跨 session 保持

---

## 模块结构

```
huaqi_src/learning/
├── __init__.py              # 导出 LessonOutline, CourseOutline, LearningProgressStore, slugify
├── models.py                # 数据模型（dataclass）
├── progress_store.py        # YAML 进度存储 + 会话 Markdown 归档
├── course_generator.py      # LLM 封装（4 个生成方法）
└── learning_tools.py        # 3 个 LangChain @tool，注册到 Agent
```

---

## 实现细节

### 数据模型（models.py）

```python
@dataclass
class LessonOutline:
    index: int
    title: str
    status: str = "pending"        # pending / in_progress / completed
    completed_at: Optional[str] = None

@dataclass
class CourseOutline:
    skill_name: str
    slug: str
    lessons: List[LessonOutline]
    created_at: str
    current_lesson: int = 1        # __post_init__ 自动推断第一个未完成章节
```

两个类均实现 `to_dict()` / `from_dict()` 用于 YAML 序列化。

### 进度存储（progress_store.py）

数据目录结构：

```
{data_dir}/learning/
├── courses/
│   └── <slug>/
│       ├── outline.yaml       # 课程大纲 + 章节进度
│       └── lessons/           # 预留（单章扩展内容）
└── sessions/
    └── YYYYMMDD_<slug>.md     # 每次学习会话的追加记录
```

核心方法：

| 方法 | 说明 |
|------|------|
| `save_course(course)` | 序列化为 YAML 写入 |
| `load_course(slug)` | 从 YAML 反序列化 |
| `list_courses()` | 列出全部课程 |
| `mark_lesson_complete(slug, index)` | 标记完成并推进 `current_lesson` |
| `save_session(...)` | 追加写入学习会话 Markdown |
| `slugify(name)` | 技术名称转 slug（`Python 3` → `python-3`）|

### LLM 生成器（course_generator.py）

封装 4 个 `ChatOpenAI.invoke()` 调用，均通过构造时注入 `llm` 参数（方便测试 Mock）：

| 方法 | Prompt 作用 |
|------|------------|
| `generate_outline(skill)` | 生成 6-10 章大纲，返回 `List[str]` |
| `generate_lesson(skill, chapter)` | 讲解一章，≤300 字 |
| `generate_quiz(skill, chapter)` | 出一道考题 |
| `generate_feedback(skill, chapter, quiz, answer)` | 批改回答，100-150 字 |

大纲解析支持两种格式：`第1章：标题` 和 `1. 标题`，均自动清理前缀。

### Agent 工具（learning_tools.py）

3 个 `@tool` 已注册到 LangGraph ToolNode：

| 工具名 | 触发语义 | 行为 |
|--------|---------|------|
| `get_learning_progress_tool` | 「我 Rust 学到哪了」 | 展示进度 + 章节列表 |
| `get_course_outline_tool` | 「Rust 课程有哪些章节」 | 展示大纲 |
| `start_lesson_tool` | 「继续学 Rust」「学 Python」 | 首次自动生成大纲；推进当前章节，返回讲解 + 考题 |

---

## 接口与使用

### 通过 Agent 对话

```
用户：帮我开始学 Rust
→ Agent 调用 start_lesson_tool(skill="Rust")
→ 自动生成大纲，讲解第一章，给出考题

用户：我 Rust 学到哪了
→ Agent 调用 get_learning_progress_tool(skill="Rust")
→ 返回当前章节 + 进度列表
```

### CLI 命令

```bash
# 列出所有课程及进度
huaqi study --list

# 开始/继续学习（首次自动生成大纲）
huaqi study rust
huaqi study "Python 3"

# 重置课程进度（删除本地 YAML）
huaqi study --reset rust
```

### 定时推送

每晚 21:00，`learning_daily_push` 任务自动为进行中的课程（最多 2 门）生成复习题并打印。需通过 `huaqi daemon start` 启动后台服务。

---

## 相关文件

- `huaqi_src/learning/models.py` - 数据模型
- `huaqi_src/learning/progress_store.py` - YAML 持久化 + Markdown 会话归档
- `huaqi_src/learning/course_generator.py` - LLM 4 个生成方法
- `huaqi_src/learning/learning_tools.py` - 3 个 @tool
- `huaqi_src/cli/commands/study.py` - `huaqi study` CLI 命令
- `huaqi_src/agent/tools.py` - 工具注册（末尾 re-export）
- `huaqi_src/agent/graph/chat.py` - ToolNode 工具列表
- `huaqi_src/agent/nodes/chat_nodes.py` - bind_tools 工具列表
- `huaqi_src/scheduler/jobs.py` - `_run_learning_push` + cron 注册
- `tests/learning/` - 全量单元测试（28 cases）

---

**文档版本**: v1.1
**最后更新**: 2026-03-31
