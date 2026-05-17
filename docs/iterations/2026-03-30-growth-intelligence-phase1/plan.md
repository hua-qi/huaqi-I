# Growth Intelligence Phase 1 实施计划

**Goal:** 实现成长智能 Phase 1 —— 完善 Inbox 文档导入、世界感知定时抓取（含 RSS 数据源配置）、日终复盘报告，并为 Agent 扩展对应 Tool。

**Architecture:** 在现有 `InboxProcessor`、`WorldNewsFetcher`、`MorningBriefAgent`、`SchedulerManager` 基础上最小化扩展。新增 `EveningReviewAgent`（日终复盘）、`inbox list` 命令、`world fetch` CLI 命令、世界抓取定时任务（07:00）、日终复盘定时任务（23:00）；同时在 `huaqi_src/agent/tools.py` 补充 `search_cli_chats_tool` 工具，使 Agent 能自主检索 cli_chats 数据。

**Tech Stack:** Python, LangChain Tools, APScheduler CronTrigger, Typer CLI, pytest

---

## 快速入门

测试命令：
```bash
pytest tests/ -x -q
```

Lint 检查：
```bash
ruff check huaqi_src/ tests/
```

---

## Task 1: `inbox list` 命令

设计文档要求 `huaqi inbox list` 命令列出已导入文档，但当前 `huaqi_src/cli/inbox.py` 只有 `sync` 和 `status`，缺少 `list`。

**Files:**
- Modify: `huaqi_src/cli/inbox.py`
- Modify: `tests/cli/test_inbox_cli.py`

### Step 1: 写失败测试

追加到 `tests/cli/test_inbox_cli.py`：

```python
def test_inbox_list_shows_archived_files(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    archive_dir = tmp_path / "memory" / "work_docs"
    archive_dir.mkdir(parents=True)
    (archive_dir / "report.md").write_text("季度报告", encoding="utf-8")

    result = runner.invoke(app, ["inbox", "list"])
    assert result.exit_code == 0
    assert "report.md" in result.output

def test_inbox_list_shows_empty_when_no_docs(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)

    result = runner.invoke(app, ["inbox", "list"])
    assert result.exit_code == 0
    assert "0" in result.output or "没有" in result.output or "已导入" in result.output
```

### Step 2: 运行测试确认失败

```bash
pytest tests/cli/test_inbox_cli.py::test_inbox_list_shows_archived_files -v
```

期望：FAILED（`No such command 'list'`）

### Step 3: 在 `huaqi_src/cli/inbox.py` 添加 `list` 命令

在 `status` 命令之后追加：

```python
@app.command("list")
def list_docs():
    """列出已导入到记忆库的工作文档"""
    from huaqi_src.core.config_paths import get_data_dir

    data_dir = get_data_dir()
    if data_dir is None:
        typer.echo("错误：数据目录未设置。", err=True)
        raise typer.Exit(1)

    archive_dir = Path(data_dir) / "memory" / "work_docs"
    archive_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(
        [f for f in archive_dir.iterdir() if f.suffix.lower() in {".md", ".txt"}]
    )
    if not files:
        typer.echo("已导入文档：0 个")
        return

    typer.echo(f"已导入文档：{len(files)} 个")
    for f in files:
        typer.echo(f"  - {f.name}")
```

### Step 4: 运行测试确认通过

```bash
pytest tests/cli/test_inbox_cli.py -v
```

期望：全部 PASSED

---

## Task 2: 世界感知定时抓取任务（07:00）

`WorldNewsFetcher` 和 `RSSSource` 已实现，但缺少：
1. `huaqi world fetch` CLI 命令（手动触发）
2. 07:00 定时任务注册

**Files:**
- Create: `huaqi_src/cli/commands/world.py`
- Modify: `huaqi_src/cli/__init__.py`
- Modify: `huaqi_src/scheduler/jobs.py`
- Modify: `tests/scheduler/test_jobs.py`

### Step 1: 写失败测试（定时任务注册）

替换 `tests/scheduler/test_jobs.py` 全部内容：

