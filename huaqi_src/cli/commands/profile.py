"""profile 子命令"""

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table

from huaqi_src.cli.context import console, ensure_initialized

profile_app = typer.Typer(name="profile", help="用户画像管理")


@profile_app.callback(invoke_without_command=True)
def profile_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@profile_app.command("show")
def profile_show():
    """显示用户画像（优先展示 LLM 叙事描述）"""
    ensure_initialized()

    from huaqi_src.core.user_profile import get_profile_manager, get_narrative_manager

    console.print("\n[bold magenta]👤 用户画像[/bold magenta]\n")

    narrative_manager = get_narrative_manager()
    cached = narrative_manager.get_cached()

    if cached is not None:
        if cached.is_today():
            console.print(Panel(
                cached.content,
                title="[bold cyan]AI 洞察[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            ))
            sources_str = "、".join(cached.data_sources) if cached.data_sources else "无"
            console.print(f"[dim]数据来源: {sources_str}  |  生成时间: {cached.generated_at[:10]}[/dim]\n")
        else:
            console.print("[dim]（画像描述生成于昨天或更早）[/dim]\n")
            console.print(Panel(
                cached.content,
                title="[bold cyan]AI 洞察（旧）[/bold cyan]",
                border_style="dim",
                padding=(1, 2),
            ))
    else:
        console.print("[dim]尚未生成 AI 画像描述。[/dim]\n")

    profile_manager = get_profile_manager()
    profile = profile_manager.profile

    identity = profile.identity
    background = profile.background

    has_identity = any([identity.name, identity.nickname, identity.occupation,
                        identity.company, identity.location, identity.birth_date])
    has_background = any([background.education, background.skills, background.hobbies, background.life_goals])

    if has_identity or has_background:
        console.print("[bold]── 结构化字段 ──[/bold]")
        if has_identity:
            identity_table = Table(box=box.SIMPLE, show_header=False)
            identity_table.add_column("项目", style="dim", width=8)
            identity_table.add_column("值")
            if identity.name:
                identity_table.add_row("名字", identity.name)
            if identity.nickname:
                identity_table.add_row("昵称", identity.nickname)
            if identity.occupation:
                identity_table.add_row("职业", identity.occupation)
            if identity.company:
                identity_table.add_row("公司", identity.company)
            if identity.location:
                identity_table.add_row("所在地", identity.location)
            if identity.birth_date:
                identity_table.add_row("生日", identity.birth_date)
            console.print(identity_table)

        if has_background:
            bg_table = Table(box=box.SIMPLE, show_header=False)
            bg_table.add_column("项目", style="dim", width=8)
            bg_table.add_column("内容")
            if background.education:
                bg_table.add_row("教育", background.education)
            if background.skills:
                bg_table.add_row("技能", ", ".join(background.skills))
            if background.hobbies:
                bg_table.add_row("爱好", ", ".join(background.hobbies))
            if background.life_goals:
                bg_table.add_row("目标", ", ".join(background.life_goals))
            console.print(bg_table)

    console.print(f"\n[dim]结构化版本: {profile.version}  |  更新: {profile.updated_at[:10]}[/dim]\n")



@profile_app.command("set")
def profile_set(
    field: str = typer.Argument(..., help="字段名 (name/nickname/occupation/location/...)"),
    value: str = typer.Argument(..., help="字段值"),
):
    """设置用户画像字段"""
    ensure_initialized()

    from huaqi_src.core.user_profile import get_profile_manager

    profile_manager = get_profile_manager()

    identity_fields = ["name", "nickname", "birth_date", "location", "occupation", "company"]
    if field in identity_fields:
        profile_manager.update_identity(**{field: value})
        console.print(f"[green]✅ 已更新 {field} = {value}[/green]")
        return

    background_list_fields = ["skills", "hobbies", "life_goals", "values"]
    if field in background_list_fields:
        items = [v.strip() for v in value.split(",")]
        current = getattr(profile_manager.profile.background, field, [])
        for item in items:
            if item not in current:
                current.append(item)
        setattr(profile_manager.profile.background, field, current)
        profile_manager.save()
        console.print(f"[green]✅ 已添加 {field}: {', '.join(items)}[/green]")
        return

    console.print(f"[yellow]❌ 未知字段: {field}[/yellow]")
    console.print(f"[dim]可用字段: {', '.join(identity_fields + background_list_fields)}[/dim]")

