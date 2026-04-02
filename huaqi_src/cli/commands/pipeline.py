"""pipeline 子命令"""

import asyncio
from pathlib import Path
from typing import Optional

import typer

from huaqi_src.cli.context import console, ensure_initialized

pipeline_app = typer.Typer(name="pipeline", help="内容流水线 - X/RSS 采集 → 小红书发布")


@pipeline_app.callback(invoke_without_command=True)
def pipeline_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@pipeline_app.command("show")
def pipeline_show():
    """显示流水线状态（草稿数量、待审核任务）"""
    ensure_initialized()

    from huaqi_src.layers.capabilities.pipeline.platforms import XiaoHongShuPublisher
    from huaqi_src.scheduler.pipeline_job import PipelineJobManager

    console.print("\n[bold cyan]🚀 流水线状态[/bold cyan]\n")

    publisher = XiaoHongShuPublisher()
    drafts = publisher.list_drafts()
    console.print(f"  草稿数量: [cyan]{len(drafts)}[/cyan]")

    manager = PipelineJobManager()
    reviews = manager.list_pending_reviews()
    console.print(f"  待审核任务: [cyan]{len(reviews)}[/cyan]")
    console.print()


@pipeline_app.command("run")
def pipeline_run(
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="预览模式，不实际发布"),
    limit: int = typer.Option(5, "--limit", "-n", help="每个源采集数量"),
    source: str = typer.Option("all", "--source", "-s", help="数据源: x/rss/all"),
):
    """执行内容流水线"""
    ensure_initialized()

    from huaqi_src.layers.capabilities.pipeline import create_default_pipeline

    console.print("\n[bold cyan]🚀 启动内容流水线[/bold cyan]\n")

    async def _run():
        pipeline = create_default_pipeline()
        if source != "all":
            from huaqi_src.layers.capabilities.pipeline.sources import XMockSource, RSSMockSource
            pipeline.sources = [
                s for s in pipeline.sources
                if (source == "x" and isinstance(s, XMockSource)) or
                   (source == "rss" and isinstance(s, RSSMockSource))
            ]
        stats = await pipeline.run(limit=limit, dry_run=dry_run)
        return stats

    try:
        stats = asyncio.run(_run())
        console.print("\n[bold green]✅ 流水线执行完成[/bold green]")
        console.print(f"  采集: {stats.get('fetched', 0)} 条")
        console.print(f"  处理: {stats.get('processed', 0)} 条")
        console.print(f"  发布: {stats.get('published', 0)} 条")
        console.print(f"  失败: {stats.get('failed', 0)} 条\n")

        if dry_run:
            console.print("[dim]💡 预览模式，内容未实际发布[/dim]")
            console.print("[dim]   去掉 --dry-run 参数即可发布[/dim]\n")

    except Exception as e:
        console.print(f"\n[red]❌ 流水线执行失败: {e}[/red]\n")


@pipeline_app.command("preview")
def pipeline_preview(
    item_id: str = typer.Argument(..., help="内容 ID 或关键词"),
):
    """预览指定内容的处理结果"""
    console.print("\n[yellow]预览功能开发中...[/yellow]\n")


@pipeline_app.command("drafts")
def pipeline_drafts(
    limit: int = typer.Option(10, "--limit", "-n", help="显示数量"),
):
    """查看已生成的草稿"""
    ensure_initialized()

    from huaqi_src.layers.capabilities.pipeline.platforms import XiaoHongShuPublisher

    publisher = XiaoHongShuPublisher()
    drafts = publisher.list_drafts()

    if not drafts:
        console.print("\n[dim]暂无草稿[/dim]\n")
        return

    console.print(f"\n[bold cyan]📝 草稿列表 ({len(drafts)} 篇)[/bold cyan]\n")
    for i, draft in enumerate(drafts[:limit], 1):
        console.print(f"{i}. [cyan]{draft['created']}[/cyan] - {draft['filename']}")

    if len(drafts) > limit:
        console.print(f"\n[dim]...还有 {len(drafts) - limit} 篇[/dim]")
    console.print()


@pipeline_app.command("review")
def pipeline_review(
    task_id: str = typer.Argument(None, help="任务ID，不提供则列出所有待审核任务"),
    approve: int = typer.Option(None, "--approve", "-a", help="通过指定索引的内容"),
    reject: int = typer.Option(None, "--reject", "-r", help="拒绝指定索引的内容"),
    publish: bool = typer.Option(False, "--publish", "-p", help="发布已审核通过的内容"),
):
    """审核待发布内容"""
    ensure_initialized()

    from huaqi_src.scheduler.pipeline_job import PipelineJobManager

    manager = PipelineJobManager()

    if task_id is None:
        reviews = manager.list_pending_reviews()
        if not reviews:
            console.print("\n[dim]暂无待审核任务[/dim]\n")
            return

        console.print("\n[bold cyan]📋 待审核任务列表[/bold cyan]\n")
        for review in reviews:
            console.print(f"[cyan]{review['task_id']}[/cyan]")
            console.print(f"  创建时间: {review['created_at']}")
            console.print(f"  待审核: {review['pending_count']}/{review['total_count']} 条")
            console.print(f"  命令: huaqi pipeline review {review['task_id']}\n")
        return

    task_data = manager.get_pending_task(task_id)
    if task_data is None:
        console.print(f"\n[red]未找到任务: {task_id}[/red]\n")
        return

    items = task_data.get("items", [])

    if approve is not None:
        if manager.approve_item(task_id, approve):
            console.print(f"\n[green]✅ 已通过项目 {approve}[/green]\n")
        else:
            console.print(f"\n[red]❌ 操作失败[/red]\n")
        return

    if reject is not None:
        if manager.reject_item(task_id, reject):
            console.print(f"\n[red]❌ 已拒绝项目 {reject}[/red]\n")
        else:
            console.print(f"\n[red]❌ 操作失败[/red]\n")
        return

    if publish:
        count = asyncio.run(manager.publish_approved(task_id))
        console.print(f"\n[green]✅ 已发布 {count} 条内容[/green]\n")
        return

    console.print(f"\n[bold cyan]📋 任务详情: {task_id}[/bold cyan]\n")
    for i, item in enumerate(items):
        status = item.get("status", "pending")
        status_icon = "⏳" if status == "pending" else "✅" if status == "approved" else "❌"
        console.print(f"{i}. {status_icon} [{status}]")
        console.print(f"   草稿: {Path(item.get('draft_path', 'N/A')).name}")
        console.print(f"   创建: {item.get('created_at')}")
        if status == "pending":
            console.print(f"   [dim]操作: -a {i} 通过 | -r {i} 拒绝[/dim]")
        console.print()

    console.print("[dim]使用 --publish 发布已审核通过的内容[/dim]\n")