```python
from unittest.mock import MagicMock
from huaqi_src.scheduler.jobs import register_default_jobs


def test_register_default_jobs_adds_morning_brief():
    mock_manager = MagicMock()
    mock_manager.add_cron_job.return_value = True

    register_default_jobs(mock_manager)

    call_ids = [
        c[1].get("job_id") or c[0][0]
        for c in mock_manager.add_cron_job.call_args_list
    ]
    assert "morning_brief" in call_ids


def test_register_default_jobs_adds_world_fetch():
    mock_manager = MagicMock()
    mock_manager.add_cron_job.return_value = True

    register_default_jobs(mock_manager)

    call_ids = [
        c[1].get("job_id") or c[0][0]
        for c in mock_manager.add_cron_job.call_args_list
    ]
    assert "world_fetch" in call_ids
```

### Step 2: 运行测试确认失败

```bash
pytest tests/scheduler/test_jobs.py::test_register_default_jobs_adds_world_fetch -v
```

期望：FAILED（`assert 'world_fetch' in ...`）

### Step 3: 修改 `huaqi_src/scheduler/jobs.py`

```python
from huaqi_src.scheduler.manager import SchedulerManager


def _run_morning_brief():
    from huaqi_src.reports.morning_brief import MorningBriefAgent
    try:
        agent = MorningBriefAgent()
        agent.run()
    except Exception as e:
        print(f"[MorningBrief] 生成失败: {e}")


def _run_world_fetch():
    from huaqi_src.world.fetcher import WorldNewsFetcher
    from huaqi_src.world.storage import WorldNewsStorage
    from huaqi_src.core.config_simple import load_config
    try:
        cfg = load_config() or {}
        world_sources_cfg = cfg.get("world_sources", [])
        sources = _build_world_sources(world_sources_cfg)
        fetcher = WorldNewsFetcher(sources=sources)
        docs = fetcher.fetch_all()
        if docs:
            storage = WorldNewsStorage()
            storage.save(docs)
            print(f"[WorldFetch] 已保存 {len(docs)} 条世界新闻")
        else:
            print("[WorldFetch] 本次未抓取到新闻")
    except Exception as e:
        print(f"[WorldFetch] 抓取失败: {e}")


def _build_world_sources(sources_cfg: list) -> list:
    from huaqi_src.world.sources.rss_source import RSSSource
    sources = []
    for item in sources_cfg:
        if item.get("type") == "rss" and item.get("url") and item.get("enabled", True):
            sources.append(RSSSource(url=item["url"], name=item.get("name", "")))
    return sources


def register_default_jobs(manager: SchedulerManager):
    manager.add_cron_job(
        job_id="morning_brief",
        func=_run_morning_brief,
        cron="0 8 * * *",
    )
    manager.add_cron_job(
        job_id="world_fetch",
        func=_run_world_fetch,
        cron="0 7 * * *",
    )
```

### Step 4: 运行测试确认通过

```bash
pytest tests/scheduler/test_jobs.py -v
```

期望：全部 PASSED

### Step 5: 创建 `huaqi_src/cli/commands/world.py`

```python
import typer

app = typer.Typer(name="world", help="世界感知：抓取和查看世界热点信息")


@app.command("fetch")
def fetch():
    """立即抓取世界新闻（无需等待定时任务）"""
    from huaqi_src.scheduler.jobs import _run_world_fetch
    typer.echo("正在抓取世界新闻...")
    _run_world_fetch()
    typer.echo("完成。")


@app.command("status")
def world_status():
    """查看已缓存的世界新闻摘要文件"""
    from pathlib import Path
    from huaqi_src.core.config_paths import get_data_dir

    data_dir = get_data_dir()
    if data_dir is None:
        typer.echo("错误：数据目录未设置。", err=True)
        raise typer.Exit(1)

    world_dir = Path(data_dir) / "world"
    world_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(world_dir.glob("*.md"), reverse=True)[:7]
    if not files:
        typer.echo("暂无世界新闻缓存。使用 `huaqi world fetch` 立即抓取。")
        return

    typer.echo(f"最近 {len(files)} 天的世界新闻摘要：")
    for f in files:
        typer.echo(f"  - {f.stem}")
```

### Step 6: 在 `huaqi_src/cli/__init__.py` 挂载 world 子命令

在现有 import 块末尾添加（紧接 `from huaqi_src.cli.inbox import app as inbox_app` 之后）：

```python
from huaqi_src.cli.commands.world import app as world_app
```

在 `app.add_typer(inbox_app, name="inbox", rich_help_panel="操作工具")` 之后添加：

```python
app.add_typer(world_app, name="world", rich_help_panel="操作工具")
```

### Step 7: 运行全量测试确认无破坏

