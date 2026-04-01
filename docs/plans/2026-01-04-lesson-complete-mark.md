# 学习章节完成标记 Implementation Plan

**Goal:** 让 Agent 能在练习题通过后自动标记章节完成，同时支持用户手动触发，并推进到下一章节。

**Architecture:** 在 `LessonOutline` 上新增 `lesson_type` 字段区分章节类型；`generate_feedback` 在结尾附加 `[PASS]`/`[FAIL]` 标记供 Agent 解析；新增 `mark_lesson_complete_tool` 工具完成标记逻辑并注册到 Agent。

**Tech Stack:** Python dataclasses, LangChain `@tool`, LangGraph ToolNode, PyYAML, pytest + unittest.mock

---

## 背景知识（必读）

本计划涉及 3 层架构，理解调用链有助于避免漏改：

```
models.py          ← 数据结构 (dataclass)
course_generator.py ← LLM 生成器
progress_store.py  ← YAML 持久化
learning_tools.py  ← LangChain @tool 函数（Agent 调用入口）
agent/tools.py     ← 统一导出所有工具
agent/graph/chat.py ← 注册 tools 列表到 ToolNode
agent/nodes/chat_nodes.py ← generate_response 中 bind_tools
```

**关键约定：**
- `LessonOutline.status` 枚举：`"pending"` / `"in_progress"` / `"completed"`
- `CourseOutline.current_lesson` 会在 `__post_init__` 自动指向第一个非 completed 课时
- 工具函数必须用 `@tool` 装饰，才能被 LangGraph ToolNode 调用
- 新工具注册需同步修改 **3 处**：`learning_tools.py`、`agent/tools.py`、`agent/graph/chat.py` + `chat_nodes.py`

---

## Task 1: 给 LessonOutline 新增 lesson_type 字段

**Files:**
- Modify: `huaqi_src/learning/models.py`
- Test: `tests/learning/test_models.py`

### Step 1: 写失败测试

在 `tests/learning/test_models.py` 末尾追加：

```python
def test_lesson_outline_has_lesson_type():
    from huaqi_src.learning.models import LessonOutline
    lesson = LessonOutline(index=1, title="所有权")
    assert lesson.lesson_type == "quiz"


def test_lesson_outline_lesson_type_serialization():
    from huaqi_src.learning.models import LessonOutline
    lesson = LessonOutline(index=1, title="项目实战", lesson_type="project")
    d = lesson.to_dict()
    assert d["lesson_type"] == "project"
    restored = LessonOutline.from_dict(d)
    assert restored.lesson_type == "project"


def test_lesson_outline_lesson_type_default_on_load():
    from huaqi_src.learning.models import LessonOutline
    lesson = LessonOutline.from_dict({"index": 1, "title": "基础语法"})
    assert lesson.lesson_type == "quiz"
```

### Step 2: 运行测试确认失败

```bash
pytest tests/learning/test_models.py::test_lesson_outline_has_lesson_type -v
```

预期：`FAILED` — `TypeError: LessonOutline.__init__() got an unexpected keyword argument 'lesson_type'` 或 `AttributeError`

### Step 3: 修改 models.py

在 `huaqi_src/learning/models.py` 中，修改 `LessonOutline` 类：

```python
@dataclass
class LessonOutline:
    index: int
    title: str
    status: str = "pending"
    completed_at: Optional[str] = None
    lesson_type: str = "quiz"

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "title": self.title,
            "status": self.status,
            "completed_at": self.completed_at,
            "lesson_type": self.lesson_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LessonOutline":
        return cls(
            index=d["index"],
            title=d["title"],
            status=d.get("status", "pending"),
            completed_at=d.get("completed_at"),
            lesson_type=d.get("lesson_type", "quiz"),
        )
```

### Step 4: 运行测试确认通过

```bash
pytest tests/learning/test_models.py -v
```

预期：全部 `PASSED`

### Step 5: 提交

```bash
git add huaqi_src/learning/models.py tests/learning/test_models.py
git commit -m "feat: add lesson_type field to LessonOutline"
```

---

## Task 2: generate_outline 生成课程时同步推断章节类型

**Files:**
- Modify: `huaqi_src/learning/course_generator.py`
- Test: `tests/learning/test_course_generator.py`

### Step 1: 写失败测试

在 `tests/learning/test_course_generator.py` 末尾追加：

