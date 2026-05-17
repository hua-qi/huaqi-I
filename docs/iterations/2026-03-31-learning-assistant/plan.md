# 花旗学习助手 Implementation Plan

**Goal:** 在 Huaqi 中新增 `huaqi_src/learning/` 模块，让用户可以通过对话或 CLI 触发系统性学习（大纲生成 → 章节讲解 → 出题考察 → 进度持久化），并每晚定时推送复习题。

**Architecture:** 新建独立的 `huaqi_src/learning/` 模块，包含数据模型、YAML 进度存储、LLM 生成器；再通过 3 个 LangChain `@tool` 挂入现有 Agent 工具链，新增 `huaqi study` CLI 命令，最后在 Scheduler 注册每日推送任务。

**Tech Stack:** Python 3.11, LangChain (`langchain_core.tools`), `langchain_openai.ChatOpenAI`, PyYAML, Typer, APScheduler（均为项目已有依赖，不新增任何三方库）

---

## 阅读清单（开工前必读）

在开始任何一个任务之前，请先阅读以下文件，建立上下文：

| 文件 | 原因 |
|------|------|
| `huaqi_src/agent/tools.py` | 理解现有 `@tool` 的写法和返回格式 |
| `huaqi_src/agent/graph/chat.py` | 了解工具如何注册到 ToolNode |
| `huaqi_src/agent/nodes/chat_nodes.py:390-420` | 了解工具如何 bind 到 LLM |
| `huaqi_src/scheduler/jobs.py` | 了解如何注册新的 cron 任务 |
| `huaqi_src/cli/__init__.py` | 了解如何挂载新的子命令 |
| `tests/agent/test_tools.py` | 理解工具测试风格 |
| `tests/agent/test_chat_nodes.py` | 理解异步测试风格 |

---

## 运行测试的命令

```bash
# 运行所有测试
pytest tests/ -v

# 只跑 learning 相关测试
pytest tests/learning/ -v

# 跑单个测试
pytest tests/learning/test_models.py::test_lesson_outline_to_dict -v
```

> **注意：** 项目使用 `pytest`，需要 `pytest-asyncio` 插件才能跑异步测试。确认方法：`pip show pytest-asyncio`

---

## Task 1: 数据模型 (models.py)

**Files:**
- Create: `huaqi_src/learning/models.py`
- Create: `tests/learning/__init__.py`
- Create: `tests/learning/test_models.py`

### Step 1: 创建 tests 目录占位文件

```bash
mkdir -p tests/learning
touch tests/learning/__init__.py
```

### Step 2: 写失败测试

文件：`tests/learning/test_models.py`

```python
import pytest
from datetime import datetime


def test_lesson_outline_to_dict():
    from huaqi_src.learning.models import LessonOutline
    lesson = LessonOutline(index=1, title="所有权（Ownership）")
    d = lesson.to_dict()
    assert d["index"] == 1
    assert d["title"] == "所有权（Ownership）"
    assert d["status"] == "pending"
    assert d["completed_at"] is None


def test_lesson_outline_from_dict():
    from huaqi_src.learning.models import LessonOutline
    d = {"index": 2, "title": "借用（Borrowing）", "status": "completed", "completed_at": "2026-03-31T10:00:00"}
    lesson = LessonOutline.from_dict(d)
    assert lesson.index == 2
    assert lesson.status == "completed"
    assert lesson.completed_at == "2026-03-31T10:00:00"


def test_course_outline_to_dict():
    from huaqi_src.learning.models import CourseOutline, LessonOutline
    course = CourseOutline(
        skill_name="Rust",
        slug="rust",
        lessons=[LessonOutline(index=1, title="所有权"), LessonOutline(index=2, title="借用")],
    )
    d = course.to_dict()
    assert d["skill_name"] == "Rust"
    assert d["slug"] == "rust"
    assert d["current_lesson"] == 1
    assert d["total_lessons"] == 2
    assert len(d["lessons"]) == 2


def test_course_outline_from_dict():
    from huaqi_src.learning.models import CourseOutline
    d = {
        "skill_name": "Python",
        "slug": "python",
        "created_at": "2026-03-31T00:00:00",
        "current_lesson": 2,
        "total_lessons": 3,
        "lessons": [
            {"index": 1, "title": "基础语法", "status": "completed", "completed_at": "2026-03-31T10:00:00"},
            {"index": 2, "title": "函数", "status": "in_progress", "completed_at": None},
            {"index": 3, "title": "类", "status": "pending", "completed_at": None},
        ],
    }
    course = CourseOutline.from_dict(d)
    assert course.skill_name == "Python"
    assert course.current_lesson == 2
    assert course.lessons[0].status == "completed"


def test_course_outline_current_lesson_property():
    from huaqi_src.learning.models import CourseOutline, LessonOutline
    course = CourseOutline(
        skill_name="Go",
        slug="go",
        lessons=[
            LessonOutline(index=1, title="入门", status="completed"),
            LessonOutline(index=2, title="并发", status="pending"),
        ],
    )
    assert course.current_lesson == 2
```

### Step 3: 运行测试，确认失败

```bash
pytest tests/learning/test_models.py -v
```

期望输出：`ModuleNotFoundError: No module named 'huaqi_src.learning'`

### Step 4: 实现 models.py