```bash
pytest tests/ -x -q
```

期望：全部 PASSED

---

## Task 3: 日终复盘报告 Agent

**Files:**
- Create: `huaqi_src/reports/evening_review.py`
- Create: `tests/reports/test_evening_review.py`
- Modify: `huaqi_src/scheduler/jobs.py`
- Modify: `tests/scheduler/test_jobs.py`

### Step 1: 写失败测试

创建 `tests/reports/test_evening_review.py`：

```python
import datetime
import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.reports.evening_review import EveningReviewAgent


def test_evening_review_creates_report_file(tmp_path):
    agent = EveningReviewAgent(data_dir=tmp_path)

    fake_review = "今日复盘：完成了三件事，情绪稳定。"
    with patch.object(agent, "_generate_review", return_value=fake_review):
        agent.run()

    report_dir = tmp_path / "reports" / "daily"
    files = list(report_dir.glob("*-evening.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "复盘" in content


def test_evening_review_includes_diary_context(tmp_path):
    diary_dir = tmp_path / "memory" / "diary"
    diary_dir.mkdir(parents=True)
    today = datetime.date.today().isoformat()
    (diary_dir / f"{today}.md").write_text("今天完成了一项重要工作。", encoding="utf-8")

    agent = EveningReviewAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "今天完成了" in context or "日记" in context


def test_evening_review_build_context_no_data(tmp_path):
    agent = EveningReviewAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert isinstance(context, str)
    assert len(context) > 0
```

### Step 2: 运行测试确认失败

```bash
pytest tests/reports/test_evening_review.py -v
```

期望：FAILED（`ModuleNotFoundError: No module named '...evening_review'`）

### Step 3: 创建 `huaqi_src/reports/evening_review.py`

```python
import datetime
from pathlib import Path
from typing import Optional


class EveningReviewAgent:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from huaqi_src.core.config_paths import require_data_dir
            data_dir = require_data_dir()
        self.data_dir = Path(data_dir)

    def _build_context(self) -> str:
        sections = []

        diary_dir = self.data_dir / "memory" / "diary"
        if diary_dir.exists():
            today = datetime.date.today().isoformat()
            today_diary = diary_dir / f"{today}.md"
            if today_diary.exists():
                sections.append("## 今日日记\n" + today_diary.read_text(encoding="utf-8")[:800])

        work_docs_dir = self.data_dir / "memory" / "work_docs"
        if work_docs_dir.exists():
            recent_docs = sorted(work_docs_dir.glob("*.md"), reverse=True)[:2]
            if recent_docs:
                snippets = [f.read_text(encoding="utf-8")[:200] for f in recent_docs]
                sections.append("## 近期工作文档\n" + "\n---\n".join(snippets))

        return "\n\n".join(sections) if sections else "今日暂无记录数据。"

    def _generate_review(self) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage

        context = self._build_context()

        from huaqi_src.cli.context import build_llm_manager
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=600)
        if llm_mgr is None:
            return "（LLM 未配置，无法生成复盘）"

        active_name = llm_mgr.get_active_provider()
        if not active_name:
            return "（未配置任何 LLM 提供商）"
        cfg = llm_mgr._configs[active_name]

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.7,
            max_tokens=600,
        )

        system_prompt = (
            "你是 huaqi，用户的 AI 同伴。请根据以下背景信息，生成一份简洁温暖的日终复盘，"
            "包含：1）今日主要事项回顾，2）情绪状态观察，3）一句明日鼓励的话。"
            "复盘应简短，不超过 400 字。"
        )

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"背景信息：\n{context}"),
        ])
        return response.content

    def run(self) -> str:
        review = self._generate_review()

        report_dir = self.data_dir / "reports" / "daily"
        report_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.date.today().isoformat()
        report_file = report_dir / f"{today}-evening.md"
        report_file.write_text(
            f"# 日终复盘 {today}\n\n{review}\n",
            encoding="utf-8",
        )

        return review
```

### Step 4: 运行测试确认通过

```bash
pytest tests/reports/test_evening_review.py -v
```

期望：全部 PASSED

### Step 5: 在 `huaqi_src/scheduler/jobs.py` 添加日终复盘任务

在 `_run_world_fetch` 函数之后，`register_default_jobs` 之前，添加：

