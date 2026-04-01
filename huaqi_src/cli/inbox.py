import typer
from pathlib import Path

app = typer.Typer(name="inbox", help="管理待处理的导入文件")


@app.command("sync")
def sync():
    """处理 inbox 中所有待导入的文件"""
    from huaqi_src.collectors.inbox_processor import InboxProcessor

    processor = InboxProcessor()
    docs = processor.sync()

    if not docs:
        typer.echo("没有待处理的文件。")
        return

    typer.echo(f"已处理 {len(docs)} 个文件：")
    for doc in docs:
        typer.echo(f"  - {doc.source}")


@app.command("status")
def status():
    """查看 inbox 中待处理和已处理的文件"""
    from huaqi_src.core.config_paths import get_inbox_work_docs_dir, get_work_docs_dir, is_data_dir_set

    if not is_data_dir_set():
        typer.echo("错误：数据目录未设置。", err=True)
        raise typer.Exit(1)

    inbox_dir = get_inbox_work_docs_dir()
    archive_dir = get_work_docs_dir()

    inbox_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    pending = [f for f in inbox_dir.iterdir() if f.suffix.lower() in {".md", ".txt"}]
    archived = [f for f in archive_dir.iterdir() if f.suffix.lower() in {".md", ".txt"}]

    typer.echo(f"inbox 目录: {inbox_dir}")
    typer.echo(f"待处理: {len(pending)} 个文件")
    typer.echo(f"已归档: {len(archived)} 个文件")