```python
def test_generate_outline_with_types_returns_tuples():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm(
        "Python 环境安装\n变量与数据类型\n列表推导式练习\n文件读写实战项目"
    )
    gen = CourseGenerator(llm=mock_llm)
    results = gen.generate_outline_with_types("Python")

    assert len(results) == 4
    for title, lesson_type in results:
        assert isinstance(title, str)
        assert lesson_type in ("quiz", "coding", "project")


def test_generate_outline_with_types_detects_project():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("实战项目：构建 Web 服务")
    gen = CourseGenerator(llm=mock_llm)
    results = gen.generate_outline_with_types("Go")

    assert results[0][1] == "project"


def test_generate_outline_with_types_detects_coding():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("代码练习：字符串处理")
    gen = CourseGenerator(llm=mock_llm)
    results = gen.generate_outline_with_types("Python")

    assert results[0][1] == "coding"
```

### Step 2: 运行测试确认失败

```bash
pytest tests/learning/test_course_generator.py::test_generate_outline_with_types_returns_tuples -v
```

预期：`FAILED` — `AttributeError: 'CourseGenerator' object has no attribute 'generate_outline_with_types'`

### Step 3: 在 course_generator.py 中新增方法

在 `CourseGenerator` 类末尾添加 `generate_outline_with_types` 方法（不改动原 `generate_outline`，保持向后兼容）：

```python
_PROJECT_KEYWORDS = ("实战", "项目", "project", "实操", "部署", "安装", "环境配置", "搭建")
_CODING_KEYWORDS = ("练习", "coding", "代码", "编写", "实现", "写一个", "刷题")

def _infer_lesson_type(self, title: str) -> str:
    title_lower = title.lower()
    for kw in self._PROJECT_KEYWORDS:
        if kw in title_lower:
            return "project"
    for kw in self._CODING_KEYWORDS:
        if kw in title_lower:
            return "coding"
    return "quiz"

def generate_outline_with_types(self, skill: str) -> List[tuple]:
    titles = self.generate_outline(skill)
    return [(title, self._infer_lesson_type(title)) for title in titles]
```

还需要在文件顶部的 `from typing import Any, List, Optional` 确认 `List` 已导入（已有，无需改动）。

### Step 4: 运行测试确认通过

```bash
pytest tests/learning/test_course_generator.py -v
```

预期：全部 `PASSED`

### Step 5: 提交

```bash
git add huaqi_src/learning/course_generator.py tests/learning/test_course_generator.py
git commit -m "feat: add generate_outline_with_types to CourseGenerator"
```

---

## Task 3: generate_feedback 末尾附加 [PASS]/[FAIL] 标记

**Files:**
- Modify: `huaqi_src/learning/course_generator.py`
- Test: `tests/learning/test_course_generator.py`

### Step 1: 写失败测试

在 `tests/learning/test_course_generator.py` 末尾追加：

```python
def test_generate_feedback_appends_pass_marker():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("回答正确！Rust 的所有权规则确保了内存安全。")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_feedback("Rust", "所有权", "以下代码...", "选项 A", passed=True)
    assert result.endswith("[PASS]")


def test_generate_feedback_appends_fail_marker():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("回答有误，注意借用规则...")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_feedback("Rust", "所有权", "以下代码...", "选项 B", passed=False)
    assert result.endswith("[FAIL]")


def test_generate_feedback_default_no_marker():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("回答正确！")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_feedback("Rust", "所有权", "以下代码...", "选项 A")
    assert isinstance(result, str)
```

### Step 2: 运行测试确认失败

```bash
pytest tests/learning/test_course_generator.py::test_generate_feedback_appends_pass_marker -v
```

预期：`FAILED` — `TypeError: generate_feedback() got an unexpected keyword argument 'passed'`

### Step 3: 修改 generate_feedback 方法签名

将 `course_generator.py` 中的 `generate_feedback` 方法替换为：

```python
def generate_feedback(self, skill: str, chapter: str, quiz: str, answer: str, passed: bool = None) -> str:
    llm = self._get_llm()
    prompt = FEEDBACK_PROMPT.format(skill=skill, chapter=chapter, quiz=quiz, answer=answer)
    response = llm.invoke(prompt)
    text = response.content.strip()
    if passed is True:
        return text + "\n\n[PASS]"
    if passed is False:
        return text + "\n\n[FAIL]"
    return text
```

### Step 4: 运行测试确认通过

```bash
pytest tests/learning/test_course_generator.py -v
```

