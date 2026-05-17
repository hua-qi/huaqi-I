# Codeflicker WorkLog Storage Implementation Plan

**Goal:** 将 codeflicker 每次会话的工作内容写入独立 Markdown 文件，并通过 WorkLogProvider 注入日报，补充"今天做了什么工作"维度。

**Architecture:** 在现有 `CLIChatWatcher.process_file()` 处理流程中新增 `WorkLogWriter` 调用分支（在 DecisionDetector 之前），将会话摘要写入 `$DATA_DIR/work_logs/YYYY-MM/YYYYMMDD_HHMMSS_{thread_id}.md`；同时新增 `WorkLogProvider` 按天聚合当日所有 WorkLog 文件，注入日报 Prompt。两条路完全独立，不修改现有 DistillationPipeline 和 TELOS 流程。

**Tech Stack:** Python 3.9+, pathlib, datetime, pydantic（已有）, pytest（已有）, watchdog（已有）

---

## 背景知识

动手前，先了解以下文件：

- `huaqi_src/layers/data/collectors/cli_chat_watcher.py` — `CLIChatWatcher.process_file()` 是现有处理入口，接收 `file_path` 和 `tool_type`，返回 `list[HuaqiDocument]`
- `huaqi_src/layers/data/collectors/cli_chat_parser.py` — `parse_cli_chat_file()` 解析 codeflicker `.md` 文件，返回 `list[CLIChatMessage]`；每条消息有 `role` 和 `content`
- `huaqi_src/layers/capabilities/reports/providers/__init__.py` — `DataProvider` 抽象基类，`register()` / `get_providers()` 注册表
- `huaqi_src/layers/capabilities/reports/providers/diary.py` — 参考实现，`DiaryProvider` 展示了 Provider 的完整写法（`__init__`、`get_context`、末尾自注册）
- `huaqi_src/layers/capabilities/reports/daily_report.py` — `DailyReportAgent._register_providers()` 展示了如何在报告类中注册 Provider
- `tests/unit/layers/data/collectors/test_cli_chat_watcher.py` — 现有 watcher 测试，了解测试惯例（`tmp_path` 作为 `data_dir`）
- `tests/unit/layers/capabilities/reports/test_providers.py` — 现有 provider 测试，了解 `_registry.clear()` + 手动注册的惯例

**WorkLog 文件格式：**

```markdown
---
date: 2026-05-04
time_start: 2026-05-04T10:00:00Z
time_end: 2026-05-04T10:30:00Z
thread_id: gb4l7s37xp22adfrlqfz
source: codeflicker
tech_stack: [watchdog, asyncio, python]
category: problem_solving
---

设计了 transcript-collector 的文件监听方案。
选择 on_created 事件触发而非轮询，解决了 watchdog 回调与 asyncio 的线程安全冲突。
```

**运行测试命令：**

```
python3 -m pytest tests/ -v
```

---

## Task 1: 实现 WorkLogWriter

`WorkLogWriter` 负责将一次 codeflicker 会话写成 WorkLog Markdown 文件。输入是 `parse_cli_chat_file()` 返回的消息列表和文件路径（用于提取 thread_id 和时间），输出是写入磁盘的文件路径。

**Files:**
- Create: `huaqi_src/layers/data/collectors/work_log_writer.py`
- Create: `tests/unit/layers/data/collectors/test_work_log_writer.py`

**Step 1: 写失败测试**