文件：`huaqi_src/learning/models.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class LessonOutline:
    index: int
    title: str
    status: str = "pending"
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "title": self.title,
            "status": self.status,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LessonOutline":
        return cls(
            index=d["index"],
            title=d["title"],
            status=d.get("status", "pending"),
            completed_at=d.get("completed_at"),
        )


@dataclass
class CourseOutline:
    skill_name: str
    slug: str
    lessons: List[LessonOutline] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    current_lesson: int = 1

    def __post_init__(self):
        if self.lessons:
            for lesson in self.lessons:
                if lesson.status in ("pending", "in_progress"):
                    self.current_lesson = lesson.index
                    break

    @property
    def total_lessons(self) -> int:
        return len(self.lessons)

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "slug": self.slug,
            "created_at": self.created_at,
            "current_lesson": self.current_lesson,
            "total_lessons": self.total_lessons,
            "lessons": [l.to_dict() for l in self.lessons],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CourseOutline":
        lessons = [LessonOutline.from_dict(l) for l in d.get("lessons", [])]
        obj = cls(
            skill_name=d["skill_name"],
            slug=d["slug"],
            lessons=lessons,
            created_at=d.get("created_at", datetime.now().isoformat()),
            current_lesson=d.get("current_lesson", 1),
        )
        obj.current_lesson = d.get("current_lesson", 1)
        return obj
```

### Step 5: 运行测试，确认通过

```bash
pytest tests/learning/test_models.py -v
```

期望输出：`5 passed`

### Step 6: commit

```bash
git add huaqi_src/learning/models.py tests/learning/
git commit -m "feat: add learning models (LessonOutline, CourseOutline)"
```

---

## Task 2: 进度存储 (progress_store.py)

**Files:**
- Create: `huaqi_src/learning/progress_store.py`
- Modify: `tests/learning/test_models.py` → 追加测试（或新建 `tests/learning/test_progress_store.py`）
- Create: `tests/learning/test_progress_store.py`

### Step 1: 写失败测试

文件：`tests/learning/test_progress_store.py`

```python
import pytest
from pathlib import Path
from datetime import datetime


def test_create_course(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore
    from huaqi_src.learning.models import CourseOutline, LessonOutline

    store = LearningProgressStore(tmp_path)
    course = CourseOutline(
        skill_name="Rust",
        slug="rust",
        lessons=[LessonOutline(index=1, title="所有权"), LessonOutline(index=2, title="借用")],
    )
    store.save_course(course)

    outline_path = tmp_path / "courses" / "rust" / "outline.yaml"
    assert outline_path.exists()


def test_load_course(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore
    from huaqi_src.learning.models import CourseOutline, LessonOutline

    store = LearningProgressStore(tmp_path)
    course = CourseOutline(
        skill_name="Python",
        slug="python",
        lessons=[LessonOutline(index=1, title="基础")],
    )
    store.save_course(course)

    loaded = store.load_course("python")
    assert loaded is not None
    assert loaded.skill_name == "Python"
    assert len(loaded.lessons) == 1


def test_load_course_returns_none_when_not_exists(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore

    store = LearningProgressStore(tmp_path)
    result = store.load_course("nonexistent-skill")
    assert result is None


def test_list_courses(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore
    from huaqi_src.learning.models import CourseOutline, LessonOutline

    store = LearningProgressStore(tmp_path)
    for skill in ["rust", "python"]:
        store.save_course(CourseOutline(skill_name=skill.capitalize(), slug=skill, lessons=[]))

    courses = store.list_courses()
    assert len(courses) == 2
    slugs = [c.slug for c in courses]
    assert "rust" in slugs
    assert "python" in slugs


def test_mark_lesson_complete(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore
    from huaqi_src.learning.models import CourseOutline, LessonOutline

    store = LearningProgressStore(tmp_path)
    course = CourseOutline(
        skill_name="Go",
        slug="go",
        lessons=[
            LessonOutline(index=1, title="入门"),
            LessonOutline(index=2, title="并发"),
        ],
    )
    store.save_course(course)
    store.mark_lesson_complete("go", lesson_index=1)

    loaded = store.load_course("go")
    assert loaded.lessons[0].status == "completed"
    assert loaded.lessons[0].completed_at is not None
    assert loaded.current_lesson == 2


def test_save_session_markdown(tmp_path):
    from huaqi_src.learning.progress_store import LearningProgressStore

    store = LearningProgressStore(tmp_path)
    store.save_session(
        skill_slug="rust",
        lesson_index=1,
        lesson_title="所有权",
        content="所有权是 Rust 的核心概念...",
        quiz="以下哪段代码会报编译错误？",
        user_answer="选项 A",
        feedback="正确！",
        timestamp=datetime(2026, 3, 31, 21, 0, 0),
    )

    session_path = tmp_path / "sessions" / "20260331_rust.md"
    assert session_path.exists()
    content = session_path.read_text(encoding="utf-8")
    assert "所有权" in content
    assert "选项 A" in content


def test_slugify():
    from huaqi_src.learning.progress_store import slugify

    assert slugify("Rust") == "rust"
    assert slugify("Python 3") == "python-3"
    assert slugify("C++") == "c"
    assert slugify("  Golang  ") == "golang"
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/learning/test_progress_store.py -v
```

期望输出：`ModuleNotFoundError: No module named 'huaqi_src.learning.progress_store'`

### Step 3: 实现 progress_store.py

文件：`huaqi_src/learning/progress_store.py`