预期：全部 `PASSED`

### Step 5: 提交

```bash
git add huaqi_src/learning/course_generator.py tests/learning/test_course_generator.py
git commit -m "feat: generate_feedback appends [PASS]/[FAIL] marker"
```

---

## Task 4: 实现 mark_lesson_complete_tool 工具

**Files:**
- Modify: `huaqi_src/learning/learning_tools.py`
- Test: `tests/learning/test_learning_tools.py`

### Step 1: 写失败测试

在 `tests/learning/test_learning_tools.py` 末尾追加：

```python
def test_mark_lesson_complete_tool_advances_to_next(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path

    store = _mock_store_with_course(tmp_path)

    from importlib import reload
    import huaqi_src.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.learning.learning_tools._get_store", return_value=store):
        result = lt.mark_lesson_complete_tool.invoke({"skill": "Rust"})

    assert isinstance(result, str)
    assert "完成" in result or "第" in result
    course = store.load_course("rust")
    assert course.lessons[0].status == "completed"


def test_mark_lesson_complete_tool_all_done(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.learning.models import CourseOutline, LessonOutline
    from huaqi_src.learning.progress_store import LearningProgressStore

    store = LearningProgressStore(tmp_path / "learning")
    course = CourseOutline(
        skill_name="Go",
        slug="go",
        lessons=[
            LessonOutline(index=1, title="基础语法", status="in_progress"),
        ],
        current_lesson=1,
    )
    store.save_course(course)

    from importlib import reload
    import huaqi_src.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.learning.learning_tools._get_store", return_value=store):
        result = lt.mark_lesson_complete_tool.invoke({"skill": "Go"})

    assert "完成" in result or "恭喜" in result


def test_mark_lesson_complete_tool_no_course(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.learning.progress_store import LearningProgressStore
    store = LearningProgressStore(tmp_path / "learning")

    from importlib import reload
    import huaqi_src.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.learning.learning_tools._get_store", return_value=store):
        result = lt.mark_lesson_complete_tool.invoke({"skill": "Rust"})

    assert "未找到" in result or "尚未" in result
```

### Step 2: 运行测试确认失败

```bash
pytest tests/learning/test_learning_tools.py::test_mark_lesson_complete_tool_advances_to_next -v
```

预期：`FAILED` — `AttributeError: module ... has no attribute 'mark_lesson_complete_tool'`

### Step 3: 在 learning_tools.py 末尾添加新工具

在 `huaqi_src/learning/learning_tools.py` 末尾追加：

```python
@tool
def mark_lesson_complete_tool(skill: str) -> str:
    """标记当前章节为已完成，并自动推进到下一章。
    当满足以下任一条件时调用：
    1. 用户回答练习题且反馈包含 [PASS]
    2. 用户明确说「完成本章」「下一章」「继续」「我会了」等
    """
    try:
        store = _get_store()
    except RuntimeError as e:
        return f"无法标记完成：{e}"

    slug = slugify(skill)
    course = store.load_course(slug)
    if course is None:
        return f"未找到「{skill}」的课程。可以说「开始学 {skill}」先生成课程大纲。"

    current_index = course.current_lesson
    current = next((l for l in course.lessons if l.index == current_index), None)
    if current is None:
        return f"🎉 「{skill}」课程已全部完成！共 {course.total_lessons} 章。"

    store.mark_lesson_complete(slug, current_index)
    course = store.load_course(slug)

    next_lesson = next(
        (l for l in course.lessons if l.status in ("pending", "in_progress")),
        None,
    )

    if next_lesson is None:
        return (
            f"🎉 恭喜！「{skill}」课程已全部完成！共 {course.total_lessons} 章。\n"
            f"你已掌握了「{skill}」的全部内容！"
        )

    lines = [
        f"✅ 第{current_index}章《{current.title}》已完成！",
        f"",
        f"下一章：第{next_lesson.index}章《{next_lesson.title}》",
        f"说「继续学」开始下一章",
    ]
    return "\n".join(lines)
```

### Step 4: 运行测试确认通过

```bash
pytest tests/learning/test_learning_tools.py -v
```

预期：全部 `PASSED`

### Step 5: 提交

```bash
git add huaqi_src/learning/learning_tools.py tests/learning/test_learning_tools.py
git commit -m "feat: add mark_lesson_complete_tool"
```

---

## Task 5: 将新工具注册到 Agent

