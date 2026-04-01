"""system 和 daemon 子命令"""

import time
from datetime import datetime
from pathlib import Path

import typer
from rich.table import Table

from huaqi_src.cli.context import console, ensure_initialized

system_app = typer.Typer(name="system", help="系统管理")


@system_app.command("webhook")
def webhook_server(
    host: str = typer.Option("127.0.0.1", "--host", help="监听地址"),
    port: int = typer.Option(8080, "--port", help="监听端口"),
):
    """启动外部事件的 Webhook 监听服务器"""
    ensure_initialized()
    from huaqi_src.integrations.wechat_webhook import run_server

    console.print(f"\n[bold green]🚀 启动 Webhook 接收服务器 ({host}:{port})[/bold green]")
    console.print('[dim]测试命令: curl -X POST http://127.0.0.1:8080/api/webhook/wechat -d \'{"actor": "张三", "content": "你好呀"}\'[/dim]')
    console.print("[dim]使用 Ctrl+C 停止服务器...[/dim]\n")
    
    try:
        run_server(host=host, port=port)
    except KeyboardInterrupt:
        console.print("\n[dim]Webhook 服务器已关闭。[/dim]")

@system_app.callback(invoke_without_command=True)
def system_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@system_app.command("show")
def system_show():
    """显示系统状态"""
    import huaqi_src.cli.context as ctx
    ensure_initialized()

    console.print("\n[bold cyan]🔧 系统状态[/bold cyan]\n")

    console.print(f"  数据目录: [cyan]{ctx.DATA_DIR}[/cyan]")

    from huaqi_src.core.config_paths import get_memory_dir
    memory_dir = get_memory_dir()
    memory_count = len(list(memory_dir.glob("*.md"))) if memory_dir.exists() else 0
    console.print(f"  记忆文件: [cyan]{memory_count}[/cyan] 条")

    if ctx._git is not None:
        git_status = ctx._git.get_status()
        if git_status.get("initialized"):
            remote_url = git_status.get("remote_url") or "(未配置)"
            branch = git_status.get("branch") or "main"
            auto_push = "开启" if git_status.get("auto_push") else "关闭"
            console.print(f"  Git 远程: [cyan]{remote_url}[/cyan]")
            console.print(f"  Git 分支: [cyan]{branch}[/cyan]")
            console.print(f"  自动推送: [cyan]{auto_push}[/cyan]")
        else:
            console.print("  Git: [dim]未初始化[/dim]")
    else:
        console.print("  Git: [dim]未初始化[/dim]")

    console.print()


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

    from huaqi_src.core.config_paths import get_memory_dir
    memory_dir = get_memory_dir()

    if memory_dir.exists():
        shutil.copytree(memory_dir, backup_dir / "memory", dirs_exist_ok=True)
        console.print(f"\n[green]✅ 备份已创建: {backup_dir}[/green]\n")
    else:
        console.print("\n[yellow]无数据可备份[/yellow]\n")


_PLIST_LABEL = "com.huaqi.daemon"
_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{_PLIST_LABEL}.plist"


def _get_plist_content(huaqi_bin: str, log_dir: Path) -> str:
    log_dir.mkdir(parents=True, exist_ok=True)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{huaqi_bin}</string>
        <string>daemon</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/daemon.err</string>
</dict>
</plist>
"""


def daemon_command_handler(
    action: str = typer.Argument(..., help="操作: start/stop/status/list/install/uninstall"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="前台运行模式"),
):
    """管理后台定时任务服务"""
    ensure_initialized()

    from huaqi_src.scheduler import get_scheduler_manager, register_default_jobs, default_scheduler_config

    scheduler = get_scheduler_manager()

    if action == "install":
        import shutil
        import subprocess
        huaqi_bin = shutil.which("huaqi") or "/usr/local/bin/huaqi"
        import huaqi_src.cli.context as _ctx
        log_dir = _ctx.DATA_DIR / "logs"
        _PLIST_PATH.write_text(_get_plist_content(huaqi_bin, log_dir), encoding="utf-8")
        result = subprocess.run(["launchctl", "load", "-w", str(_PLIST_PATH)], capture_output=True, text=True)
        if result.returncode == 0:
            console.print(f"[green]✅ Daemon 已安装并启动 (开机自启)[/green]")
            console.print(f"[dim]plist: {_PLIST_PATH}[/dim]")
            console.print(f"[dim]日志: {log_dir}/daemon.log[/dim]\n")
        else:
            console.print(f"[red]❌ launchctl load 失败: {result.stderr}[/red]")
        return

    if action == "uninstall":
        import subprocess
        if _PLIST_PATH.exists():
            subprocess.run(["launchctl", "unload", "-w", str(_PLIST_PATH)], capture_output=True)
            _PLIST_PATH.unlink()
            console.print("[green]✅ Daemon 已卸载并移除开机自启[/green]\n")
        else:
            console.print("[yellow]⚠️ 未找到已安装的 plist[/yellow]\n")
        return

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
