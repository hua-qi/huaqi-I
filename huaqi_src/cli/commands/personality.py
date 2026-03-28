"""personality 子命令"""

import typer
from rich import box
from rich.table import Table

from huaqi_src.cli.context import console, ensure_initialized

personality_app = typer.Typer(name="personality", help="人格画像管理")


@personality_app.callback(invoke_without_command=True)
def personality_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@personality_app.command("update")
def personality_update(
    days: int = typer.Option(7, "--days", "-d", help="分析最近几天的日记"),
):
    """分析日记并生成画像更新提案"""
    ensure_initialized()

    from huaqi_src.core.personality_updater import PersonalityUpdater

    updater = PersonalityUpdater()
    proposal = updater.analyze_recent(days=days)

    if proposal is None:
        console.print("\n[dim]未检测到显著的画像变化[/dim]\n")
        return

    console.print("\n[bold cyan]📊 人格画像更新提案[/bold cyan]\n")
    console.print(updater.get_update_summary(proposal))
    console.print(f"\n使用以下命令查看详情：")
    console.print(f"  huaqi personality review {proposal.id}")
    console.print()


@personality_app.command("review")
def personality_review(
    proposal_id: str = typer.Argument(None, help="提案ID，不提供则列出待审核提案"),
    approve: bool = typer.Option(False, "--approve", "-a", help="批准提案"),
    reject: bool = typer.Option(False, "--reject", "-r", help="拒绝提案"),
    notes: str = typer.Option(None, "--notes", "-n", help="备注"),
):
    """查看或审核画像更新提案"""
    ensure_initialized()

    from huaqi_src.core.personality_updater import PersonalityUpdater

    updater = PersonalityUpdater()

    if proposal_id is None:
        proposals = updater.list_pending_proposals()
        if not proposals:
            console.print("\n[dim]暂无待审核的画像更新提案[/dim]\n")
            return

        console.print("\n[bold cyan]📋 待审核提案列表[/bold cyan]\n")
        for p in proposals:
            console.print(f"[cyan]{p.id}[/cyan]")
            console.print(f"  创建时间: {p.created_at.strftime('%Y-%m-%d %H:%M')}")
            console.print(f"  变化项: {len(p.changes)} 项")
            console.print(f"  查看: huaqi personality review {p.id}\n")
        return

    proposal = updater.get_proposal(proposal_id)
    if proposal is None:
        console.print(f"\n[red]未找到提案: {proposal_id}[/red]\n")
        return

    if approve:
        if updater.approve_proposal(proposal_id, notes):
            console.print("\n[green]✅ 已批准并应用画像更新[/green]\n")
        else:
            console.print("\n[red]❌ 操作失败[/red]\n")
        return

    if reject:
        if updater.reject_proposal(proposal_id, notes):
            console.print("\n[red]❌ 已拒绝画像更新提案[/red]\n")
        else:
            console.print("\n[red]❌ 操作失败[/red]\n")
        return

    console.print("\n[bold cyan]📊 提案详情[/bold cyan]\n")
    console.print(updater.get_update_summary(proposal))

    if proposal.status == "pending":
        console.print("\n[dim]操作选项:[/dim]")
        console.print(f"  --approve (-a)  批准并应用更新")
        console.print(f"  --reject (-r)   拒绝更新")
        console.print(f"  --notes (-n)    添加备注")
    console.print()


@personality_app.command("show")
def personality_show():
    """显示当前人格画像"""
    import huaqi_src.cli.context as ctx
    ensure_initialized()

    from huaqi_src.core.personality_simple import PersonalityEngine

    engine = PersonalityEngine(ctx.DATA_DIR / "memory")
    profile = engine.profile

    console.print("\n[bold cyan]👤 当前人格画像[/bold cyan]\n")

    table = Table(show_header=False, box=box.ROUNDED)
    table.add_column(style="cyan", width=15)
    table.add_column()

    table.add_row("名称", profile.name)
    table.add_row("角色", profile.role)
    table.add_row("版本", profile.version)
    table.add_row("", "")
    table.add_row("开放度", f"{profile.openness:.2f}")
    table.add_row("责任心", f"{profile.conscientiousness:.2f}")
    table.add_row("外向性", f"{profile.extraversion:.2f}")
    table.add_row("宜人性", f"{profile.agreeableness:.2f}")
    table.add_row("情绪稳定性", f"{profile.neuroticism:.2f}")
    table.add_row("", "")
    table.add_row("沟通风格", profile.tone)
    table.add_row("正式程度", f"{profile.formality:.2f}")
    table.add_row("共情水平", f"{profile.empathy:.2f}")

    console.print(table)
    console.print()
