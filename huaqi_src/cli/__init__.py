"""Huaqi CLI 包

将所有子命令挂载到主 app，供 cli.py 入口调用。
"""

from pathlib import Path
from typing import Optional

import typer

from huaqi_src.cli.context import console
from huaqi_src.cli.commands.config import config_app
from huaqi_src.cli.commands.profile import profile_app
from huaqi_src.cli.commands.pipeline import pipeline_app
from huaqi_src.cli.commands.personality import personality_app
from huaqi_src.cli.commands.system import system_app, daemon_command_handler

app = typer.Typer(
    name="huaqi",
    help="个人 AI 同伴系统",
    no_args_is_help=False,
)

app.add_typer(config_app)
app.add_typer(profile_app)
app.add_typer(pipeline_app)
app.add_typer(personality_app)
app.add_typer(system_app)


@app.command("chat")
def chat_command(
    use_langgraph: bool = typer.Option(True, "--langgraph/--legacy", help="使用 LangGraph Agent 模式"),
):
    """启动对话模式 (新版 LangGraph Agent)"""
    from huaqi_src.cli.context import ensure_initialized
    from huaqi_src.cli.chat import run_langgraph_chat, chat_mode

    ensure_initialized()

    if use_langgraph:
        run_langgraph_chat()
    else:
        chat_mode()


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


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", "-d", help="数据目录路径"),
):
    """Huaqi - 个人 AI 同伴系统"""
    from huaqi_src.core.config_paths import (
        set_data_dir, get_data_dir, is_data_dir_set, save_data_dir_to_config
    )
    import huaqi_src.cli.context as _ctx

    if data_dir is not None:
        set_data_dir(data_dir)
        save_data_dir_to_config(data_dir)

    if not is_data_dir_set():
        console.print("\n[bold red]❌ 错误: 未指定数据目录[/bold red]\n")
        console.print("请使用以下方式之一指定数据存储目录:\n")
        console.print("  [cyan]1. 命令行参数:[/cyan]")
        console.print("     huaqi --data-dir /path/to/data\n")
        console.print("  [cyan]2. 环境变量:[/cyan]")
        console.print("     export HUAQI_DATA_DIR=/path/to/data")
        console.print("     huaqi\n")
        console.print("  [cyan]3. 简写形式:[/cyan]")
        console.print("     huaqi -d /path/to/data\n")
        raise typer.Exit(1)

    _ctx.DATA_DIR = get_data_dir()
    _ctx.MEMORY_DIR = _ctx.DATA_DIR / "memory"

    if ctx.invoked_subcommand is None:
        from huaqi_src.cli.chat import chat_mode
        chat_mode()