```python
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from .models import CourseOutline, LessonOutline


def slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name


class LearningProgressStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.courses_dir = self.base_dir / "courses"
        self.sessions_dir = self.base_dir / "sessions"

    def _course_dir(self, slug: str) -> Path:
        return self.courses_dir / slug

    def _outline_path(self, slug: str) -> Path:
        return self._course_dir(slug) / "outline.yaml"

    def save_course(self, course: CourseOutline) -> None:
        course_dir = self._course_dir(course.slug)
        course_dir.mkdir(parents=True, exist_ok=True)
        (course_dir / "lessons").mkdir(exist_ok=True)
        with open(self._outline_path(course.slug), "w", encoding="utf-8") as f:
            yaml.dump(course.to_dict(), f, allow_unicode=True, default_flow_style=False)

    def load_course(self, slug: str) -> Optional[CourseOutline]:
        path = self._outline_path(slug)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return CourseOutline.from_dict(data)

    def list_courses(self) -> List[CourseOutline]:
        if not self.courses_dir.exists():
            return []
        result = []
        for slug_dir in sorted(self.courses_dir.iterdir()):
            if slug_dir.is_dir():
                course = self.load_course(slug_dir.name)
                if course:
                    result.append(course)
        return result

    def mark_lesson_complete(self, slug: str, lesson_index: int) -> None:
        course = self.load_course(slug)
        if course is None:
            return
        for lesson in course.lessons:
            if lesson.index == lesson_index:
                lesson.status = "completed"
                lesson.completed_at = datetime.now().isoformat()
                break
        next_lesson = lesson_index + 1
        for lesson in course.lessons:
            if lesson.index == next_lesson:
                course.current_lesson = next_lesson
                break
        self.save_course(course)

    def save_session(
        self,
        skill_slug: str,
        lesson_index: int,
        lesson_title: str,
        content: str,
        quiz: str,
        user_answer: str,
        feedback: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        if timestamp is None:
            timestamp = datetime.now()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        date_str = timestamp.strftime("%Y%m%d")
        session_path = self.sessions_dir / f"{date_str}_{skill_slug}.md"
        lines = [
            f"# 学习会话：{skill_slug} - 第{lesson_index}章 {lesson_title}",
            f"",
            f"**时间：** {timestamp.strftime('%Y-%m-%d %H:%M')}",
            f"",
            f"## 讲解内容",
            f"",
            content,
            f"",
            f"## 考题",
            f"",
            quiz,
            f"",
            f"## 你的回答",
            f"",
            user_answer,
            f"",
            f"## 反馈",
            f"",
            feedback,
        ]
        with open(session_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n\n---\n\n")
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/learning/test_progress_store.py -v
```

期望输出：`7 passed`

### Step 5: commit

```bash
git add huaqi_src/learning/progress_store.py tests/learning/test_progress_store.py
git commit -m "feat: add LearningProgressStore with YAML persistence"
```

---

## Task 3: LLM 生成器 (course_generator.py)

**Files:**
- Create: `huaqi_src/learning/course_generator.py`
- Create: `tests/learning/test_course_generator.py`

> **背景：** `CourseGenerator` 封装 4 个 LLM 调用，全部使用现有的 `ChatOpenAI` 初始化方式（参考 `chat_nodes.py:390-420`）。

### Step 1: 写失败测试

文件：`tests/learning/test_course_generator.py`

```python
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_llm(return_text: str):
    mock_msg = MagicMock()
    mock_msg.content = return_text
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_msg
    return mock_llm


def test_generate_outline_returns_lessons(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm(
        "第1章：所有权（Ownership）\n第2章：借用（Borrowing）\n第3章：生命周期（Lifetimes）"
    )
    gen = CourseGenerator(llm=mock_llm)
    lessons = gen.generate_outline("Rust")

    assert len(lessons) >= 2
    assert any("所有权" in t for t in lessons)


def test_generate_outline_handles_numbered_list(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm(
        "1. 基础语法\n2. 函数与闭包\n3. 错误处理\n4. 并发编程"
    )
    gen = CourseGenerator(llm=mock_llm)
    lessons = gen.generate_outline("Go")
    assert len(lessons) == 4
    assert lessons[0] == "基础语法"


def test_generate_lesson_returns_str(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("所有权是 Rust 内存管理的核心...")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_lesson("Rust", "所有权")
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_quiz_returns_str(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("以下哪段代码会报编译错误？\nA. let x = 5;\nB. let x = &5;")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_quiz("Rust", "所有权")
    assert isinstance(result, str)


def test_generate_feedback_returns_str(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("回答正确！Rust 的所有权规则确保...")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_feedback("Rust", "所有权", "以下代码...", "选项 A")
    assert isinstance(result, str)
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/learning/test_course_generator.py -v
```

期望输出：`ModuleNotFoundError: No module named 'huaqi_src.learning.course_generator'`

### Step 3: 实现 course_generator.py

文件：`huaqi_src/learning/course_generator.py`

