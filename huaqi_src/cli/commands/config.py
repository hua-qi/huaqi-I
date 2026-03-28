"""config 子命令"""

import os
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.table import Table

from huaqi_src.cli.context import console, ensure_initialized, DATA_DIR

config_app = typer.Typer(name="config", help="系统配置管理")


@config_app.callback(invoke_without_command=True)
def config_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        ctx.get_help()


@config_app.command("show")
def config_show():
    """显示当前配置"""
    import huaqi_src.cli.context as ctx
    ensure_initialized()

    config = ctx._config.load_config()

    console.print("\n[bold blue]⚙️ 系统配置[/bold blue]\n")

    table = Table(show_header=False, box=box.ROUNDED)
    table.add_column(style="cyan", width=20)
    table.add_column()

    table.add_row("数据目录", str(ctx.DATA_DIR))
    table.add_row("LLM 提供商", config.llm_default_provider)

    for name, provider in config.llm_providers.items():
        table.add_row(f"LLM {name}", f"{provider.model} @ {provider.api_base or 'default'}")

    table.add_row("界面主题", config.interface_theme)

    console.print(table)
    console.print()


@config_app.command("set-llm")
def config_set_llm(
    provider: str = typer.Argument(..., help="提供商名称 (openai/claude/deepseek/dummy)"),
    api_key: str = typer.Option(..., "--api-key", "-k", help="API 密钥（必填）"),
    api_base: str = typer.Option(None, "--api-base", "-b", help="API 基础地址"),
    model: str = typer.Option(None, "--model", "-m", help="模型名称"),
):
    """配置 LLM"""
    import huaqi_src.cli.context as ctx
    ensure_initialized()

    from huaqi_src.core.config_simple import LLMProviderConfig

    if model is None:
        default_models = {
            "openai": "gpt-3.5-turbo",
            "deepseek": "deepseek-chat",
            "claude": "claude-3-sonnet-20240229",
            "dummy": "dummy",
        }
        model = default_models.get(provider, "gpt-3.5-turbo")

    llm_config = LLMProviderConfig(
        name=provider,
        model=model,
        api_key=api_key,
        api_base=api_base,
    )

    config = ctx._config.load_config()
    config.llm_providers[provider] = llm_config
    config.llm_default_provider = provider
    ctx._config.save_config()

    console.print(f"\n[green]✅ LLM 已配置: {provider}[/green]")
    console.print(f"   模型: {model}")
    console.print(f"   API Key: {api_key[:8]}...{api_key[-4:]}")
    if api_base:
        console.print(f"   地址: {api_base}")
    console.print()


@config_app.command("set-data-dir")
def config_set_data_dir(
    path: Path = typer.Argument(..., help="数据目录路径（如: ~/huaqi 或 /path/to/dir）"),
    migrate: bool = typer.Option(True, "--migrate/--no-migrate", help="是否迁移现有数据"),
):
    """配置数据存储地址（支持数据迁移）"""
    import shutil
    import huaqi_src.cli.context as ctx
    ensure_initialized()

    path_str = str(path)
    home_str = str(Path.home())

    if path_str.startswith("~"):
        path_str = path_str.replace("~", home_str, 1)

    if home_str in path_str and path_str.count(home_str.split("/")[-1]) > 1:
        parts = path_str.split(home_str + "/")
        if len(parts) > 1 and parts[1].startswith("Users/"):
            second_home = path_str.find(home_str, len(home_str))
            if second_home > 0:
                path_str = path_str[second_home:]

    path = Path(path_str).resolve()
    path.mkdir(parents=True, exist_ok=True)

    old_data_dir = ctx.DATA_DIR

    if migrate and old_data_dir.exists() and old_data_dir != path:
        console.print(f"\n[yellow]🔄 正在迁移数据...[/yellow]")
        console.print(f"   从: {old_data_dir}")
        console.print(f"   到: {path}")

        dirs_to_migrate = ["memory", "drafts", "pending_reviews", "vector_db"]
        migrated_count = 0
        for dir_name in dirs_to_migrate:
            old_dir = old_data_dir / dir_name
            new_dir = path / dir_name
            if old_dir.exists():
                if new_dir.exists():
                    console.print(f"   ⚠️  {dir_name} 已存在，跳过")
                else:
                    shutil.copytree(old_dir, new_dir)
                    migrated_count += 1
                    console.print(f"   ✅  {dir_name}")

        old_config = old_data_dir / "memory" / "config.yaml"
        new_config = path / "memory" / "config.yaml"
        if old_config.exists() and not new_config.exists():
            new_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_config, new_config)
            console.print(f"   ✅  config.yaml")

        console.print(f"\n[green]✅ 数据迁移完成 ({migrated_count} 个目录)[/green]")

    from huaqi_src.core.config_simple import ConfigManager
    _new_config = ConfigManager(path)
    _new_config.set("data_dir", str(path))

    ctx.DATA_DIR = path
    ctx.MEMORY_DIR = path / "memory"
    ctx._config = _new_config

    from huaqi_src.core.config_paths import set_data_dir
    set_data_dir(path)

    console.print(f"\n[green]✅ 数据目录已设置为: {path}[/green]")
    console.print(f"\n[dim]提示: 旧数据仍保留在 {old_data_dir}[/dim]\n")


@config_app.command("get")
def config_get(key: str = typer.Argument(..., help="配置项名称")):
    """获取配置项"""
    import huaqi_src.cli.context as ctx
    ensure_initialized()
    value = ctx._config.get(key)
    console.print(f"{key}: {value}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="配置项名称"),
    value: str = typer.Argument(..., help="配置项值"),
):
    """设置配置项"""
    import huaqi_src.cli.context as ctx
    ensure_initialized()
    ctx._config.set(key, value)
    console.print(f"[green]✅ 已设置 {key} = {value}[/green]")
