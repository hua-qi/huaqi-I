# 花旗学习助手

**Date:** 2026-03-31

## Context

用户已在 `growth.yaml` 中记录了自己想要学习的技术（skill 或 life_goals），但花旗目前只支持手动 `/log` 记录学习时间，没有任何主动辅助学习功能。核心诉求是：花旗能够根据用户指定的技术，主动帮助用户系统性地学习——生成结构化课程、讲解概念、出题考察、记录进度。

## Discussion

**核心问题：学习体验如何设计？**

- 学习应为「讲解 → 出题 → 答题反馈 → 进入下一章」的闭环循环，而不是单次问答
- 课程大纲由 LLM 根据技术名称动态生成（6-10 章，由浅入深），而非预置固定内容
- 进度需要持久化，支持跨会话继续学习

**触发方式：**

1. **对话嵌入**：用户在 `huaqi chat` 中说「继续学 Rust」，Agent 自动调用工具
2. **CLI 主动学习**：`huaqi study <技术名>` 进入专属学习模式
3. **定时推送**：每天晚上 9 点自动出一道复习题写入日志/通知

**存储方案选择：**

- 使用 YAML 存储课程大纲和进度（轻量、人类可读、与现有 growth.yaml 风格一致）
- 每次学习会话记录为 Markdown 文件
- 存储在 `{data_dir}/memory/learning/` 目录下

**不引入新依赖：** 复用现有 `langchain_openai`、`pyyaml`、APScheduler 体系，不增加任何三方库。

## Approach

新建 `huaqi_src/learning/` 模块，提供：

1. **数据层**：`models.py` + `progress_store.py` 负责课程/章节数据结构定义与 YAML 读写
2. **生成层**：`course_generator.py` 封装 4 个 LLM Prompt（大纲生成、章节讲解、出题、答题反馈）
3. **工具层**：`learning_tools.py` 暴露 3 个 LangChain Agent Tools，供对话自动调用
4. **CLI 层**：`commands/study.py` 实现 `huaqi study` 命令，支持列表、重置、进入学习模式
5. **调度层**：在 Scheduler 注册 `learning_daily_push` 每日推送任务

整体与现有 Agent Tools、Scheduler、CLI 体系无缝对接，不破坏现有数据结构。

## Architecture

### 目录结构

```
huaqi_src/learning/
├── __init__.py               # 导出 LearningProgressStore, CourseOutline, LessonOutline
├── models.py                 # LessonOutline, CourseOutline 数据类（含 to_dict/from_dict）
├── progress_store.py         # LearningProgressStore（YAML 读写、slugify、会话记录）
├── course_generator.py       # CourseGenerator（generate_outline/lesson/quiz/feedback）
└── learning_tools.py         # 3 个 @tool：get_learning_progress, get_course_outline, start_lesson
```

### 存储布局

```
{data_dir}/memory/learning/
├── courses/
│   └── {skill-slug}/
│       ├── outline.yaml        # 课程大纲 + 进度
│       └── lessons/
│           ├── 01-{name}.md
│           └── 02-{name}.md
└── sessions/
    └── {YYYYMMDD}_{skill}.md   # 每次学习会话记录
```

### outline.yaml 格式

```yaml
skill_name: "Rust"
slug: "rust"
created_at: "2026-03-31T00:00:00"
current_lesson: 1
total_lessons: 8
lessons:
  - index: 1
    title: "所有权（Ownership）"
    status: "completed"       # pending / in_progress / completed
    completed_at: "2026-03-31T10:00:00"
  - index: 2
    title: "借用（Borrowing）"
    status: "pending"
```

### LLM Prompt 体系

| Prompt | 用途 | 输出 |
|--------|------|------|
| `OUTLINE_PROMPT` | 为技术生成 6-10 章学习大纲 | 章节列表（纯文本） |
| `LESSON_PROMPT` | 讲解某章节（概念 + 原理 + 示例） | Markdown，≤300 字 |
| `QUIZ_PROMPT` | 出一道考题（编程语言优先出代码题） | 纯题目文本 |
| `FEEDBACK_PROMPT` | 对用户答题给出评价和补充说明 | 鼓励 + 纠错，≤150 字 |

### Agent Tools 注册

| Tool | 触发场景 |
|------|---------|
| `get_learning_progress_tool` | 「我学 XX 到哪了」「学习进度怎样」 |
| `get_course_outline_tool` | 「Rust 课程有哪些章节」「给我看学习计划」 |
| `start_lesson_tool` | 「继续学 Rust」「开始今天的学习」「出道题考我」 |

三个 Tool 注册到 `agent/tools.py`、`agent/graph/chat.py`、`agent/nodes/chat_nodes.py`。

### CLI 命令

```bash
huaqi study rust           # 生成大纲（首次）或进入学习对话模式
huaqi study --list         # 列出所有课程进度表格
huaqi study rust --reset   # 重置该课程进度
```

### 定时推送

- Cron：`0 21 * * *`（每天晚 9 点）
- 为进行中的课程（最多 2 门）各出一道复习题
- 写入日志，后续可扩展为 inbox 通知或系统推送

### 改动范围

| 文件 | 类型 |
|------|------|
| `huaqi_src/learning/` (5 个文件) | 新增模块 |
| `huaqi_src/cli/commands/study.py` | 新增 CLI 命令 |
| `huaqi_src/agent/tools.py` | 追加 3 行导入 |
| `huaqi_src/agent/graph/chat.py` | 追加 tools 注册 |
| `huaqi_src/agent/nodes/chat_nodes.py` | 修改 tools 列表 |
| `huaqi_src/cli/__init__.py` | 挂载 study 命令 |
| `huaqi_src/scheduler/handlers.py` | 追加推送处理函数 |
| `huaqi_src/scheduler/jobs.py` | 注册定时任务 |
| `tests/learning/` | 新增测试目录 |

**不引入任何新的第三方依赖。**
