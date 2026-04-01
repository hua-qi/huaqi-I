"""config 子命令"""

import os
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.table import Table

from huaqi_src.cli.context import console, ensure_initialized, DATA_DIR

config_app = typer.Typer(name="config", help="系统配置管理")

KEY_DESCRIPTIONS = {
    "data_dir": "数据目录",
    "llm_default_provider": "默认 LLM 提供商",
    "llm_providers.*.model": "模型名称",
    "llm_providers.*.api_key": "API 密钥",
    "llm_providers.*.api_base": "API 地址",
    "llm_providers.*.temperature": "温度参数",
    "llm_providers.*.max_tokens": "最大 Token 数",
    "memory.max_session_memory": "最大会话记忆条数",
    "memory.search_algorithm": "搜索算法",
    "memory.search_top_k": "搜索返回数量",
    "modules.network_proxy": "网络请求采集模块",
    "interface_theme": "界面主题",
    "interface_language": "界面语言",
    "git.remote_url": "Git 远程地址",
    "git.branch": "Git 分支",
    "git.remote": "Git 远程名称",
    "git.auto_push": "自动推送",
}

SENSITIVE_KEYS = {"api_key"}


def _get_description(key: str) -> str:
    if key in KEY_DESCRIPTIONS:
        return KEY_DESCRIPTIONS[key]
    parts = key.split(".")
    if len(parts) >= 3:
        wildcard_key = f"{parts[0]}.*.{'.'.join(parts[2:])}"
        if wildcard_key in KEY_DESCRIPTIONS:
            return KEY_DESCRIPTIONS[wildcard_key]
    return ""


def _mask_value(key: str, value: str) -> str:
    last_part = key.split(".")[-1]
    if last_part in SENSITIVE_KEYS and value and len(value) > 8:
        return f"{value[:6]}...{value[-4:]}"
    return value


def _flatten_config(config, prefix="") -> list[tuple[str, str, str]]:
    rows = []
    import huaqi_src.cli.context as ctx

    git_status = {}
    if ctx._git is not None:
        git_status = ctx._git.get_status()

    simple_keys = [
        "data_dir",
        "llm_default_provider",
        "interface_theme",
        "interface_language",
    ]
    for k in simple_keys:
        val = getattr(config, k, None)
        display = str(val) if val is not None else "(未设置)"
        rows.append((k, _get_description(k), display))

    for name, provider in config.llm_providers.items():
        for field in ["model", "api_key", "api_base", "temperature", "max_tokens"]:
            key = f"llm_providers.{name}.{field}"
            val = getattr(provider, field, None)
            display = str(val) if val is not None else "(未设置)"
            display = _mask_value(key, display)
            rows.append((key, _get_description(key), display))

    memory = config.memory
    for field in ["max_session_memory", "search_algorithm", "search_top_k"]:
        key = f"memory.{field}"
        val = getattr(memory, field, None)
        display = str(val) if val is not None else "(未设置)"
        rows.append((key, _get_description(key), display))

    modules = config.modules
    for field in ["network_proxy"]:
        key = f"modules.{field}"
        val = modules.get(field, False)
        display = "开启" if val else "关闭"
        rows.append((key, _get_description(key), display))

    if git_status.get("initialized"):
        git_fields = {
            "git.remote_url": git_status.get("remote_url") or "(未设置)",
            "git.branch": git_status.get("branch") or "(未设置)",
            "git.remote": git_status.get("remote") or "(未设置)",
            "git.auto_push": "true" if git_status.get("auto_push") else "false",
        }
        for key, display in git_fields.items():
            rows.append((key, _get_description(key), display))

    return rows


@config_app.callback(invoke_without_command=True)
def config_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        ctx.get_help()


@config_app.command("show")
def config_show():
    """显示所有配置项"""
    import huaqi_src.cli.context as ctx
    ensure_initialized()

    config = ctx._config.load_config()

    console.print("\n[bold blue]⚙️ 系统配置[/bold blue]\n")

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("KEY", style="cyan", no_wrap=True)
    table.add_column("说明", style="dim")
    table.add_column("值")

    for key, desc, val in _flatten_config(config):
        table.add_row(key, desc, val)

    console.print(table)
    console.print("\n[dim]提示: 使用 huaqi config set <KEY> 修改配置[/dim]\n")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="配置项 KEY（可通过 huaqi config show 查看）"),
    value: Optional[str] = typer.Argument(None, help="要设置的新值"),
):
    """设置配置项"""
    import huaqi_src.cli.context as ctx
    ensure_initialized()

    if key == "llm_providers" or key == "llm":
        _wizard_set_llm(ctx)
    elif key == "git" or key == "git.remote_url":
        _wizard_set_git(ctx)
    elif key == "data_dir":
        _wizard_set_data_dir(ctx)
    else:
        current = ctx._config.get(key)
        current_display = str(current) if current is not None else "(未设置)"
        console.print(f"当前值: [dim]{current_display}[/dim]")
        
        if value is None:
            new_value = typer.prompt("新值")
        else:
            new_value = value
            
        # 将输入值转换为布尔类型（对于 modules.*）
        if key.startswith("modules."):
            new_value = str(new_value).lower() in ("true", "1", "yes", "开启", "y", "t")
            
        ctx._config.set(key, new_value)
        console.print(f"[green]✅ 已设置 {key} = {new_value}[/green]")


