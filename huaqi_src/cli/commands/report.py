import typer
from huaqi_src.cli.context import console, ensure_initialized
from huaqi_src.layers.capabilities.reports.manager import ReportManager

report_app = typer.Typer(help="报告查看与生成")

@report_app.command("morning")
def morning_cmd(
    date: str = typer.Argument("today", help="日期 (today, yesterday, YYYY-MM-DD)"),
    force: bool = typer.Option(False, "--force", "-f", help="强制重新生成")
):
    """查看或生成晨间简报"""
    ensure_initialized()
    manager = ReportManager()
    console.print("[dim]正在获取晨间简报...[/dim]")
    content = manager.get_or_generate_report("morning", date, force)
    console.print(f"\n{content}\n")

@report_app.command("daily")
def daily_cmd(
    date: str = typer.Argument("today", help="日期 (today, yesterday, YYYY-MM-DD)"),
    force: bool = typer.Option(False, "--force", "-f", help="强制重新生成")
):
    """查看或生成日终复盘"""
    ensure_initialized()
    manager = ReportManager()
    console.print("[dim]正在获取日终复盘...[/dim]")
    content = manager.get_or_generate_report("daily", date, force)
    console.print(f"\n{content}\n")
    
@report_app.command("weekly")
def weekly_cmd(
    date: str = typer.Argument("today", help="日期 (today, yesterday, YYYY-MM-DD)"),
    force: bool = typer.Option(False, "--force", "-f", help="强制重新生成")
):
    """查看或生成周报"""
    ensure_initialized()
    manager = ReportManager()
    console.print("[dim]正在获取周报...[/dim]")
    content = manager.get_or_generate_report("weekly", date, force)
    console.print(f"\n{content}\n")
