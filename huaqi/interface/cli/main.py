"""Huaqi CLI - 命令行入口

个人 AI 同伴系统的命令行交互界面
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from huaqi import __version__, __description__

app = typer.Typer(
    name="huaqi",
    help=__description__,
    no_args_is_help=True,
)
console = Console()


def get_banner() -> Text:
    """返回应用横幅"""
    banner = Text()
    banner.append("╔═══════════════════════════════════════╗\n", style="cyan")
    banner.append("║     ", style="cyan")
    banner.append("🌸 Huaqi ", style="bold magenta")
    banner.append("- 你的 AI 同伴", style="white")
    banner.append("     ║\n", style="cyan")
    banner.append("║   ", style="cyan")
    banner.append("不是使用 AI，而是养育 AI", style="dim")
    banner.append("   ║\n", style="cyan")
    banner.append("╚═══════════════════════════════════════╝", style="cyan")
    return banner


@app.callback()
def callback():
    """Huaqi - 个人 AI 同伴系统"""
    pass


@app.command()
def version():
    """显示版本信息"""
    console.print(get_banner())
    console.print(f"\n版本: {__version__}")


@app.command()
def status():
    """查看系统状态"""
    console.print(get_banner())
    
    # TODO: 实现状态检查
    status_info = {
        "配置状态": "未初始化",
        "记忆库": "未创建",
        "同步状态": "未配置",
        "LLM 连接": "未配置",
    }
    
    for key, value in status_info.items():
        console.print(f"  {key}: {value}")


@app.command()
def chat(
    quick: bool = typer.Option(False, "--quick", "-q", help="快速问答模式"),
):
    """开始与 AI 同伴对话"""
    console.print(get_banner())
    console.print("\n[dim]对话功能开发中...[/dim]\n")
    
    # TODO: 实现对对话功能
    console.print("请先运行: huaqi config init")


# 子命令组
app.add_typer(config_app := typer.Typer(name="config", help="配置管理"), name="config")
app.add_typer(memory_app := typer.Typer(name="memory", help="记忆管理"), name="memory")
app.add_typer(skill_app := typer.Typer(name="skill", help="技能管理"), name="skill")


@config_app.command("init")
def config_init():
    """初始化配置"""
    console.print(get_banner())
    console.print("\n[bold green]初始化配置...[/bold green]\n")
    
    # TODO: 实现配置初始化
    console.print("[yellow]提示: 这个功能正在开发中[/yellow]")


@config_app.command("sync")
def config_sync():
    """同步配置到云端"""
    console.print("同步功能开发中...")


@memory_app.command("search")
def memory_search(query: str):
    """搜索记忆
    
    Args:
        query: 搜索关键词或问题
    """
    console.print(f"搜索记忆: {query}")
    console.print("[dim]功能开发中...[/dim]")


@memory_app.command("status")
def memory_status():
    """查看记忆库状态"""
    console.print("记忆库状态:")
    console.print("  长期记忆: 0 条")
    console.print("  工作记忆: 0 条")
    console.print("  会话记忆: 0 条")


@skill_app.command("list")
def skill_list():
    """列出可用技能"""
    console.print("可用技能:")
    console.print("  [dim]暂无已配置的技能[/dim]")


# 导入命令
@app.command()
def import_files(
    source: Path = typer.Argument(..., help="要导入的文件或目录路径"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="预览模式，不实际导入"),
    wizard: bool = typer.Option(False, "--wizard", "-w", help="使用交互式向导"),
):
    """导入外部文档作为记忆"""
    console.print(get_banner())
    console.print()
    
    if not source.exists():
        console.print(f"[red]路径不存在: {source}[/red]")
        raise typer.Exit(1)
    
    # TODO: 初始化导入器
    from huaqi.memory.importer.batch import ImportWizard, BatchImporter
    
    importer = BatchImporter(
        memory_storage=None,  # TODO: 传入实际存储
        llm_client=None,      # TODO: 传入 LLM 客户端
        dry_run=dry_run
    )
    
    if wizard or source.is_dir():
        # 使用向导模式
        wizard = ImportWizard(importer)
        wizard.run()
    else:
        # 直接导入单个文件
        result = importer.import_single(source)
        
        if result.success:
            console.print(f"[green]✓ 导入成功:[/green] {result.title}")
            console.print(f"  类型: {result.memory_type}")
            console.print(f"  标签: {', '.join(result.tags)}")
            if result.extracted_insights:
                console.print(f"  提取到 {len(result.extracted_insights)} 条洞察")
        else:
            console.print(f"[red]✗ 导入失败:[/red] {result.error_message}")


if __name__ == "__main__":
    app()