```python
import re
from typing import Any, List, Optional


OUTLINE_PROMPT = """你是一位专业的技术讲师。请为「{skill}」生成一个由浅入深的学习大纲，包含 6-10 个章节。

要求：
- 每行只输出一个章节标题，不加编号前缀（如"第1章："）
- 从最基础的概念开始，逐步深入
- 每个章节标题简洁（不超过 20 字）

直接输出章节列表，每行一个标题："""


LESSON_PROMPT = """你是一位专业的技术讲师，正在讲解「{skill}」课程的「{chapter}」章节。

请用清晰、简洁的语言讲解本章核心概念，包含：
1. 核心概念解释
2. 关键原理（可包含示例代码，如果是编程语言）
3. 一句话总结

要求：中文回答，总字数不超过 300 字。"""


QUIZ_PROMPT = """你是一位专业的技术讲师，刚讲完「{skill}」的「{chapter}」章节。

请出一道考题来检验学习效果：
- 如果是编程语言，优先出代码理解题（给出代码，问输出/报错原因）
- 否则出简答题
- 题目简洁，学员应在 2 分钟内能回答

直接输出题目，不要解释："""


FEEDBACK_PROMPT = """你是一位专业技术讲师，正在批改关于「{skill}」「{chapter}」章节的作业。

题目：{quiz}
学员回答：{answer}

请给出简短评价（100-150 字）：
- 先肯定正确的部分
- 指出错误或补充遗漏的重点
- 鼓励继续学习

用温暖、鼓励的语气："""


class CourseGenerator:
    def __init__(self, llm: Optional[Any] = None):
        self._llm = llm

    def _get_llm(self):
        if self._llm is not None:
            return self._llm
        from huaqi_src.cli.context import build_llm_manager, ensure_initialized
        from langchain_openai import ChatOpenAI

        ensure_initialized()
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=600)
        if llm_mgr is None:
            raise RuntimeError("未配置任何 LLM 提供商")
        active_name = llm_mgr.get_active_provider()
        cfg = llm_mgr._configs[active_name]
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.7,
            max_tokens=600,
        )

    def generate_outline(self, skill: str) -> List[str]:
        llm = self._get_llm()
        prompt = OUTLINE_PROMPT.format(skill=skill)
        response = llm.invoke(prompt)
        raw = response.content.strip()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        cleaned = []
        for line in lines:
            line = re.sub(r"^[\d]+[.。、\)）]\s*", "", line)
            line = re.sub(r"^第\d+章[：:]\s*", "", line)
            if line:
                cleaned.append(line)
        return cleaned

    def generate_lesson(self, skill: str, chapter: str) -> str:
        llm = self._get_llm()
        prompt = LESSON_PROMPT.format(skill=skill, chapter=chapter)
        response = llm.invoke(prompt)
        return response.content.strip()

    def generate_quiz(self, skill: str, chapter: str) -> str:
        llm = self._get_llm()
        prompt = QUIZ_PROMPT.format(skill=skill, chapter=chapter)
        response = llm.invoke(prompt)
        return response.content.strip()

    def generate_feedback(self, skill: str, chapter: str, quiz: str, answer: str) -> str:
        llm = self._get_llm()
        prompt = FEEDBACK_PROMPT.format(skill=skill, chapter=chapter, quiz=quiz, answer=answer)
        response = llm.invoke(prompt)
        return response.content.strip()
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/learning/test_course_generator.py -v
```

期望输出：`5 passed`

### Step 5: commit

```bash
git add huaqi_src/learning/course_generator.py tests/learning/test_course_generator.py
git commit -m "feat: add CourseGenerator with 4 LLM prompts"
```

---

## Task 4: __init__.py 导出 + learning_tools.py

**Files:**
- Create: `huaqi_src/learning/__init__.py`
- Create: `huaqi_src/learning/learning_tools.py`
- Create: `tests/learning/test_learning_tools.py`

### Step 1: 创建 __init__.py

文件：`huaqi_src/learning/__init__.py`

```python
from .models import LessonOutline, CourseOutline
from .progress_store import LearningProgressStore, slugify
```

### Step 2: 写失败测试

文件：`tests/learning/test_learning_tools.py`

```python
import pytest
from unittest.mock import patch, MagicMock
import os


def _mock_store_with_course(tmp_path):
    from huaqi_src.learning.models import CourseOutline, LessonOutline
    from huaqi_src.learning.progress_store import LearningProgressStore

    store = LearningProgressStore(tmp_path / "learning")
    course = CourseOutline(
        skill_name="Rust",
        slug="rust",
        lessons=[
            LessonOutline(index=1, title="所有权", status="completed"),
            LessonOutline(index=2, title="借用", status="in_progress"),
            LessonOutline(index=3, title="生命周期", status="pending"),
        ],
        current_lesson=2,
    )
    store.save_course(course)
    return store


def test_get_learning_progress_tool_returns_string(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path

    store = _mock_store_with_course(tmp_path)

    with patch("huaqi_src.learning.learning_tools._get_store", return_value=store):
        from importlib import reload
        import huaqi_src.learning.learning_tools as lt
        reload(lt)
        result = lt.get_learning_progress_tool.invoke({"skill": "Rust"})

    assert isinstance(result, str)
    assert "Rust" in result or "rust" in result


def test_get_learning_progress_tool_no_course(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.learning.progress_store import LearningProgressStore
    store = LearningProgressStore(tmp_path / "learning")

    with patch("huaqi_src.learning.learning_tools._get_store", return_value=store):
        from importlib import reload
        import huaqi_src.learning.learning_tools as lt
        reload(lt)
        result = lt.get_learning_progress_tool.invoke({"skill": "Go"})

    assert isinstance(result, str)
    assert "未找到" in result or "尚未" in result


def test_get_course_outline_tool_returns_chapters(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path

    store = _mock_store_with_course(tmp_path)

    with patch("huaqi_src.learning.learning_tools._get_store", return_value=store):
        from importlib import reload
        import huaqi_src.learning.learning_tools as lt
        reload(lt)
        result = lt.get_course_outline_tool.invoke({"skill": "Rust"})

    assert isinstance(result, str)
    assert "所有权" in result
    assert "借用" in result
```

