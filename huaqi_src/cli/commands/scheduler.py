from typing import Optional
import typer
from rich.table import Table
from rich.console import Console

scheduler_app = typer.Typer(help="定时任务管理")
console = Console()


def _get_config_manager():
    from huaqi_src.config.manager import get_config_manager
    return get_config_manager()


@scheduler_app.command("list")
def list_cmd():
    from huaqi_src.scheduler.jobs import _DEFAULT_JOB_CONFIGS
    cm = _get_config_manager()
    config = cm.load_config()

    table = Table(title="定时任务配置")
    table.add_column("Job ID")
    table.add_column("显示名")
    table.add_column("启用")
    table.add_column("Cron")

    for job_id, defaults in _DEFAULT_JOB_CONFIGS.items():
        job_cfg = config.scheduler_jobs.get(job_id)
        enabled = job_cfg.enabled if job_cfg else True
        cron = (job_cfg.cron if job_cfg and job_cfg.cron else defaults["cron"])
        table.add_row(job_id, defaults["display_name"], "✓" if enabled else "✗", cron)

    console.print(table)


@scheduler_app.command("enable")
def enable_cmd(job_id: str):
    from huaqi_src.config.manager import SchedulerJobConfig
    from huaqi_src.scheduler.jobs import KNOWN_JOB_IDS
    if job_id not in KNOWN_JOB_IDS:
        typer.echo(f"未知任务: {job_id}")
        raise typer.Exit(1)
    cm = _get_config_manager()
    config = cm.load_config()
    existing = config.scheduler_jobs.get(job_id) or SchedulerJobConfig()
    config.scheduler_jobs[job_id] = SchedulerJobConfig(enabled=True, cron=existing.cron)
    cm.save_config()
    typer.echo(f"已启用: {job_id}")


@scheduler_app.command("disable")
def disable_cmd(job_id: str):
    from huaqi_src.config.manager import SchedulerJobConfig
    from huaqi_src.scheduler.jobs import KNOWN_JOB_IDS
    if job_id not in KNOWN_JOB_IDS:
        typer.echo(f"未知任务: {job_id}")
        raise typer.Exit(1)
    cm = _get_config_manager()
    config = cm.load_config()
    existing = config.scheduler_jobs.get(job_id) or SchedulerJobConfig()
    config.scheduler_jobs[job_id] = SchedulerJobConfig(enabled=False, cron=existing.cron)
    cm.save_config()
    typer.echo(f"已禁用: {job_id}")


@scheduler_app.command("set-cron")
def set_cron_cmd(job_id: str, cron: str):
    from huaqi_src.config.manager import SchedulerJobConfig
    from huaqi_src.scheduler.jobs import KNOWN_JOB_IDS
    if job_id not in KNOWN_JOB_IDS:
        typer.echo(f"未知任务: {job_id}")
        raise typer.Exit(1)
    cm = _get_config_manager()
    config = cm.load_config()
    existing = config.scheduler_jobs.get(job_id) or SchedulerJobConfig()
    config.scheduler_jobs[job_id] = SchedulerJobConfig(enabled=existing.enabled, cron=cron)
    cm.save_config()
    typer.echo(f"已更新 {job_id} cron: {cron}")
