"""system 和 daemon 子命令"""

import time
from datetime import datetime
from pathlib import Path

import typer
from rich.table import Table

from huaqi_src.cli.context import console, ensure_initialized

system_app = typer.Typer(name="system", help="系统管理")


@system_app.callback(invoke_without_command=True)
def system_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@system_app.command("migrate")
def system_migrate(
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="预览模式"),
    skip_backup: bool = typer.Option(False, "--skip-backup", help="跳过备份（不推荐）"),
):
    """执行数据迁移 v3 -> v4"""
    import subprocess
    import sys

    script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "migrate_v3_to_v4.py"

    if not script_path.exists():
        console.print("[red]迁移脚本不存在[/red]")
        return

    cmd = [sys.executable, str(script_path)]
    if dry_run:
        cmd.append("--dry-run")
    if skip_backup:
        cmd.append("--skip-backup")

    console.print("\n[bold cyan]🔄 执行数据迁移...[/bold cyan]\n")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        console.print("\n[green]✅ 迁移完成[/green]\n")
    else:
        console.print("\n[red]❌ 迁移失败[/red]\n")


@system_app.command("hot-reload")
def system_hot_reload(
    action: str = typer.Argument("status", help="操作: start/stop/status"),
):
    """管理配置热重载"""
    import huaqi_src.cli.context as ctx
    ensure_initialized()

    from huaqi_src.core.config_hot_reload import get_hot_reload, init_hot_reload

    if action == "start":
        hot_reload = get_hot_reload()
        if hot_reload and hot_reload._running:
            console.print("[yellow]热重载已在运行中[/yellow]\n")
            return
        init_hot_reload(ctx._config)
        console.print("[green]✅ 配置热重载已启动[/green]\n")

    elif action == "stop":
        hot_reload = get_hot_reload()
        if hot_reload:
            hot_reload.stop()
            console.print("[dim]热重载已停止[/dim]\n")
        else:
            console.print("[dim]热重载未运行[/dim]\n")

    elif action == "status":
        hot_reload = get_hot_reload()
        if hot_reload and hot_reload._running:
            console.print("[green]● 热重载运行中[/green]\n")
        else:
            console.print("[dim]○ 热重载未运行[/dim]\n")


@system_app.command("backup")
def system_backup():
    """创建数据备份"""
    import shutil
    import huaqi_src.cli.context as ctx

    backup_dir = ctx.DATA_DIR / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    memory_dir = ctx.DATA_DIR / "memory"

    if memory_dir.exists():
        shutil.copytree(memory_dir, backup_dir / "memory", dirs_exist_ok=True)
        console.print(f"\n[green]✅ 备份已创建: {backup_dir}[/green]\n")
    else:
        console.print("\n[yellow]无数据可备份[/yellow]\n")


def daemon_command_handler(
    action: str = typer.Argument(..., help="操作: start/stop/status/list"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="前台运行模式"),
):
    """管理后台定时任务服务"""
    ensure_initialized()

    from huaqi_src.scheduler import get_scheduler_manager, register_default_jobs, default_scheduler_config

    scheduler = get_scheduler_manager()

    if action == "start":
        if scheduler.is_running():
            console.print("[yellow]⚠️ Daemon 已在运行中[/yellow]")
            return

        register_default_jobs(default_scheduler_config)
        scheduler.start()

        if foreground:
            console.print("[green]✅ Daemon 已启动 (前台模式)[/green]")
            console.print("[dim]按 Ctrl+C 停止[/dim]\n")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                scheduler.shutdown()
                console.print("\n[dim]Daemon 已停止[/dim]")
        else:
            console.print("[green]✅ Daemon 已启动 (后台模式)[/green]")
            console.print("[dim]使用 'huaqi daemon stop' 停止[/dim]\n")

    elif action == "stop":
        if not scheduler.is_running():
            console.print("[yellow]⚠️ Daemon 未在运行[/yellow]")
            return
        scheduler.shutdown()
        console.print("[green]✅ Daemon 已停止[/green]\n")

    elif action == "status":
        if scheduler.is_running():
            console.print("[green]● Daemon 运行中[/green]")
            jobs = scheduler.list_jobs()
            if jobs:
                console.print(f"\n[bold]已注册任务 ({len(jobs)}):[/bold]")
                for job in jobs:
                    next_run = job.get("next_run_time", "N/A")
                    console.print(f"  • {job['id']}: {job['trigger']}")
                    console.print(f"    下次执行: {next_run}")
            else:
                console.print("\n[dim]暂无任务[/dim]")
        else:
            console.print("[dim]○ Daemon 未运行[/dim]")
        console.print()

    elif action == "list":
        jobs = scheduler.list_jobs()
        if jobs:
            table = Table(title="定时任务列表")
            table.add_column("ID", style="cyan")
            table.add_column("触发器", style="green")
            table.add_column("下次执行", style="yellow")
            for job in jobs:
                next_run = job.get("next_run_time", "N/A")
                if next_run:
                    next_run = str(next_run)[:19]
                table.add_row(job["id"], job["trigger"], str(next_run))
            console.print(table)
        else:
            console.print("[dim]暂无任务[/dim]")
        console.print()

    else:
        console.print(f"[red]❌ 未知操作: {action}[/red]")
        console.print("可用操作: start, stop, status, list\n")
