"""system 子命令"""

from datetime import datetime
from pathlib import Path

import typer

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

    from huaqi_src.config.paths import get_memory_dir
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

    from huaqi_src.config.hot_reload import get_hot_reload, init_hot_reload

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

    from huaqi_src.config.paths import get_memory_dir
    memory_dir = get_memory_dir()

    if memory_dir.exists():
        shutil.copytree(memory_dir, backup_dir / "memory", dirs_exist_ok=True)
        console.print(f"\n[green]✅ 备份已创建: {backup_dir}[/green]\n")
    else:
        console.print("\n[yellow]无数据可备份[/yellow]\n")