```python
# tests/unit/layers/data/collectors/test_work_log_writer.py
from pathlib import Path
from huaqi_src.layers.data.collectors.cli_chat_parser import CLIChatMessage
from huaqi_src.layers.data.collectors.work_log_writer import WorkLogWriter


def _make_messages():
    return [
        CLIChatMessage(role="user", content="帮我设计 watchdog 监听方案"),
        CLIChatMessage(role="assistant", content="选择 on_created 事件，解决了 asyncio 线程安全问题"),
    ]


def test_write_creates_file_in_correct_directory(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    messages = _make_messages()
    file_path = writer.write(
        messages=messages,
        thread_id="abc123",
        time_start="2026-05-04T10:00:00Z",
        time_end="2026-05-04T10:30:00Z",
    )

    assert file_path is not None
    assert file_path.exists()
    work_logs_dir = tmp_path / "work_logs" / "2026-05"
    assert file_path.parent == work_logs_dir


def test_write_file_contains_yaml_frontmatter(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    messages = _make_messages()
    file_path = writer.write(
        messages=messages,
        thread_id="abc123",
        time_start="2026-05-04T10:00:00Z",
        time_end="2026-05-04T10:30:00Z",
    )

    content = file_path.read_text(encoding="utf-8")
    assert "---" in content
    assert "thread_id: abc123" in content
    assert "source: codeflicker" in content
    assert "time_start: 2026-05-04T10:00:00Z" in content
    assert "time_end: 2026-05-04T10:30:00Z" in content


def test_write_file_contains_summary_body(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    messages = _make_messages()
    file_path = writer.write(
        messages=messages,
        thread_id="abc123",
        time_start="2026-05-04T10:00:00Z",
        time_end="2026-05-04T10:30:00Z",
    )

    content = file_path.read_text(encoding="utf-8")
    assert len(content.split("---")) >= 3
    body = content.split("---", 2)[2].strip()
    assert len(body) > 0


def test_write_returns_none_for_empty_messages(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    result = writer.write(
        messages=[],
        thread_id="abc123",
        time_start="2026-05-04T10:00:00Z",
        time_end="2026-05-04T10:30:00Z",
    )
    assert result is None


def test_write_filename_contains_thread_id(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    messages = _make_messages()
    file_path = writer.write(
        messages=messages,
        thread_id="mythread42",
        time_start="2026-05-04T14:00:00Z",
        time_end="2026-05-04T14:30:00Z",
    )

    assert "mythread42" in file_path.name
```

**Step 2: 运行测试，确认失败**

```
python3 -m pytest tests/unit/layers/data/collectors/test_work_log_writer.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.layers.data.collectors.work_log_writer'`

**Step 3: 实现 WorkLogWriter**

```python
# huaqi_src/layers/data/collectors/work_log_writer.py
from pathlib import Path
from typing import Optional

from huaqi_src.layers.data.collectors.cli_chat_parser import CLIChatMessage


class WorkLogWriter:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from huaqi_src.config.paths import require_data_dir
            data_dir = require_data_dir()
        self._data_dir = Path(data_dir)

    def write(
        self,
        messages: list[CLIChatMessage],
        thread_id: str,
        time_start: str,
        time_end: str,
    ) -> Optional[Path]:
        if not messages:
            return None

        date_part = time_start[:10].replace("-", "")
        time_part = time_start[11:19].replace(":", "")
        month_key = time_start[:7]

        out_dir = self._data_dir / "work_logs" / month_key
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{date_part}_{time_part}_{thread_id}.md"
        out_file = out_dir / filename

        summary = self._build_summary(messages)
        frontmatter = (
            f"---\n"
            f"date: {time_start[:10]}\n"
            f"time_start: {time_start}\n"
            f"time_end: {time_end}\n"
            f"thread_id: {thread_id}\n"
            f"source: codeflicker\n"
            f"---\n"
        )
        out_file.write_text(frontmatter + "\n" + summary + "\n", encoding="utf-8")
        return out_file

    def _build_summary(self, messages: list[CLIChatMessage]) -> str:
        user_msgs = [m.content for m in messages if m.role == "user"]
        assistant_msgs = [m.content for m in messages if m.role == "assistant"]

        parts = []
        if user_msgs:
            parts.append(user_msgs[0][:100])
        if assistant_msgs:
            parts.append(assistant_msgs[-1][:100])

        return "。".join(parts) if parts else ""
```

