"""定时任务 CLI 命令（headless 执行，供 GitHub Actions 调用）"""
import typer

scheduler_app = typer.Typer(help="定时任务管理（headless）")
console = __import__("rich.console", fromlist=["Console"]).Console()


@scheduler_app.command("run")
def run_cmd(job_id: str):
    """Headless 执行指定定时任务（供 GitHub Actions 调用）"""
    from huaqi_src.config.paths import require_data_dir
    from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore

    store = ScheduledJobStore(require_data_dir())
    job = store.get_job(job_id)
    if job is None:
        typer.echo(f"任务不存在: {job_id}")
        raise typer.Exit(1)

    from huaqi_src.scheduler.job_runner import _run_scheduled_job

    typer.echo(f"正在执行任务: {job.display_name}")
    _run_scheduled_job(job.id, job.prompt, job.output_dir)
