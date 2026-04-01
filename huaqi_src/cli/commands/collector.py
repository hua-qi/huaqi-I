import typer
from huaqi_src.collectors.cli_chat_watcher import CLIChatWatcher

app = typer.Typer(name="collector", help="数据采集器管理")


@app.command("status")
def status():
    """查看数据采集器状态"""
    from huaqi_src.core.config_manager import ConfigManager
    from huaqi_src.core.config_paths import get_data_dir

    cfg = ConfigManager()
    cli_chat_enabled = cfg.is_enabled("cli_chat")

    data_dir = get_data_dir()
    typer.echo(f"数据目录: {data_dir or '未设置'}")
    typer.echo(f"CLI 对话监听 (modules.cli_chat): {'✓ 已开启' if cli_chat_enabled else '✗ 已关闭'}")


@app.command("sync-cli")
def sync_cli():
    """手动触发一次 CLI 对话历史同步"""
    typer.echo("正在同步 CLI 对话记录...")
    watcher = CLIChatWatcher()
    docs = watcher.sync_all()
    if not docs:
        typer.echo("没有新的 CLI 对话记录。")
    else:
        typer.echo(f"已同步 {len(docs)} 个对话文件。")