**Step 4: 运行测试，确认通过**

```
python3 -m pytest tests/unit/layers/data/collectors/test_work_log_writer.py -v
```

预期：5 tests passed

**Step 5: 提交**

```
git add huaqi_src/layers/data/collectors/work_log_writer.py tests/unit/layers/data/collectors/test_work_log_writer.py
git commit -m "feat: add WorkLogWriter"
```

---

## Task 2: 将 WorkLogWriter 集成到 CLIChatWatcher

在 `CLIChatWatcher.process_file()` 中，解析消息之后、写入 memory 目录之前，调用 `WorkLogWriter.write()`。需要从文件路径中提取 `thread_id`，并处理缺少时间信息时的降级（用当前时间代替）。

**Files:**
- Modify: `huaqi_src/layers/data/collectors/cli_chat_watcher.py`
- Modify: `tests/unit/layers/data/collectors/test_cli_chat_watcher.py`

**Step 1: 追加失败测试**

在 `tests/unit/layers/data/collectors/test_cli_chat_watcher.py` 末尾追加：

```python
def test_process_file_creates_work_log(tmp_path):
    conv_dir = tmp_path / "conversations"
    md_file = conv_dir / "session_001.md"
    _make_md_session(md_file)

    watch_paths = [{"type": "codeflicker", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    watcher.process_file(md_file, tool_type="codeflicker")

    work_logs_dir = tmp_path / "work_logs"
    md_files = list(work_logs_dir.rglob("*.md"))
    assert len(md_files) == 1


def test_process_file_work_log_not_created_for_non_codeflicker(tmp_path):
    conv_dir = tmp_path / "conversations"
    md_file = conv_dir / "session_001.md"
    _make_md_session(md_file)

    watch_paths = [{"type": "custom", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    watcher.process_file(md_file, tool_type="custom")

    work_logs_dir = tmp_path / "work_logs"
    assert not work_logs_dir.exists()
```

**Step 2: 运行测试，确认失败**

```
python3 -m pytest tests/unit/layers/data/collectors/test_cli_chat_watcher.py::test_process_file_creates_work_log -v
```

预期：FAIL（work_logs 目录不存在）

**Step 3: 修改 CLIChatWatcher.process_file()**

在 `cli_chat_watcher.py` 中，找到 `process_file` 方法，在 `if not messages: return []` 之后、写入 memory 目录之前，插入：

```python
if tool_type == "codeflicker":
    from huaqi_src.layers.data.collectors.work_log_writer import WorkLogWriter
    import datetime as _dt
    now_iso = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    thread_id = file_path.stem
    WorkLogWriter(data_dir=self._data_dir).write(
        messages=messages,
        thread_id=thread_id,
        time_start=now_iso,
        time_end=now_iso,
    )
```

完整修改后的 `process_file` 方法：

```python
def process_file(self, file_path: Path, tool_type: str) -> list[HuaqiDocument]:
    messages = parse_cli_chat_file(file_path, tool_type=tool_type)
    if not messages:
        return []

    if tool_type == "codeflicker":
        import datetime as _dt
        from huaqi_src.layers.data.collectors.work_log_writer import WorkLogWriter
        now_iso = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        thread_id = file_path.stem
        WorkLogWriter(data_dir=self._data_dir).write(
            messages=messages,
            thread_id=thread_id,
            time_start=now_iso,
            time_end=now_iso,
        )

    content_lines = [
        f"[{m.role}]: {m.content}" for m in messages
    ]
    content = "\n".join(content_lines)

    now = datetime.datetime.now()
    month_key = now.strftime("%Y-%m")
    out_dir = self._data_dir / "memory" / "cli_chats" / month_key
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"{tool_type}-{file_path.stem}.md"
    header = f"# {tool_type} 对话记录: {file_path.name}\n\n"
    out_file.write_text(header + content + "\n", encoding="utf-8")

    doc_id = hashlib.md5(f"cli_chat:{tool_type}:{file_path.name}:{len(messages)}".encode()).hexdigest()[:12]
    return [
        HuaqiDocument(
            doc_id=doc_id,
            doc_type="cli_chat",
            source=f"cli_chat:{tool_type}:{file_path.name}",
            content=content,
            timestamp=now,
            metadata={"tool_type": tool_type, "file": str(file_path)},
        )
    ]
```