**Files:**
- Modify: `huaqi_src/agent/tools.py:230-233`
- Modify: `huaqi_src/agent/graph/chat.py:19-23,79-91`
- Modify: `huaqi_src/agent/nodes/chat_nodes.py:363-380`
- Test: `tests/learning/test_agent_integration.py`

### Step 1: 写失败测试

在 `tests/learning/test_agent_integration.py` 末尾追加：

```python
def test_mark_lesson_complete_tool_registered():
    from huaqi_src.agent.tools import mark_lesson_complete_tool
    assert hasattr(mark_lesson_complete_tool, "invoke")
    assert mark_lesson_complete_tool.name == "mark_lesson_complete_tool"


def test_mark_lesson_complete_tool_in_chat_graph():
    from huaqi_src.agent.graph.chat import build_chat_graph
    graph = build_chat_graph()
    tool_names = [t.name for t in graph.nodes["tools"].runnable.tools]
    assert "mark_lesson_complete_tool" in tool_names
```

### Step 2: 运行测试确认失败

```bash
pytest tests/learning/test_agent_integration.py::test_mark_lesson_complete_tool_registered -v
```

预期：`FAILED` — `ImportError: cannot import name 'mark_lesson_complete_tool'`

### Step 3: 修改 agent/tools.py 的导入

将 `huaqi_src/agent/tools.py` 末尾的导入块替换为：

```python
from huaqi_src.learning.learning_tools import (
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
    mark_lesson_complete_tool,
)
```

### Step 4: 修改 agent/graph/chat.py 的导入

将 `chat.py` 的工具导入块（第 19-23 行）替换为：

```python
from ..tools import (
    search_diary_tool,
    search_events_tool,
    search_work_docs_tool,
    search_worldnews_tool,
    search_person_tool,
    get_relationship_map_tool,
    search_cli_chats_tool,
    search_huaqi_chats_tool,
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
    mark_lesson_complete_tool,
)
```

将 `chat.py` 中的 `tools` 列表（第 79-91 行）替换为：

```python
tools = [
    search_diary_tool,
    search_events_tool,
    search_work_docs_tool,
    search_worldnews_tool,
    search_person_tool,
    get_relationship_map_tool,
    search_cli_chats_tool,
    search_huaqi_chats_tool,
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
    mark_lesson_complete_tool,
]
```

### Step 5: 修改 chat_nodes.py 的 bind_tools

在 `huaqi_src/agent/nodes/chat_nodes.py` 中找到 `generate_response` 函数里的工具列表（约第 363-380 行），在其中加入 `mark_lesson_complete_tool`：

```python
from ..tools import (
    search_diary_tool,
    search_events_tool,
    search_huaqi_chats_tool,
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
    mark_lesson_complete_tool,
)
tools = [
    search_diary_tool,
    search_events_tool,
    search_huaqi_chats_tool,
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
    mark_lesson_complete_tool,
]
```

### Step 6: 运行测试确认通过

```bash
pytest tests/learning/test_agent_integration.py -v
```

预期：全部 `PASSED`

### Step 7: 运行完整测试套件确保无回归

```bash
pytest tests/learning/ -v
```

预期：全部 `PASSED`

### Step 8: 提交

```bash
git add huaqi_src/agent/tools.py huaqi_src/agent/graph/chat.py huaqi_src/agent/nodes/chat_nodes.py tests/learning/test_agent_integration.py
git commit -m "feat: register mark_lesson_complete_tool to agent"
```

---

## Task 6: 更新 start_lesson_tool 使其使用 lesson_type

**Files:**
- Modify: `huaqi_src/learning/learning_tools.py`
- Test: `tests/learning/test_learning_tools.py`

**目的：** 当 `generate_outline` 创建新课程时，同步写入每章的 `lesson_type`。

### Step 1: 写失败测试

在 `tests/learning/test_learning_tools.py` 末尾追加：

```python
def test_start_lesson_tool_saves_lesson_type(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.learning.progress_store import LearningProgressStore
    store = LearningProgressStore(tmp_path / "learning")

    mock_gen = MagicMock()
    mock_gen.generate_outline_with_types.return_value = [
        ("环境安装", "project"),
        ("变量类型", "quiz"),
        ("代码练习", "coding"),
    ]
    mock_gen.generate_lesson.return_value = "讲解内容"
    mock_gen.generate_quiz.return_value = "考题"

    from importlib import reload
    import huaqi_src.learning.learning_tools as lt
    reload(lt)
    with patch("huaqi_src.learning.learning_tools._get_store", return_value=store), \
         patch("huaqi_src.learning.learning_tools.CourseGenerator", return_value=mock_gen):
        lt.start_lesson_tool.invoke({"skill": "Python"})

    course = store.load_course("python")
    assert course.lessons[0].lesson_type == "project"
    assert course.lessons[1].lesson_type == "quiz"
    assert course.lessons[2].lesson_type == "coding"
```

