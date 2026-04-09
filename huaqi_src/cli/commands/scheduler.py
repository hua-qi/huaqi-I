from typing import Optional
import typer
from rich.table import Table
from rich.console import Console

scheduler_app = typer.Typer(help="定时任务管理")
console = Console()

_CLEAR_SENTINEL = "__clear__"


def _get_store():
    from huaqi_src.config.paths import require_data_dir
    from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore
    return ScheduledJobStore(require_data_dir())


def _sync_to_scheduler(store):
    try:
        from huaqi_src.scheduler.manager import get_scheduler_manager
        from huaqi_src.scheduler.jobs import register_jobs
        scheduler = get_scheduler_manager()
        if scheduler.is_running():
            register_jobs(scheduler, store)
    except Exception as e:
        console.print(f"[dim yellow]⚠ 同步到调度器失败（将在下次 daemon 重启时生效）: {e}[/dim yellow]")


@scheduler_app.command("list")
def list_cmd():
    store = _get_store()
    jobs = store.load_jobs()

    table = Table(title="定时任务配置")
    table.add_column("Job ID")
    table.add_column("显示名")
    table.add_column("启用")
    table.add_column("Cron")
    table.add_column("输出目录")

    for job in jobs:
        table.add_row(
            job.id,
            job.display_name,
            "✓" if job.enabled else "✗",
            job.cron,
            job.output_dir or "-",
        )

    console.print(table)


@scheduler_app.command("add")
def add_cmd(
    job_id: str = typer.Option(..., "--id", prompt="任务 ID"),
    display_name: str = typer.Option(..., "--name", prompt="显示名"),
    cron: str = typer.Option(..., "--cron", prompt="Cron 表达式（如 0 9 * * 1）"),
    prompt: str = typer.Option(..., "--prompt", prompt="触发时传给 Agent 的 prompt"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", prompt="输出目录（回车跳过）"),
):
    from huaqi_src.scheduler.scheduled_job_store import ScheduledJob
    store = _get_store()
    cleaned_output_dir = (output_dir or "").strip() or None
    job = ScheduledJob(
        id=job_id,
        display_name=display_name,
        cron=cron,
        enabled=True,
        prompt=prompt,
        output_dir=cleaned_output_dir,
    )
    try:
        store.add_job(job)
        typer.echo(f"已创建任务: {job_id}")
        _sync_to_scheduler(store)
    except ValueError as e:
        typer.echo(str(e))
        raise typer.Exit(1)


@scheduler_app.command("remove")
def remove_cmd(job_id: str):
    store = _get_store()
    try:
        store.remove_job(job_id)
        typer.echo(f"已删除任务: {job_id}")
        _sync_to_scheduler(store)
    except ValueError as e:
        typer.echo(str(e))
        raise typer.Exit(1)


@scheduler_app.command("edit")
def edit_cmd(
    job_id: str,
    display_name: Optional[str] = typer.Option(None, "--name"),
    cron: Optional[str] = typer.Option(None, "--cron"),
    prompt: Optional[str] = typer.Option(None, "--prompt"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir"),
    clear_output_dir: bool = typer.Option(False, "--clear-output-dir", help="清空输出目录"),
):
    store = _get_store()
    job = store.get_job(job_id)
    if job is None:
        typer.echo(f"任务不存在: {job_id}")
        raise typer.Exit(1)

    updates = {}
    if display_name is not None:
        updates["display_name"] = display_name
    if cron is not None:
        updates["cron"] = cron
    if prompt is not None:
        updates["prompt"] = prompt
    if clear_output_dir:
        updates["output_dir"] = None
    elif output_dir is not None:
        updates["output_dir"] = (output_dir or "").strip() or None

    updated_job = job.model_copy(update=updates)
    store.update_job(updated_job)
    typer.echo(f"已更新任务: {job_id}")
    _sync_to_scheduler(store)


@scheduler_app.command("enable")
def enable_cmd(job_id: str):
    store = _get_store()
    job = store.get_job(job_id)
    if job is None:
        typer.echo(f"任务不存在: {job_id}")
        raise typer.Exit(1)
    updated_job = job.model_copy(update={"enabled": True})
    store.update_job(updated_job)
    typer.echo(f"已启用: {job_id}")
    _sync_to_scheduler(store)


@scheduler_app.command("disable")
def disable_cmd(job_id: str):
    store = _get_store()
    job = store.get_job(job_id)
    if job is None:
        typer.echo(f"任务不存在: {job_id}")
        raise typer.Exit(1)
    updated_job = job.model_copy(update={"enabled": False})
    store.update_job(updated_job)
    typer.echo(f"已禁用: {job_id}")
    _sync_to_scheduler(store)


@scheduler_app.command("run")
def run_cmd(job_id: str):
    store = _get_store()
    job = store.get_job(job_id)
    if job is None:
        typer.echo(f"任务不存在: {job_id}")
        raise typer.Exit(1)
    from huaqi_src.scheduler.job_runner import _run_scheduled_job
    typer.echo(f"正在执行任务: {job.display_name}")
    _run_scheduled_job(job.id, job.prompt, job.output_dir)