**Step 4: 运行测试，确认通过**

```
python3 -m pytest tests/unit/layers/data/collectors/test_cli_chat_watcher.py -v
```

预期：6 tests passed（原有 4 个 + 新增 2 个）

**Step 5: 提交**

```
git add huaqi_src/layers/data/collectors/cli_chat_watcher.py tests/unit/layers/data/collectors/test_cli_chat_watcher.py
git commit -m "feat: integrate WorkLogWriter into CLIChatWatcher"
```

---

## Task 3: 实现 WorkLogProvider

`WorkLogProvider` 读取 `$DATA_DIR/work_logs/YYYY-MM/` 下匹配当天日期的 WorkLog 文件，按 `time_start` 排序，生成可注入日报 Prompt 的文本块。只参与 `daily` 报告，优先级 25（介于 world=10 和 diary=20 之后，略高于 people=40）。

**Files:**
- Create: `huaqi_src/layers/capabilities/reports/providers/work_log.py`
- Modify: `tests/unit/layers/capabilities/reports/test_providers.py`

**Step 1: 追加失败测试**

在 `tests/unit/layers/capabilities/reports/test_providers.py` 末尾追加：

```python
def test_work_log_provider_returns_todays_sessions(tmp_path):
    import datetime
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.work_log import WorkLogProvider
    _registry.clear()

    today = datetime.date.today()
    month_key = today.strftime("%Y-%m")
    date_str = today.strftime("%Y%m%d")

    work_logs_dir = tmp_path / "work_logs" / month_key
    work_logs_dir.mkdir(parents=True)

    session_file = work_logs_dir / f"{date_str}_100000_threadabc.md"
    session_file.write_text(
        "---\n"
        f"date: {today.isoformat()}\n"
        "time_start: " + today.isoformat() + "T10:00:00Z\n"
        "time_end: " + today.isoformat() + "T10:30:00Z\n"
        "thread_id: threadabc\n"
        "source: codeflicker\n"
        "---\n\n"
        "实现了 WorkLogWriter，写入 Markdown 文件。\n",
        encoding="utf-8",
    )

    from huaqi_src.layers.capabilities.reports.providers import register
    register(WorkLogProvider(data_dir=tmp_path))

    providers = get_providers("daily")
    work_log_providers = [p for p in providers if p.name == "work_log"]
    assert len(work_log_providers) == 1

    date_range = DateRange(start=today, end=today)
    ctx = work_log_providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "WorkLogWriter" in ctx
    assert "今日编程工作" in ctx


def test_work_log_provider_returns_none_when_no_logs(tmp_path):
    import datetime
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange, register
    from huaqi_src.layers.capabilities.reports.providers.work_log import WorkLogProvider
    _registry.clear()

    register(WorkLogProvider(data_dir=tmp_path))

    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    work_log_providers = [p for p in providers if p.name == "work_log"]
    assert len(work_log_providers) == 1

    ctx = work_log_providers[0].get_context("daily", date_range)
    assert ctx is None


def test_work_log_provider_not_for_weekly(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, register
    from huaqi_src.layers.capabilities.reports.providers.work_log import WorkLogProvider
    _registry.clear()

    register(WorkLogProvider(data_dir=tmp_path))

    providers = get_providers("weekly")
    work_log_providers = [p for p in providers if p.name == "work_log"]
    assert len(work_log_providers) == 0


def test_work_log_provider_multiple_sessions_sorted(tmp_path):
    import datetime
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange, register
    from huaqi_src.layers.capabilities.reports.providers.work_log import WorkLogProvider
    _registry.clear()

    today = datetime.date.today()
    month_key = today.strftime("%Y-%m")
    date_str = today.strftime("%Y%m%d")

    work_logs_dir = tmp_path / "work_logs" / month_key
    work_logs_dir.mkdir(parents=True)

    for hour, task in [("100000", "早上完成了 Task A"), ("140000", "下午完成了 Task B")]:
        f = work_logs_dir / f"{date_str}_{hour}_thread{hour}.md"
        f.write_text(
            "---\n"
            f"date: {today.isoformat()}\n"
            f"time_start: {today.isoformat()}T{hour[:2]}:00:00Z\n"
            f"time_end: {today.isoformat()}T{hour[:2]}:30:00Z\n"
            f"thread_id: thread{hour}\n"
            "source: codeflicker\n"
            "---\n\n"
            f"{task}\n",
            encoding="utf-8",
        )

    register(WorkLogProvider(data_dir=tmp_path))

    providers = get_providers("daily")
    work_log_providers = [p for p in providers if p.name == "work_log"]
    date_range = DateRange(start=today, end=today)
    ctx = work_log_providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "Task A" in ctx
    assert "Task B" in ctx
    assert ctx.index("Task A") < ctx.index("Task B")
```

