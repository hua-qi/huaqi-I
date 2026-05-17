# CLI 报告查看与生成系统 Implementation Plan

**Goal:** 实现一个统一的 ReportManager 和 CLI 命令（包括顶层和聊天内命令），用于查找和实时生成各类报告。

**Architecture:** 将报告检索与生成职责封装在 ReportManager 中，向外暴露 `get_or_generate_report` 接口。顶层 CLI 和聊天内的 `/report` 指令通过该管理器获取内容并打印展示。

**Tech Stack:** Python, Typer, Rich

---

### Task 1: ReportManager 核心逻辑

**Files:**
- Create: `huaqi_src/layers/capabilities/reports/manager.py`
- Create: `tests/layers/capabilities/reports/test_manager.py`

**Step 1: Write the failing test**

```python
# tests/layers/capabilities/reports/test_manager.py
import pytest
from unittest.mock import patch, MagicMock
from huaqi_src.layers.capabilities.reports.manager import ReportManager

def test_get_or_generate_report_not_found(tmp_path):
    manager = ReportManager(data_dir=tmp_path)
    result = manager.get_or_generate_report("morning", date_str="2000-01-01")
    assert "无法生成历史日期的报告" in result

@patch('huaqi_src.layers.capabilities.reports.manager.MorningBriefAgent')
def test_get_or_generate_report_today(mock_agent_class, tmp_path):
    mock_agent = MagicMock()
    mock_agent_class.return_value = mock_agent
    
    manager = ReportManager(data_dir=tmp_path)
    manager.get_or_generate_report("morning", date_str="today")
    mock_agent.run.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `mkdir -p tests/layers/capabilities/reports && touch tests/layers/capabilities/reports/__init__.py && pytest tests/layers/capabilities/reports/test_manager.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError for `ReportManager`

**Step 3: Write minimal implementation**

```python
# huaqi_src/layers/capabilities/reports/manager.py
import datetime
from pathlib import Path
from typing import Optional
from huaqi_src.layers.capabilities.reports.morning_brief import MorningBriefAgent
from huaqi_src.layers.capabilities.reports.daily_report import DailyReportAgent
from huaqi_src.layers.capabilities.reports.weekly_report import WeeklyReportAgent
from huaqi_src.layers.capabilities.reports.quarterly_report import QuarterlyReportAgent
from huaqi_src.config.paths import require_data_dir

class ReportManager:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or require_data_dir()
        self.reports_dir = self.data_dir / "reports"

    def get_or_generate_report(self, report_type: str, date_str: str = "today", force: bool = False) -> str:
        today = datetime.date.today()
        if date_str == "today":
            target_date = today
        elif date_str == "yesterday":
            target_date = today - datetime.timedelta(days=1)
        else:
            try:
                target_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return f"日期格式错误: {date_str}，请使用 YYYY-MM-DD"
            
        date_iso = target_date.isoformat()
        
        mapping = {
            "morning": ("daily", f"{date_iso}-morning.md", MorningBriefAgent),
            "daily": ("daily", f"{date_iso}-evening.md", DailyReportAgent),
            "weekly": ("weekly", f"{date_iso}-weekly.md", WeeklyReportAgent),
            "quarterly": ("quarterly", f"{date_iso}-quarterly.md", QuarterlyReportAgent),
        }
        
        if report_type not in mapping:
            return f"未知的报告类型: {report_type}"
            
        subdir, filename, agent_class = mapping[report_type]
        file_path = self.reports_dir / subdir / filename
        
        if not force and file_path.exists():
            return file_path.read_text(encoding="utf-8")
            
        if target_date != today:
            return f"无法生成历史日期的报告: {date_iso}，且未找到已有文件。"
            
        # 实时生成
        agent = agent_class(data_dir=self.data_dir)
        try:
            agent.run()
        except Exception as e:
            return f"报告生成失败: {str(e)}"
        
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        
        return "报告已触发生成，但未找到输出文件。"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/layers/capabilities/reports/test_manager.py -v`
Expected: PASS

**Step 5: Commit**

Run: `git add huaqi_src/layers/capabilities/reports/manager.py tests/layers/capabilities/reports/test_manager.py tests/layers/capabilities/reports/__init__.py && git commit -m "feat: implement ReportManager for retrieving and generating reports"`

---

### Task 2: 顶级 CLI 命令 (CLI Top Level)

**Files:**
- Create: `huaqi_src/cli/commands/report.py`
- Modify: `huaqi_src/cli/__init__.py` (line 19, 36)
- Test: `tests/cli/commands/test_report.py`

**Step 1: Write the failing test**

```python
# tests/cli/commands/test_report.py
from typer.testing import CliRunner
from huaqi_src.cli import app

runner = CliRunner()

def test_report_command_help():
    result = runner.invoke(app, ["report", "--help"])
    assert result.exit_code == 0
    assert "morning" in result.output
    assert "daily" in result.output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/commands/test_report.py -v`
Expected: FAIL with "No such command 'report'."

**Step 3: Write minimal implementation**