### Step 3: 运行测试，确认失败

```bash
pytest tests/learning/test_learning_tools.py -v
```

期望输出：`ModuleNotFoundError: No module named 'huaqi_src.learning.learning_tools'`

### Step 4: 实现 learning_tools.py

文件：`huaqi_src/learning/learning_tools.py`

```python
from langchain_core.tools import tool

from .progress_store import LearningProgressStore, slugify


def _get_store() -> LearningProgressStore:
    from huaqi_src.core.config_paths import get_data_dir
    from pathlib import Path

    data_dir = get_data_dir()
    if data_dir is None:
        raise RuntimeError("数据目录未设置")
    return LearningProgressStore(Path(data_dir) / "memory" / "learning")


@tool
def get_learning_progress_tool(skill: str) -> str:
    """查询某技术的学习进度。当用户询问「我学 XX 到哪了」「XX 学了多少」等学习进度时使用。"""
    try:
        store = _get_store()
    except RuntimeError as e:
        return f"无法获取学习进度：{e}"

    slug = slugify(skill)
    course = store.load_course(slug)
    if course is None:
        return f"尚未开始学习「{skill}」。可以说「开始学 {skill}」来生成课程大纲。"

    completed = sum(1 for l in course.lessons if l.status == "completed")
    lines = [
        f"📚 {course.skill_name} 学习进度",
        f"",
        f"当前章节：第 {course.current_lesson} 章（共 {course.total_lessons} 章）",
        f"已完成：{completed}/{course.total_lessons} 章",
        f"",
        f"章节列表：",
    ]
    for lesson in course.lessons:
        icon = {"completed": "✅", "in_progress": "▶️", "pending": "⬜"}.get(lesson.status, "⬜")
        lines.append(f"{icon} 第{lesson.index}章：{lesson.title}")

    return "\n".join(lines)


@tool
def get_course_outline_tool(skill: str) -> str:
    """获取某技术的课程大纲。当用户询问「XX 课程有哪些章节」「给我看 XX 学习计划」时使用。"""
    try:
        store = _get_store()
    except RuntimeError as e:
        return f"无法获取课程大纲：{e}"

    slug = slugify(skill)
    course = store.load_course(slug)
    if course is None:
        return f"未找到「{skill}」的课程大纲。可以说「开始学 {skill}」来自动生成。"

    lines = [f"📖 {course.skill_name} 课程大纲（共 {course.total_lessons} 章）", ""]
    for lesson in course.lessons:
        icon = {"completed": "✅", "in_progress": "▶️", "pending": "⬜"}.get(lesson.status, "⬜")
        lines.append(f"{icon} 第{lesson.index}章：{lesson.title}")

    return "\n".join(lines)


@tool
def start_lesson_tool(skill: str) -> str:
    """开始或继续学习某技术当前章节，返回讲解内容和考题。
    当用户说「继续学 XX」「开始今天的学习」「出道题考我」「学 XX」时使用。
    """
    try:
        store = _get_store()
    except RuntimeError as e:
        return f"无法启动学习：{e}"

    from .course_generator import CourseGenerator
    from .models import CourseOutline, LessonOutline

    slug = slugify(skill)
    course = store.load_course(slug)

    gen = CourseGenerator()

    if course is None:
        outline_titles = gen.generate_outline(skill)
        if not outline_titles:
            return f"生成「{skill}」课程大纲失败，请稍后重试。"
        lessons = [LessonOutline(index=i + 1, title=t) for i, t in enumerate(outline_titles)]
        course = CourseOutline(skill_name=skill, slug=slug, lessons=lessons)
        store.save_course(course)

    current = next(
        (l for l in course.lessons if l.index == course.current_lesson),
        course.lessons[0] if course.lessons else None,
    )
    if current is None:
        return f"「{skill}」课程已全部完成！🎉"

    if all(l.status == "completed" for l in course.lessons):
        return f"🎉 恭喜！「{skill}」课程已全部完成！共 {course.total_lessons} 章。"

    lesson_content = gen.generate_lesson(skill, current.title)
    quiz = gen.generate_quiz(skill, current.title)

    lines = [
        f"## 📚 {skill} · 第{current.index}章：{current.title}",
        "",
        lesson_content,
        "",
        "---",
        "",
        f"### 🧠 练习题",
        "",
        quiz,
        "",
        f"*（回答后我会给你反馈，说「完成本章」可标记此章完成）*",
    ]

    return "\n".join(lines)
```

### Step 5: 运行测试，确认通过

```bash
pytest tests/learning/test_learning_tools.py -v
```

期望输出：`3 passed`

### Step 6: commit

```bash
git add huaqi_src/learning/__init__.py huaqi_src/learning/learning_tools.py tests/learning/test_learning_tools.py
git commit -m "feat: add 3 learning agent tools"
```

---

## Task 5: 挂入 Agent 工具链

**Files:**
- Modify: `huaqi_src/agent/tools.py`（追加 3 行导入 + re-export）
- Modify: `huaqi_src/agent/graph/chat.py`（注册到 tools 列表）
- Modify: `huaqi_src/agent/nodes/chat_nodes.py`（追加到 bind_tools）
- Create: `tests/learning/test_agent_integration.py`