**Step 2: 运行测试，确认失败**

```
python3 -m pytest tests/unit/layers/capabilities/reports/test_providers.py::test_work_log_provider_returns_todays_sessions -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.layers.capabilities.reports.providers.work_log'`

**Step 3: 实现 WorkLogProvider**

```python
# huaqi_src/layers/capabilities/reports/providers/work_log.py
import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.layers.capabilities.reports.providers import DataProvider, DateRange, register


class WorkLogProvider(DataProvider):
    name = "work_log"
    priority = 25
    supported_reports = ["daily"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        target_date = date_range.end
        month_key = target_date.strftime("%Y-%m")
        date_prefix = target_date.strftime("%Y%m%d")

        work_logs_dir = self._data_dir / "work_logs" / month_key
        if not work_logs_dir.exists():
            return None

        session_files = sorted(work_logs_dir.glob(f"{date_prefix}_*.md"))
        if not session_files:
            return None

        snippets = []
        for f in session_files:
            raw = f.read_text(encoding="utf-8")
            parts = raw.split("---", 2)
            if len(parts) < 3:
                continue
            frontmatter = parts[1]
            body = parts[2].strip()

            time_start = ""
            time_end = ""
            for line in frontmatter.splitlines():
                if line.startswith("time_start:"):
                    time_start = line.split(":", 1)[1].strip()
                elif line.startswith("time_end:"):
                    time_end = line.split(":", 1)[1].strip()

            time_label = ""
            if time_start and time_end:
                start_hm = time_start[11:16] if len(time_start) >= 16 else time_start
                end_hm = time_end[11:16] if len(time_end) >= 16 else time_end
                time_label = f"### {start_hm}–{end_hm}\n"

            snippets.append(time_label + body)

        if not snippets:
            return None

        return "## 今日编程工作（来自 codeflicker）\n\n" + "\n\n".join(snippets)


try:
    from huaqi_src.config.paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(WorkLogProvider(_data_dir))
except Exception:
    pass
```

**Step 4: 运行测试，确认通过**

```
python3 -m pytest tests/unit/layers/capabilities/reports/test_providers.py -k "work_log" -v
```

预期：4 tests passed

**Step 5: 提交**

```
git add huaqi_src/layers/capabilities/reports/providers/work_log.py tests/unit/layers/capabilities/reports/test_providers.py
git commit -m "feat: add WorkLogProvider"
```

---

## Task 4: 将 WorkLogProvider 注册到 DailyReportAgent

修改 `DailyReportAgent._register_providers()`，加入 `WorkLogProvider`，使其在日报生成时自动参与上下文构建。