def _wizard_set_llm(ctx):
    from huaqi_src.core.config_simple import LLMProviderConfig

    console.print("\n[bold]LLM 配置向导[/bold]")

    provider_choices = ["openai", "deepseek", "claude", "dummy", "自定义"]
    for i, p in enumerate(provider_choices, 1):
        console.print(f"  {i}. {p}")
    choice = typer.prompt("选择提供商", default="deepseek")
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(provider_choices) - 1:
            provider = provider_choices[idx]
        else:
            provider = typer.prompt("提供商名称")
    else:
        provider = choice

    default_models = {
        "openai": "gpt-3.5-turbo",
        "deepseek": "deepseek-chat",
        "claude": "claude-3-sonnet-20240229",
        "dummy": "dummy",
    }
    default_model = default_models.get(provider, "")
    model = typer.prompt("模型名称", default=default_model)
    api_key = typer.prompt("API Key", hide_input=True)
    api_base = typer.prompt("API Base（可选，留空跳过）", default="")

    llm_config = LLMProviderConfig(
        name=provider,
        model=model,
        api_key=api_key,
        api_base=api_base or None,
    )
    config = ctx._config.load_config()
    config.llm_providers[provider] = llm_config
    config.llm_default_provider = provider
    ctx._config.save_config()

    console.print(f"\n[green]✅ LLM 已配置: {provider}[/green]")
    console.print(f"   模型: {model}")
    console.print(f"   API Key: {api_key[:6]}...{api_key[-4:]}")
    if api_base:
        console.print(f"   地址: {api_base}")
    console.print()


def _wizard_set_git(ctx):
    if ctx._git is None:
        console.print("[red]❌ Git 模块未初始化[/red]")
        raise typer.Exit(1)

    if not ctx._git._repo_initialized:
        console.print("[yellow]🔧 初始化 Git 仓库...[/yellow]")
        if not ctx._git.init_repo():
            console.print("[red]❌ Git 仓库初始化失败[/red]")
            raise typer.Exit(1)

    console.print("\n[bold]Git 配置向导[/bold]")
    url = typer.prompt("远程仓库地址")
    branch = typer.prompt("分支名称", default="main")
    remote = typer.prompt("远程名称", default="origin")
    auto_push = typer.confirm("开启自动推送？", default=True)

    ok = ctx._git.set_remote(url=url, name=remote, branch=branch, auto_push=auto_push)
    if ok:
        console.print(f"\n[green]✅ Git 远程仓库已配置[/green]")
        console.print(f"   远程: {remote}")
        console.print(f"   地址: {url}")
        console.print(f"   分支: {branch}")
        console.print(f"   自动推送: {'开启' if auto_push else '关闭'}\n")
    else:
        console.print("[red]❌ 配置失败，请检查 URL 是否正确[/red]")
        raise typer.Exit(1)


def _wizard_set_data_dir(ctx):
    import shutil

    console.print("\n[bold]数据目录配置[/bold]")
    path_input = typer.prompt("新数据目录路径")
    path_str = path_input.replace("~", str(Path.home()), 1)
    path = Path(path_str).resolve()
    path.mkdir(parents=True, exist_ok=True)

    old_data_dir = ctx.DATA_DIR
    migrate = False
    if old_data_dir.exists() and old_data_dir != path:
        migrate = typer.confirm(f"是否将数据从 {old_data_dir} 迁移到新目录？", default=True)

    if migrate:
        console.print(f"\n[yellow]🔄 正在迁移数据...[/yellow]")
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
        console.print(f"\n[green]✅ 数据迁移完成 ({migrated_count} 个目录)[/green]")

    from huaqi_src.core.config_simple import ConfigManager
    _new_config = ConfigManager(path)
    _new_config.set("data_dir", str(path))

    ctx.DATA_DIR = path
    ctx.MEMORY_DIR = path / "memory"
    ctx._config = _new_config

    from huaqi_src.core.config_paths import set_data_dir
    set_data_dir(path)

    console.print(f"\n[green]✅ 数据目录已设置为: {path}[/green]\n")