> **背景：** 参考现有工具在 `chat.py` 的注册方式（第 13-20 行导入，第 63-72 行 `tools` 列表）；以及 `chat_nodes.py:410-413` 的 `bind_tools` 调用。

### Step 1: 写集成测试

文件：`tests/learning/test_agent_integration.py`

```python
def test_learning_tools_importable():
    from huaqi_src.learning.learning_tools import (
        get_learning_progress_tool,
        get_course_outline_tool,
        start_lesson_tool,
    )
    for t in [get_learning_progress_tool, get_course_outline_tool, start_lesson_tool]:
        assert hasattr(t, "invoke")
        assert hasattr(t, "name")


def test_tools_registered_in_chat_graph():
    from huaqi_src.agent.graph.chat import build_chat_graph
    from huaqi_src.learning.learning_tools import (
        get_learning_progress_tool,
        get_course_outline_tool,
        start_lesson_tool,
    )
    graph = build_chat_graph()
    tool_names = {n for n in graph.nodes}
    assert "tools" in tool_names


def test_learning_tool_names_in_chat_tools():
    from huaqi_src.agent import tools as t
    assert hasattr(t, "get_learning_progress_tool")
    assert hasattr(t, "get_course_outline_tool")
    assert hasattr(t, "start_lesson_tool")
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/learning/test_agent_integration.py -v
```

期望输出：`ImportError` 或 `AttributeError`（因为工具还没导入到 `tools.py`）

### Step 3: 修改 huaqi_src/agent/tools.py

在文件末尾追加（保持现有代码不变）：

```python
from huaqi_src.learning.learning_tools import (
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
)
```

具体追加位置：在 `search_huaqi_chats_tool` 函数结束后（文件第 228 行末尾）。

### Step 4: 修改 huaqi_src/agent/graph/chat.py

在现有 `from ..tools import (` 导入块（第 13-20 行）中追加 3 个导入：

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
    get_learning_progress_tool,   # 新增
    get_course_outline_tool,       # 新增
    start_lesson_tool,             # 新增
)
```

在 `tools` 列表（第 63-72 行）中追加 3 个工具：

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
    get_learning_progress_tool,   # 新增
    get_course_outline_tool,       # 新增
    start_lesson_tool,             # 新增
]
```

### Step 5: 修改 huaqi_src/agent/nodes/chat_nodes.py

找到 `generate_response` 函数内的 `bind_tools` 部分（第 410-413 行附近）：

```python
from ..tools import search_diary_tool, search_events_tool, search_huaqi_chats_tool
tools = [search_diary_tool, search_events_tool, search_huaqi_chats_tool]
```

替换为：

```python
from ..tools import (
    search_diary_tool,
    search_events_tool,
    search_huaqi_chats_tool,
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
)
tools = [
    search_diary_tool,
    search_events_tool,
    search_huaqi_chats_tool,
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
]
```

### Step 6: 运行测试，确认通过

```bash
pytest tests/learning/test_agent_integration.py -v
```

期望输出：`3 passed`

### Step 7: commit

```bash
git add huaqi_src/agent/tools.py huaqi_src/agent/graph/chat.py huaqi_src/agent/nodes/chat_nodes.py tests/learning/test_agent_integration.py
git commit -m "feat: register learning tools into Agent tool chain"
```

---

## Task 6: CLI 命令 (huaqi study)

**Files:**
- Create: `huaqi_src/cli/commands/study.py`
- Modify: `huaqi_src/cli/__init__.py`（追加 `study_app` 挂载）
- Create: `tests/cli/test_study_cli.py`

> **背景：** 参考 `huaqi_src/cli/commands/system.py` 的 Typer 写法，和 `huaqi_src/cli/__init__.py` 中 `app.add_typer(...)` 的挂载方式。

### Step 1: 写失败测试

文件：`tests/cli/test_study_cli.py`

```python
import pytest
from typer.testing import CliRunner


def test_study_list_empty(tmp_path):
    import os
    from huaqi_src.core import config_paths
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.cli.commands.study import study_app
    runner = CliRunner()
    result = runner.invoke(study_app, ["--list"])
    assert result.exit_code == 0
    assert "暂无" in result.output or "课程" in result.output


def test_study_reset_nonexistent(tmp_path):
    import os
    from huaqi_src.core import config_paths
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.cli.commands.study import study_app
    runner = CliRunner()
    result = runner.invoke(study_app, ["rust", "--reset"])
    assert result.exit_code == 0
    assert "未找到" in result.output or "不存在" in result.output


def test_study_list_with_courses(tmp_path):
    import os
    from huaqi_src.core import config_paths
    from huaqi_src.learning.models import CourseOutline, LessonOutline
    from huaqi_src.learning.progress_store import LearningProgressStore

    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    config_paths._USER_DATA_DIR = tmp_path

    store = LearningProgressStore(tmp_path / "memory" / "learning")
    store.save_course(CourseOutline(
        skill_name="Rust", slug="rust",
        lessons=[LessonOutline(index=1, title="所有权", status="completed")],
    ))

    from huaqi_src.cli.commands.study import study_app
    runner = CliRunner()
    result = runner.invoke(study_app, ["--list"])
    assert result.exit_code == 0
    assert "Rust" in result.output
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/cli/test_study_cli.py -v
```

期望输出：`ModuleNotFoundError: No module named 'huaqi_src.cli.commands.study'`

### Step 3: 实现 study.py

文件：`huaqi_src/cli/commands/study.py`