**Files:**
- Modify: `huaqi_src/layers/capabilities/reports/daily_report.py`
- Modify: `tests/unit/layers/capabilities/reports/test_daily_report.py`（确认测试仍通过）

**Step 1: 查看 test_daily_report.py，了解现有测试内容**

```
python3 -m pytest tests/unit/layers/capabilities/reports/test_daily_report.py -v
```

记录当前通过数量。

**Step 2: 追加失败测试**

在 `tests/unit/layers/capabilities/reports/test_daily_report.py` 末尾追加：

```python
def test_daily_report_registers_work_log_provider(tmp_path):
    from unittest.mock import patch
    from huaqi_src.layers.capabilities.reports.providers import _registry
    from huaqi_src.layers.capabilities.reports.daily_report import DailyReportAgent
    _registry.clear()

    agent = DailyReportAgent(data_dir=tmp_path)
    provider_names = [p.name for p in _registry]
    assert "work_log" in provider_names
```

**Step 3: 运行测试，确认失败**

```
python3 -m pytest tests/unit/layers/capabilities/reports/test_daily_report.py::test_daily_report_registers_work_log_provider -v
```

预期：FAIL（`work_log` 不在 provider_names 中）

**Step 4: 修改 DailyReportAgent._register_providers()**

在 `daily_report.py` 中找到 `_register_providers` 方法，添加 `WorkLogProvider`：

```python
def _register_providers(self) -> None:
    from huaqi_src.layers.capabilities.reports.providers import _registry, register
    from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
    from huaqi_src.layers.capabilities.reports.providers.diary import DiaryProvider
    from huaqi_src.layers.capabilities.reports.providers.people import PeopleProvider
    from huaqi_src.layers.capabilities.reports.providers.work_log import WorkLogProvider

    for p in list(_registry):
        if p.name in ("world", "diary", "people", "work_log"):
            _registry.remove(p)

    register(WorldProvider(self._data_dir))
    register(DiaryProvider(self._data_dir))
    register(PeopleProvider(self._data_dir))
    register(WorkLogProvider(self._data_dir))
```

**Step 5: 运行测试，确认通过**

```
python3 -m pytest tests/unit/layers/capabilities/reports/test_daily_report.py -v
```

预期：所有测试（包含新增 1 个）通过

**Step 6: 提交**

```
git add huaqi_src/layers/capabilities/reports/daily_report.py tests/unit/layers/capabilities/reports/test_daily_report.py
git commit -m "feat: register WorkLogProvider in DailyReportAgent"
```

---

## Task 5: 全量测试通过

**Step 1: 运行全部测试**

```
python3 -m pytest tests/ -v
```

**Step 2: 如有失败，按以下思路排查**

| 错误类型 | 常见原因 | 解决方式 |
|----------|----------|----------|
| `_registry` 被污染 | 测试间注册表未清空 | 在测试函数开头加 `_registry.clear()` |
| `work_logs` 目录不存在 | `WorkLogProvider.get_context` 未处理缺失目录 | 确认已有 `if not work_logs_dir.exists(): return None` |
| `time_start` 解析错误 | 时间字符串格式不一致 | 在 `WorkLogWriter.write()` 中统一用 ISO 8601 格式 |
| import 循环 | `work_log.py` 导入路径有误 | 检查 import 路径是否用 `huaqi_src.config.paths` 而非 `huaqi_src.core.config_paths` |

**Step 3: 提交**

```
git add -A
git commit -m "test: all worklog tests passing"
```

---

## 后续扩展指南

如需让 WorkLog 也参与周报（汇总一周编程工作），只需：

1. 将 `WorkLogProvider.supported_reports` 改为 `["daily", "weekly"]`
2. 在 `get_context()` 中增加 `report_type == "weekly"` 分支，扫描 `date_range.start` 到 `date_range.end` 之间的所有 WorkLog 文件
3. 在 `WeeklyReportAgent._register_providers()` 中加入 `WorkLogProvider`
