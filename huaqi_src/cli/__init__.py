"""Huaqi CLI 包

将所有子命令挂载到主 app，供 cli.py 入口调用。
"""

from typing import Optional

import typer

from huaqi_src.cli.context import console
from huaqi_src.cli.commands.config import config_app
from huaqi_src.cli.commands.profile import profile_app
from huaqi_src.cli.commands.pipeline import pipeline_app
from huaqi_src.cli.commands.personality import personality_app
from huaqi_src.cli.commands.system import system_app, daemon_command_handler
from huaqi_src.cli.inbox import app as inbox_app
from huaqi_src.cli.commands.people import people_app
from huaqi_src.cli.commands.collector import app as collector_app
from huaqi_src.cli.commands.study import study_app
from huaqi_src.cli.commands.report import report_app
from huaqi_src.cli.commands.world import world_app
from huaqi_src.cli.commands.scheduler import scheduler_app

app = typer.Typer(
    name="huaqi",
    help="个人 AI 同伴系统",
    no_args_is_help=False,
    add_completion=False,
)

app.add_typer(config_app, rich_help_panel="配置管理")
app.add_typer(profile_app, rich_help_panel="配置管理")
app.add_typer(personality_app, rich_help_panel="配置管理")
app.add_typer(pipeline_app, rich_help_panel="操作工具")
app.add_typer(system_app, rich_help_panel="操作工具")
app.add_typer(inbox_app, name="inbox", rich_help_panel="操作工具")
app.add_typer(people_app, name="people", rich_help_panel="操作工具")
app.add_typer(collector_app, name="collector", rich_help_panel="操作工具")
app.add_typer(study_app, name="study", rich_help_panel="操作工具")
app.add_typer(report_app, name="report", rich_help_panel="操作工具")
app.add_typer(world_app, name="world", rich_help_panel="操作工具")
app.add_typer(scheduler_app, name="scheduler", rich_help_panel="操作工具")


@app.command("chat")
def chat_command(
    use_langgraph: bool = typer.Option(True, "--langgraph/--legacy", help="使用 LangGraph Agent 模式"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="恢复已有会话 ID（留空则新建）"),
    list_sessions: bool = typer.Option(False, "--list-sessions", "-l", help="列出最近会话"),
):
    """启动对话模式 (新版 LangGraph Agent)"""
    from huaqi_src.cli.context import ensure_initialized
    from huaqi_src.cli.chat import run_langgraph_chat, chat_mode

    ensure_initialized()

    if not use_langgraph:
        chat_mode()
        return

    if list_sessions:
        from huaqi_src.agent import load_sessions
        sessions = load_sessions()
        if not sessions:
            console.print("[dim]暂无历史会话[/dim]")
            return
        console.print("\n[bold cyan]📋 最近会话[/bold cyan]\n")
        for i, s in enumerate(sessions[:10], 1):
            last = s.get("last_active", "")[:16].replace("T", " ")
            turns = s.get("turns", 0)
            title = s.get("title", "无标题")
            tid = s["thread_id"][:8]
            console.print(f"  {i:2}. [{tid}...] {title}  [dim]{last} · {turns}轮[/dim]")
        console.print()
        return

    run_langgraph_chat(thread_id=session)


@app.command("status")
def show_status():
    """查看完整系统状态"""
    from huaqi_src.cli.context import ensure_initialized
    from huaqi_src.cli.chat import _show_detailed_status

    ensure_initialized()
    _show_detailed_status()


@app.command("daemon")
def daemon_command(
    action: str = typer.Argument(..., help="操作: start/stop/status/list"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="前台运行模式"),
):
    """管理后台定时任务服务"""
    daemon_command_handler(action=action, foreground=foreground)


@app.command("resume")
def resume_command(
    task_id: str = typer.Argument(..., help="要恢复的会话/任务 ID"),
    response: str = typer.Argument("confirm", help="提供给系统的回复，如 confirm/reject"),
):
    """恢复被中断的人机协同任务"""
    import asyncio
    from huaqi_src.agent.chat_agent import ChatAgent
    



    agent = ChatAgent(thread_id=task_id)
    
    async def _run_resume():
        print("回复: ", end="", flush=True)
        async for chunk in agent.resume(response):
            print(chunk, end="", flush=True)



    asyncio.run(_run_resume())


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
):
    """Huaqi - 个人 AI 同伴系统"""
    from huaqi_src.config.paths import is_data_dir_set, get_data_dir
    import huaqi_src.cli.context as _ctx

    if not is_data_dir_set():
        console.print("\n[bold yellow]👋 欢迎使用 Huaqi！[/bold yellow]\n")
        console.print("首次使用需要设置数据存储目录。\n")

        from huaqi_src.cli.commands.config import _wizard_set_data_dir
        _wizard_set_data_dir(_ctx)

    _ctx.DATA_DIR = get_data_dir()
    from huaqi_src.config.paths import get_memory_dir
    _ctx.MEMORY_DIR = get_memory_dir() if is_data_dir_set() else None

    if ctx.invoked_subcommand is None:
        from huaqi_src.cli.chat import run_langgraph_chat
        run_langgraph_chat()