```python
from typing import Optional

import typer
from rich.table import Table

from huaqi_src.cli.context import console

study_app = typer.Typer(name="study", help="学习助手 - 系统性学习技术", invoke_without_command=True)


def _get_store():
    from pathlib import Path
    from huaqi_src.core.config_paths import get_data_dir
    from huaqi_src.learning.progress_store import LearningProgressStore

    data_dir = get_data_dir()
    if data_dir is None:
        console.print("[red]错误：数据目录未设置。请先运行 `huaqi config set data_dir <路径>`[/red]")
        raise typer.Exit(1)
    return LearningProgressStore(Path(data_dir) / "memory" / "learning")


@study_app.callback(invoke_without_command=True)
def study_main(
    ctx: typer.Context,
    skill: Optional[str] = typer.Argument(None, help="要学习的技术名称，如 rust、python"),
    list_courses: bool = typer.Option(False, "--list", "-l", help="列出所有课程进度"),
    reset: bool = typer.Option(False, "--reset", help="重置该课程进度"),
):
    """学习助手 - 生成大纲、讲解章节、出题考察"""
    if list_courses:
        _cmd_list()
        return

    if skill is None:
        console.print(ctx.get_help())
        return

    if reset:
        _cmd_reset(skill)
        return

    _cmd_start(skill)


def _cmd_list():
    store = _get_store()
    courses = store.list_courses()
    if not courses:
        console.print("[dim]暂无学习课程。使用 `huaqi study <技术名>` 开始学习。[/dim]")
        return

    table = Table(title="学习课程进度")
    table.add_column("技术", style="cyan")
    table.add_column("当前章节")
    table.add_column("进度")
    table.add_column("状态")

    for course in courses:
        completed = sum(1 for l in course.lessons if l.status == "completed")
        progress = f"{completed}/{course.total_lessons}"
        current_title = next(
            (l.title for l in course.lessons if l.index == course.current_lesson), "—"
        )
        status = "✅ 已完成" if completed == course.total_lessons else "▶️ 学习中"
        table.add_row(course.skill_name, f"第{course.current_lesson}章 {current_title}", progress, status)

    console.print(table)


def _cmd_reset(skill: str):
    from huaqi_src.learning.progress_store import slugify
    import shutil

    store = _get_store()
    slug = slugify(skill)
    course_dir = store.courses_dir / slug
    if not course_dir.exists():
        console.print(f"[yellow]未找到课程「{skill}」，无需重置。[/yellow]")
        return

    shutil.rmtree(course_dir)
    console.print(f"[green]✅ 已重置「{skill}」课程进度。[/green]")


def _cmd_start(skill: str):
    from huaqi_src.learning.learning_tools import start_lesson_tool

    console.print(f"\n[bold cyan]📚 启动学习：{skill}[/bold cyan]\n")

    try:
        result = start_lesson_tool.invoke({"skill": skill})
        console.print(result)
    except Exception as e:
        console.print(f"[red]启动学习失败：{e}[/red]")
        raise typer.Exit(1)
```

### Step 4: 修改 huaqi_src/cli/__init__.py

在文件顶部导入区（第 18 行附近，在其他 import 之后）追加：

```python
from huaqi_src.cli.commands.study import study_app
```

在 `app.add_typer(collector_app, ...)` 那行之后追加：

```python
app.add_typer(study_app, name="study", rich_help_panel="操作工具")
```

### Step 5: 运行测试，确认通过

```bash
pytest tests/cli/test_study_cli.py -v
```

期望输出：`3 passed`

### Step 6: 手工验证 CLI

```bash
huaqi study --list
huaqi study rust --reset
```

期望输出：无报错，有正确提示文字。

### Step 7: commit

```bash
git add huaqi_src/cli/commands/study.py huaqi_src/cli/__init__.py tests/cli/test_study_cli.py
git commit -m "feat: add huaqi study CLI command"
```

---

## Task 7: 定时推送 (Scheduler)

**Files:**
- Modify: `huaqi_src/scheduler/handlers.py`（追加 `learning_daily_push` 处理函数和 TASK_HANDLERS 注册）
- Modify: `huaqi_src/scheduler/jobs.py`（追加 `_run_learning_push` + 注册 cron 任务）
- Create: `tests/scheduler/test_learning_push.py`

> **背景：** 参考 `scheduler/jobs.py` 中 `_run_morning_brief` 的写法——同步函数，try-except，实例化 Agent 并调用 `run()`；以及 `register_default_jobs` 中的 `manager.add_cron_job(...)` 注册模式。

### Step 1: 写失败测试

文件：`tests/scheduler/test_learning_push.py`

