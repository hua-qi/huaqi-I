"""Huaqi CLI - 命令行入口

个人 AI 同伴系统的命令行交互界面
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from huaqi import __version__, __description__
from huaqi.core.config import init_config_manager, ConfigManager
from huaqi.core.auth import UserManager, UserProfile
from huaqi.memory.storage.user_isolated import UserMemoryManager

# 全局状态
_config_manager: Optional[ConfigManager] = None
_user_manager: Optional[UserManager] = None
_current_user: Optional[str] = None

app = typer.Typer(
    name="huaqi",
    help=__description__,
    no_args_is_help=True,
)
console = Console()

DATA_DIR = Path.home() / ".huaqi"


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


def ensure_initialized():
    """确保系统已初始化"""
    global _config_manager, _user_manager
    
    if _config_manager is None:
        _config_manager = init_config_manager(DATA_DIR)
    
    if _user_manager is None:
        _user_manager = UserManager(DATA_DIR)


def require_login():
    """要求用户已登录"""
    global _current_user
    
    if _current_user is None:
        # 尝试从会话恢复
        # TODO: 实现会话持久化
        console.print("[red]请先登录: huaqi login[/red]")
        raise typer.Exit(1)
    
    return _current_user


@app.callback()
def callback(
    user: Optional[str] = typer.Option(None, "--user", "-u", help="指定用户ID"),
):
    """Huaqi - 个人 AI 同伴系统"""
    global _current_user
    
    ensure_initialized()
    
    if user:
        _current_user = user
        _config_manager.switch_user(user)


@app.command()
def version():
    """显示版本信息"""
    console.print(get_banner())
    console.print(f"\n版本: {__version__}")
    
    # 显示当前用户
    if _current_user:
        console.print(f"当前用户: {_current_user}")
    else:
        console.print("未登录")


@app.command()
def status():
    """查看系统状态"""
    ensure_initialized()
    console.print(get_banner())
    
    # 系统状态
    status_info = {
        "数据目录": str(DATA_DIR),
        "配置状态": "已初始化" if _config_manager else "未初始化",
        "当前用户": _current_user or "未登录",
    }
    
    console.print("\n[bold]系统状态:[/bold]")
    for key, value in status_info.items():
        console.print(f"  {key}: {value}")
    
    # 如果已登录，显示用户状态
    if _current_user:
        memory_manager = UserMemoryManager(_config_manager, _current_user)
        stats = memory_manager.get_user_stats()
        
        console.print("\n[bold]用户存储:[/bold]")
        console.print(f"  数据目录: {stats['data_dir']}")
        console.print(f"  总大小: {stats['total_size_human']}")
        console.print(f"  文件数: {stats['file_count']}")
        console.print(f"  记忆文件: {stats['memory_files']}")


# ========== 认证命令 ==========

auth_app = typer.Typer(name="auth", help="用户认证")
app.add_typer(auth_app, name="auth")


@auth_app.command("login")
def auth_login(
    provider: str = typer.Option("github", "--provider", "-p", help="OAuth 提供商 (github/google)"),
):
    """登录用户"""
    ensure_initialized()
    console.print(get_banner())
    console.print(f"\n[bold]登录 via {provider}[/bold]\n")
    
    # TODO: 实现 OAuth 登录流程
    # 1. 生成 OAuth URL
    # 2. 打开浏览器
    # 3. 接收回调
    # 4. 创建/获取用户
    # 5. 创建会话
    
    console.print("[yellow]OAuth 登录功能开发中...[/yellow]")
    console.print("\n目前可以先使用本地用户:")
    console.print("  huaqi auth create-local --email your@email.com --username yourname")


@auth_app.command("logout")
def auth_logout():
    """退出登录"""
    global _current_user
    _current_user = None
    console.print("[green]已退出登录[/green]")


@auth_app.command("whoami")
def auth_whoami():
    """显示当前用户"""
    if _current_user:
        console.print(f"当前用户: {_current_user}")
    else:
        console.print("未登录")


@auth_app.command("create-local")
def auth_create_local(
    email: str = typer.Option(..., "--email", "-e", help="邮箱"),
    username: str = typer.Option(..., "--username", "-u", help="用户名"),
    display_name: Optional[str] = typer.Option(None, "--name", "-n", help="显示名称"),
):
    """创建本地用户（开发测试用）"""
    ensure_initialized()
    
    try:
        user = _user_manager.create_user(
            email=email,
            username=username,
            provider="local",
            provider_id=email,
            display_name=display_name or username
        )
        console.print(f"[green]用户创建成功:[/green] {user.user_id}")
        console.print(f"  邮箱: {user.email}")
        console.print(f"  用户名: {user.username}")
        
        # 自动切换到新用户
        _config_manager.switch_user(user.user_id)
        global _current_user
        _current_user = user.user_id
        console.print(f"\n[dim]已自动切换到新用户[/dim]")
        
    except ValueError as e:
        console.print(f"[red]创建失败: {e}[/red]")


@auth_app.command("list")
def auth_list():
    """列出所有用户"""
    ensure_initialized()
    
    users = _user_manager.list_users()
    
    if not users:
        console.print("暂无用户")
        return
    
    console.print(f"[bold]共 {len(users)} 个用户:[/bold]\n")
    
    for user in users:
        marker = " →" if user.user_id == _current_user else "  "
        console.print(f"{marker} {user.username} ({user.email})")
        console.print(f"    ID: {user.user_id}")
        console.print(f"    提供商: {user.provider}")
        console.print()


# ========== 配置命令 ==========

config_app = typer.Typer(name="config", help="配置管理")
app.add_typer(config_app, name="config")


@config_app.command("init")
def config_init():
    """初始化系统配置"""
    ensure_initialized()
    console.print(get_banner())
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    console.print(f"\n[green]✓ 数据目录已创建:[/green] {DATA_DIR}")
    
    # 检查用户
    users = _user_manager.list_users()
    if not users:
        console.print("\n[yellow]提示: 还没有用户，请先创建:[/yellow]")
        console.print("  huaqi auth create-local --email your@email.com --username yourname")
    else:
        console.print(f"\n[dim]已有 {len(users)} 个用户[/dim]")


@config_app.command("get")
def config_get(key: str):
    """获取配置项"""
    ensure_initialized()
    user_id = require_login()
    
    value = _config_manager.get(key, user_id=user_id)
    console.print(f"{key}: {value}")


@config_app.command("set")
def config_set(key: str, value: str):
    """设置配置项"""
    ensure_initialized()
    user_id = require_login()
    
    # 尝试解析值类型
    try:
        # 尝试解析为布尔值
        if value.lower() in ("true", "false"):
            parsed_value = value.lower() == "true"
        # 尝试解析为数字
        elif value.isdigit():
            parsed_value = int(value)
        elif "." in value and value.replace(".", "").isdigit():
            parsed_value = float(value)
        else:
            parsed_value = value
    except:
        parsed_value = value
    
    _config_manager.set(key, parsed_value, user_id=user_id)
    console.print(f"[green]✓ 已设置:[/green] {key} = {parsed_value}")


@config_app.command("show")
def config_show():
    """显示当前配置"""
    ensure_initialized()
    user_id = require_login()
    
    config = _config_manager.load_config(user_id)
    
    console.print("[bold]当前配置:[/bold]\n")
    console.print(f"用户ID: {config.user_id}")
    console.print(f"默认 LLM: {config.llm_default_provider}")
    console.print(f"主题: {config.interface_theme}")
    console.print(f"同步: {'已启用' if config.sync.enabled else '未启用'}")


# ========== 记忆命令 ==========

memory_app = typer.Typer(name="memory", help="记忆管理")
app.add_typer(memory_app, name="memory")


@memory_app.command("init")
def memory_init(
    quick: bool = typer.Option(False, "--quick", "-q", help="快速初始化（最小化档案）"),
    name: str = typer.Option(None, "--name", "-n", help="你的名字（快速模式）"),
    occupation: str = typer.Option(None, "--occupation", "-o", help="职业（快速模式）"),
):
    """初始化记忆档案"""
    ensure_initialized()
    user_id = require_login()
    
    from huaqi.core.memory_initializer import init_memory_command
    
    memory_manager = UserMemoryManager(_config_manager, user_id)
    
    if quick:
        # 快速模式
        if not name:
            name = Prompt.ask("你的名字")
        if not occupation:
            occupation = Prompt.ask("你的职业", default="未知")
        
        init_memory_command(memory_manager, quick=True, name=name, occupation=occupation)
    else:
        # 交互式向导
        init_memory_command(memory_manager, quick=False)


@memory_app.command("search")
def memory_search(query: str):
    """搜索记忆"""
    ensure_initialized()
    user_id = require_login()
    
    memory_manager = UserMemoryManager(_config_manager, user_id)
    results = memory_manager.search_memories(query)
    
    if results:
        console.print(f"[bold]找到 {len(results)} 条记忆:[/bold]\n")
        for result in results[:10]:
            console.print(f"  📄 {result['path']}")
    else:
        console.print("未找到相关记忆")


@memory_app.command("status")
def memory_status():
    """查看记忆库状态"""
    ensure_initialized()
    user_id = require_login()
    
    memory_manager = UserMemoryManager(_config_manager, user_id)
    
    # 统计各类型记忆
    all_memories = memory_manager.list_memories()
    
    type_counts = {}
    for memory in all_memories:
        mem_type = memory["type"]
        type_counts[mem_type] = type_counts.get(mem_type, 0) + 1
    
    console.print("[bold]记忆库状态:[/bold]\n")
    console.print(f"总计: {len(all_memories)} 条记忆")
    console.print()
    
    if type_counts:
        console.print("按类型分布:")
        for mem_type, count in sorted(type_counts.items()):
            console.print(f"  {mem_type}: {count} 条")


@memory_app.command("list")
def memory_list(type_filter: Optional[str] = typer.Option(None, "--type", "-t", help="按类型过滤")):
    """列出所有记忆"""
    ensure_initialized()
    user_id = require_login()
    
    memory_manager = UserMemoryManager(_config_manager, user_id)
    memories = memory_manager.list_memories(type_filter)
    
    if memories:
        console.print(f"[bold]共 {len(memories)} 条记忆:[/bold]\n")
        for memory in memories[:20]:
            console.print(f"  📄 {memory['path']}")
        if len(memories) > 20:
            console.print(f"\n  ... 还有 {len(memories) - 20} 条")
    else:
        console.print("暂无记忆")


# ========== 对话命令 ==========

@app.command()
def chat(
    quick: str = typer.Option(None, "--quick", "-q", help="快速问答模式（单次）"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="是否流式输出"),
):
    """开始与 AI 同伴对话"""
    ensure_initialized()
    user_id = require_login()
    
    from huaqi.core.conversation import ConversationManager
    from huaqi.core.llm import init_llm_manager
    
    console.print(get_banner())
    console.print()
    
    # 检查 LLM 配置
    llm_manager = init_llm_manager()
    config = _config_manager.load_config(user_id)
    
    # 如果没有配置 LLM，使用 dummy
    if not config.llm_providers:
        console.print("[yellow]提示: 尚未配置 LLM，使用虚拟模式[/yellow]")
        console.print("请配置真实的 LLM 提供商以获得更好的体验:")
        console.print("  huaqi config set llm_default_provider claude")
        console.print("  huaqi config set llm_providers.claude.api_key YOUR_API_KEY")
        
        from huaqi.core.llm import LLMConfig
        llm_manager.add_config(LLMConfig(
            provider="dummy",
            model="dummy",
        ))
        llm_manager.set_active("dummy")
    
    # 初始化对话管理器
    conversation = ConversationManager(
        config_manager=_config_manager,
        llm_manager=llm_manager,
        user_id=user_id,
    )
    
    # 快速问答模式
    if quick:
        console.print(f"[bold]你:[/bold] {quick}\n")
        console.print("[bold]Huaqi:[/bold] ", end="")
        
        if stream:
            response_text = ""
            for chunk in conversation.chat(quick, stream=True):
                console.print(chunk, end="")
                response_text += chunk
            console.print()
        else:
            response = conversation.chat(quick, stream=False)
            console.print(response)
        
        return
    
    # 交互式对话模式
    console.print("[dim]开始对话，输入 'exit' 或 'quit' 退出，输入 'clear' 清除上下文[/dim]\n")
    
    while True:
        try:
            # 获取用户输入
            user_input = console.input("[bold]你:[/bold] ").strip()
            
            if not user_input:
                continue
            
            # 处理特殊命令
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("\n[dim]再见！期待下次与你交流。[/dim]")
                break
            
            if user_input.lower() == "clear":
                conversation.clear_session()
                console.print("[dim]会话上下文已清除[/dim]\n")
                continue
            
            if user_input.lower() == "status":
                session = conversation.get_session()
                if session:
                    console.print(f"[dim]当前会话: {session.session_id}, 共 {len(session.turns)} 轮对话[/dim]\n")
                else:
                    console.print("[dim]无活动会话[/dim]\n")
                continue
            
            # 对话
            console.print()
            console.print("[bold cyan]Huaqi:[/bold cyan] ", end="")
            
            if stream:
                for chunk in conversation.chat(user_input, stream=True):
                    console.print(chunk, end="")
                console.print("\n")
            else:
                response = conversation.chat(user_input, stream=False)
                console.print(response)
                console.print()
                
        except KeyboardInterrupt:
            console.print("\n\n[dim]已中断对话[/dim]")
            break
        except EOFError:
            console.print("\n\n[dim]再见！[/dim]")
            break


# ========== 技能命令 ==========

skill_app = typer.Typer(name="skill", help="技能管理")
app.add_typer(skill_app, name="skill")


@skill_app.command("list")
def skill_list():
    """列出可用技能"""
    console.print("可用技能:")
    console.print("  [dim]暂无已配置的技能[/dim]")


# ========== 导入命令 ==========

@app.command()
def import_files(
    source: Path = typer.Argument(..., help="要导入的文件或目录路径"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="预览模式，不实际导入"),
    wizard: bool = typer.Option(False, "--wizard", "-w", help="使用交互式向导"),
):
    """导入外部文档作为记忆"""
    ensure_initialized()
    user_id = require_login()
    
    console.print(get_banner())
    console.print()
    
    if not source.exists():
        console.print(f"[red]路径不存在: {source}[/red]")
        raise typer.Exit(1)
    
    from huaqi.memory.importer.batch import ImportWizard, BatchImporter
    
    memory_manager = UserMemoryManager(_config_manager, user_id)
    
    importer = BatchImporter(
        memory_manager=memory_manager,
        llm_client=None,  # TODO: 传入 LLM 客户端
        dry_run=dry_run
    )
    
    if wizard or source.is_dir():
        wizard = ImportWizard(importer)
        wizard.run()
    else:
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