```python
def _run_evening_review():
    from huaqi_src.reports.evening_review import EveningReviewAgent
    try:
        agent = EveningReviewAgent()
        agent.run()
    except Exception as e:
        print(f"[EveningReview] 生成失败: {e}")
```

在 `register_default_jobs` 中追加：

```python
    manager.add_cron_job(
        job_id="evening_review",
        func=_run_evening_review,
        cron="0 23 * * *",
    )
```

### Step 6: 在 `tests/scheduler/test_jobs.py` 添加测试

追加：

```python
def test_register_default_jobs_adds_evening_review():
    mock_manager = MagicMock()
    mock_manager.add_cron_job.return_value = True

    register_default_jobs(mock_manager)

    call_ids = [
        c[1].get("job_id") or c[0][0]
        for c in mock_manager.add_cron_job.call_args_list
    ]
    assert "evening_review" in call_ids
```

### Step 7: 运行测试确认通过

```bash
pytest tests/scheduler/test_jobs.py -v
```

期望：全部 PASSED

---

## Task 4: Agent Tool — `search_cli_chats_tool`

设计文档要求 Agent 可搜索 `cli_chats` 数据，当前 `tools.py` 缺少该 Tool。

**Files:**
- Modify: `huaqi_src/agent/tools.py`
- Modify: `tests/agent/test_tools.py`

### Step 1: 查看现有测试文件结构

```bash
pytest tests/agent/test_tools.py -v
```

### Step 2: 写失败测试

打开 `tests/agent/test_tools.py`，追加：

```python
def test_search_cli_chats_tool_returns_string(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.agent.tools import search_cli_chats_tool
    result = search_cli_chats_tool.invoke({"query": "测试查询"})
    assert isinstance(result, str)


def test_search_cli_chats_tool_finds_content(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    cli_chats_dir = tmp_path / "memory" / "cli_chats"
    cli_chats_dir.mkdir(parents=True)
    (cli_chats_dir / "session-001.md").write_text(
        "# 对话记录\n今天用 codeflicker 帮助实现了新功能。",
        encoding="utf-8",
    )
    from huaqi_src.agent.tools import search_cli_chats_tool
    result = search_cli_chats_tool.invoke({"query": "codeflicker"})
    assert "codeflicker" in result or "对话" in result
```

### Step 3: 运行测试确认失败

```bash
pytest tests/agent/test_tools.py::test_search_cli_chats_tool_returns_string -v
```

期望：FAILED（`cannot import name 'search_cli_chats_tool'`）

### Step 4: 在 `huaqi_src/agent/tools.py` 添加新 Tool

在文件末尾追加：

```python
@tool
def search_cli_chats_tool(query: str) -> str:
    """搜索用户与其他 CLI Agent（如 codeflicker、Claude）的对话记录。当用户询问与 AI 工具的历史对话、曾经讨论过的技术问题或代码任务时使用。"""
    from pathlib import Path
    from huaqi_src.core.config_paths import get_data_dir

    data_dir = get_data_dir()
    if data_dir is None:
        return f"未找到 CLI 对话记录（数据目录未设置）。"

    cli_chats_dir = Path(data_dir) / "memory" / "cli_chats"
    if not cli_chats_dir.exists():
        return f"未找到包含 '{query}' 的 CLI 对话记录。"

    results = []
    query_lower = query.lower()
    for doc_file in sorted(cli_chats_dir.rglob("*.md"), reverse=True):
        try:
            content = doc_file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                results.append(f"文件: {doc_file.name}\n内容摘要: {content[:300]}")
        except Exception:
            continue

    if not results:
        return f"未找到包含 '{query}' 的 CLI 对话记录。"

    return "找到以下 CLI 对话记录：\n\n" + "\n---\n".join(results[:3])
```

### Step 5: 运行测试确认通过

```bash
pytest tests/agent/test_tools.py -v
```

期望：全部 PASSED

---

## Task 5: 全量验证

### Step 1: 运行所有测试

```bash
pytest tests/ -x -q
```

期望：全部 PASSED，无报错

### Step 2: Lint 检查

```bash
ruff check huaqi_src/ tests/
```

期望：无报错（或仅有已知的 `#` 注释风格警告）

### Step 3: 手动验证 CLI 命令注册

```bash
python cli.py --help
python cli.py inbox --help
python cli.py world --help
```

期望：`inbox` 显示 `sync`、`status`、`list` 三个命令；`world` 显示 `fetch`、`status` 两个命令。