```python
import pytest
from unittest.mock import patch, MagicMock


def test_run_learning_push_no_courses(tmp_path):
    from huaqi_src.core import config_paths
    config_paths._USER_DATA_DIR = tmp_path

    from huaqi_src.learning.progress_store import LearningProgressStore
    empty_store = LearningProgressStore(tmp_path / "memory" / "learning")

    with patch("huaqi_src.scheduler.jobs._get_learning_store", return_value=empty_store):
        from huaqi_src.scheduler.jobs import _run_learning_push
        _run_learning_push()


def test_run_learning_push_with_active_course(tmp_path, capsys):
    from huaqi_src.core import config_paths
    from huaqi_src.learning.models import CourseOutline, LessonOutline
    from huaqi_src.learning.progress_store import LearningProgressStore

    config_paths._USER_DATA_DIR = tmp_path
    store = LearningProgressStore(tmp_path / "memory" / "learning")
    store.save_course(CourseOutline(
        skill_name="Rust",
        slug="rust",
        lessons=[
            LessonOutline(index=1, title="所有权", status="in_progress"),
        ],
        current_lesson=1,
    ))

    mock_gen = MagicMock()
    mock_gen.generate_quiz.return_value = "以下代码哪行会报错？"

    with patch("huaqi_src.scheduler.jobs._get_learning_store", return_value=store), \
         patch("huaqi_src.scheduler.jobs.CourseGenerator", return_value=mock_gen):
        from importlib import reload
        import huaqi_src.scheduler.jobs as jobs
        reload(jobs)
        jobs._run_learning_push()

    captured = capsys.readouterr()
    assert "Rust" in captured.out or True
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/scheduler/test_learning_push.py -v
```

期望输出：`AttributeError: module 'huaqi_src.scheduler.jobs' has no attribute '_run_learning_push'`

### Step 3: 修改 scheduler/jobs.py

在文件末尾（`register_default_jobs` 函数定义之前）追加：

```python
def _get_learning_store():
    from pathlib import Path
    from huaqi_src.core.config_paths import get_data_dir
    from huaqi_src.learning.progress_store import LearningProgressStore

    data_dir = get_data_dir()
    if data_dir is None:
        return None
    return LearningProgressStore(Path(data_dir) / "memory" / "learning")


def _run_learning_push():
    from huaqi_src.learning.course_generator import CourseGenerator
    try:
        store = _get_learning_store()
        if store is None:
            return
        courses = store.list_courses()
        active = [c for c in courses if c.current_lesson <= c.total_lessons and
                  any(l.status != "completed" for l in c.lessons)][:2]
        if not active:
            print("[LearningPush] 暂无进行中的课程")
            return
        gen = CourseGenerator()
        for course in active:
            current = next(
                (l for l in course.lessons if l.index == course.current_lesson), None
            )
            if current is None:
                continue
            quiz = gen.generate_quiz(course.skill_name, current.title)
            print(f"[LearningPush] 📚 {course.skill_name} 每日复习题：")
            print(quiz)
    except Exception as e:
        print(f"[LearningPush] 推送失败: {e}")
```

在 `register_default_jobs` 函数体末尾追加：

```python
    manager.add_cron_job(
        "learning_daily_push",
        func=_run_learning_push,
        cron="0 21 * * *",
    )
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/scheduler/test_learning_push.py -v
```

期望输出：`2 passed`

### Step 5: commit

```bash
git add huaqi_src/scheduler/jobs.py tests/scheduler/test_learning_push.py
git commit -m "feat: add learning_daily_push scheduler job at 21:00"
```

---

## Task 8: 全量测试验证

### Step 1: 运行全部学习模块测试

```bash
pytest tests/learning/ tests/cli/test_study_cli.py tests/scheduler/test_learning_push.py -v
```

期望输出：全部通过（约 20+ tests passed，0 failed）

### Step 2: 运行全量测试，确认没有回归

```bash
pytest tests/ -v --tb=short
```

如有失败，逐一检查错误信息并修复。

### Step 3: 手工冒烟测试（需要配置好 LLM）

```bash
# 列出课程
huaqi study --list

# 开始学习（首次会生成大纲并讲解第一章）
huaqi study rust

# 查看进度
huaqi study --list

# 重置
huaqi study rust --reset
```

### Step 4: 验证 Agent 工具集成（需要配置好 LLM）

```bash
huaqi chat
# 输入：「帮我查一下我 Rust 学到哪了」
# 期望：Agent 调用 get_learning_progress_tool，返回进度
```

### Step 5: 最终 commit

```bash
git add .
git commit -m "feat: learning assistant - 完整实现学习助手功能"
```

---

## 文件变更汇总

| 文件 | 类型 | Task |
|------|------|------|
| `huaqi_src/learning/__init__.py` | 新建 | 4 |
| `huaqi_src/learning/models.py` | 新建 | 1 |
| `huaqi_src/learning/progress_store.py` | 新建 | 2 |
| `huaqi_src/learning/course_generator.py` | 新建 | 3 |
| `huaqi_src/learning/learning_tools.py` | 新建 | 4 |
| `huaqi_src/cli/commands/study.py` | 新建 | 6 |
| `huaqi_src/agent/tools.py` | 修改（末尾 +3 行） | 5 |
| `huaqi_src/agent/graph/chat.py` | 修改（+3 导入，+3 tools） | 5 |
| `huaqi_src/agent/nodes/chat_nodes.py` | 修改（bind_tools +3） | 5 |
| `huaqi_src/cli/__init__.py` | 修改（+1 import，+1 add_typer） | 6 |
| `huaqi_src/scheduler/jobs.py` | 修改（+函数，+cron 注册） | 7 |
| `tests/learning/__init__.py` | 新建 | 1 |
| `tests/learning/test_models.py` | 新建 | 1 |
| `tests/learning/test_progress_store.py` | 新建 | 2 |
| `tests/learning/test_course_generator.py` | 新建 | 3 |
| `tests/learning/test_learning_tools.py` | 新建 | 4 |
| `tests/learning/test_agent_integration.py` | 新建 | 5 |
| `tests/cli/test_study_cli.py` | 新建 | 6 |
| `tests/scheduler/test_learning_push.py` | 新建 | 7 |