```python
# huaqi_src/cli/commands/report.py
import typer
from huaqi_src.cli.context import console
from huaqi_src.layers.capabilities.reports.manager import ReportManager

report_app = typer.Typer(help="报告查看与生成")

@report_app.command("morning")
def morning_cmd(
    date: str = typer.Argument("today", help="日期 (today, yesterday, YYYY-MM-DD)"),
    force: bool = typer.Option(False, "--force", "-f", help="强制重新生成")
):
    """查看或生成晨间简报"""
    manager = ReportManager()
    console.print("[dim]正在获取晨间简报...[/dim]")
    content = manager.get_or_generate_report("morning", date, force)
    console.print(f"\n{content}\n")

@report_app.command("daily")
def daily_cmd(
    date: str = typer.Argument("today", help="日期 (today, yesterday, YYYY-MM-DD)"),
    force: bool = typer.Option(False, "--force", "-f", help="强制重新生成")
):
    """查看或生成日终复盘"""
    manager = ReportManager()
    console.print("[dim]正在获取日终复盘...[/dim]")
    content = manager.get_or_generate_report("daily", date, force)
    console.print(f"\n{content}\n")
    
@report_app.command("weekly")
def weekly_cmd(
    date: str = typer.Argument("today", help="日期 (today, yesterday, YYYY-MM-DD)"),
    force: bool = typer.Option(False, "--force", "-f", help="强制重新生成")
):
    """查看或生成周报"""
    manager = ReportManager()
    console.print("[dim]正在获取周报...[/dim]")
    content = manager.get_or_generate_report("weekly", date, force)
    console.print(f"\n{content}\n")
```

Modify `huaqi_src/cli/__init__.py`, around line 19-20, add import:
```python
from huaqi_src.cli.commands.study import study_app
from huaqi_src.cli.commands.report import report_app
```

Modify `huaqi_src/cli/__init__.py`, around line 36-37, add typer mount:
```python
app.add_typer(study_app, name="study", rich_help_panel="操作工具")
app.add_typer(report_app, name="report", rich_help_panel="操作工具")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/commands/test_report.py -v`
Expected: PASS

**Step 5: Commit**

Run: `git add huaqi_src/cli/commands/report.py huaqi_src/cli/__init__.py tests/cli/commands/test_report.py && git commit -m "feat: add top-level report CLI commands"`

---

### Task 3: 聊天内命令集成 (Chat Command)

**Files:**
- Modify: `huaqi_src/cli/chat.py`
- Test: `tests/cli/test_chat_report.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_chat_report.py
from unittest.mock import patch
from huaqi_src.cli.chat import _handle_report_command

@patch('huaqi_src.cli.chat.console.print')
@patch('huaqi_src.cli.chat.ReportManager')
def test_handle_report_morning(mock_manager_class, mock_print):
    mock_manager = mock_manager_class.return_value
    mock_manager.get_or_generate_report.return_value = "Mock Morning Content"
    
    _handle_report_command(["/report", "morning", "today"])
    
    mock_manager.get_or_generate_report.assert_called_with("morning", "today")
    mock_print.assert_any_call("\nMock Morning Content\n")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_chat_report.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Modify `huaqi_src/cli/chat.py`, completely replace the `_handle_report_command` function (around lines 152-194):

```python
def _handle_report_command(parts: list):
    """处理报告命令"""
    from huaqi_src.layers.capabilities.pattern.engine import get_pattern_engine
    from huaqi_src.layers.capabilities.reports.manager import ReportManager
    from huaqi_src.cli.context import console

    engine = get_pattern_engine()
    manager = ReportManager()

    if len(parts) < 2:
        console.print("[yellow]用法: /report [morning|daily|weekly|quarterly|insights] [date][/yellow]\n")
        return

    subcmd = parts[1]
    date_str = parts[2] if len(parts) > 2 else "today"

    if subcmd in ("morning", "daily", "weekly", "quarterly", "w"):
        report_type = "weekly" if subcmd == "w" else subcmd
        console.print(f"[dim]正在获取 {report_type} 报告...[/dim]")
        content = manager.get_or_generate_report(report_type, date_str)
        console.print(f"\n{content}\n")
    elif subcmd in ("insights", "i"):
        insights = engine.get_active_insights()
        if insights:
            console.print("\n[bold]💡 你的模式洞察[/bold]\n")
            for insight in insights[:5]:
                emoji = "🔴" if insight.severity == "attention" else "🟡" if insight.severity == "warning" else "🟢" if insight.severity == "positive" else "🔵"
                console.print(f"{emoji} {insight.title}")
                console.print(f"   {insight.description}")
                if insight.recommendation:
                    console.print(f"   💡 {insight.recommendation}")
                console.print()
        else:
            console.print("[dim]暂无洞察，继续记录日记和对话，我会更了解你。[/dim]\n")
    else:
        console.print("[yellow]用法: /report [morning|daily|weekly|quarterly|insights] [date][/yellow]\n")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_chat_report.py -v`
Expected: PASS

**Step 5: Commit**

Run: `git add huaqi_src/cli/chat.py tests/cli/test_chat_report.py && git commit -m "feat: integrate report manager into chat command"`