### Step 2: 运行测试确认失败

```bash
pytest tests/learning/test_learning_tools.py::test_start_lesson_tool_saves_lesson_type -v
```

预期：`FAILED` — `assert course.lessons[0].lesson_type == "project"` fails（保存的是默认 `"quiz"`）

### Step 3: 修改 start_lesson_tool 中创建课程的逻辑

在 `learning_tools.py` 的 `start_lesson_tool` 函数中，找到这段代码：

```python
    if course is None:
        outline_titles = gen.generate_outline(skill)
        if not outline_titles:
            return f"生成「{skill}」课程大纲失败，请稍后重试。"
        lessons = [LessonOutline(index=i + 1, title=t) for i, t in enumerate(outline_titles)]
```

替换为：

```python
    if course is None:
        outline_with_types = gen.generate_outline_with_types(skill)
        if not outline_with_types:
            return f"生成「{skill}」课程大纲失败，请稍后重试。"
        lessons = [
            LessonOutline(index=i + 1, title=t, lesson_type=lt)
            for i, (t, lt) in enumerate(outline_with_types)
        ]
```

注意：`lt` 是变量名，不要与模块名冲突，可改为 `ltype`：

```python
    if course is None:
        outline_with_types = gen.generate_outline_with_types(skill)
        if not outline_with_types:
            return f"生成「{skill}」课程大纲失败，请稍后重试。"
        lessons = [
            LessonOutline(index=i + 1, title=title, lesson_type=ltype)
            for i, (title, ltype) in enumerate(outline_with_types)
        ]
```

### Step 4: 运行测试确认通过

```bash
pytest tests/learning/test_learning_tools.py -v
```

预期：全部 `PASSED`

### Step 5: 提交

```bash
git add huaqi_src/learning/learning_tools.py tests/learning/test_learning_tools.py
git commit -m "feat: start_lesson_tool saves lesson_type when creating new course"
```

---

## Task 7: 端到端验证（手动）

**不需要写代码，只需验证集成效果。**

### Step 1: 运行完整测试套件

```bash
pytest tests/learning/ -v
```

预期：全部 `PASSED`，共约 20+ 个测试。

### Step 2: 快速验证工具可导入

```bash
python -c "from huaqi_src.agent.tools import mark_lesson_complete_tool; print(mark_lesson_complete_tool.name)"
```

预期输出：`mark_lesson_complete_tool`

### Step 3: 最终提交（如需）

如果前面各 Task 已单独提交，则此步骤跳过。否则：

```bash
git add -A
git commit -m "feat: lesson complete mark - full implementation"
```

---

## 变更文件总览

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `huaqi_src/learning/models.py` | 修改 | `LessonOutline` 新增 `lesson_type` 字段 |
| `huaqi_src/learning/course_generator.py` | 修改 | 新增 `generate_outline_with_types`；`generate_feedback` 新增 `passed` 参数 |
| `huaqi_src/learning/learning_tools.py` | 修改 | 新增 `mark_lesson_complete_tool`；`start_lesson_tool` 使用 `lesson_type` |
| `huaqi_src/agent/tools.py` | 修改 | 导出 `mark_lesson_complete_tool` |
| `huaqi_src/agent/graph/chat.py` | 修改 | `tools` 列表新增 `mark_lesson_complete_tool` |
| `huaqi_src/agent/nodes/chat_nodes.py` | 修改 | `generate_response` 的工具绑定新增 `mark_lesson_complete_tool` |
| `tests/learning/test_models.py` | 修改 | 新增 `lesson_type` 相关测试 |
| `tests/learning/test_course_generator.py` | 修改 | 新增 `generate_outline_with_types` 和 `[PASS]/[FAIL]` 测试 |
| `tests/learning/test_learning_tools.py` | 修改 | 新增 `mark_lesson_complete_tool` 测试 |
| `tests/learning/test_agent_integration.py` | 修改 | 新增工具注册验证测试 |
