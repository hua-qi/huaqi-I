#!/usr/bin/env python3
"""Huaqi CLI - 个人 AI 同伴系统

交互式对话模式，支持配置管理

Usage:
    huaqi              # 进入交互式对话
    huaqi status       # 查看系统状态
    huaqi config       # 配置管理
"""

import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Iterator, Union
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich import box
from rich.text import Text
import re
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.named_commands import accept_line
from prompt_toolkit.filters import has_selection

# prompt_toolkit 样式
_prompt_style = Style.from_dict({
    'prompt': '#00d7d7 bold',
})

# 创建带样式的 prompt 会话
_prompt_session: Optional[PromptSession] = None


def _get_prompt_session() -> PromptSession:
    """获取 prompt 会话（延迟初始化）"""
    global _prompt_session
    if _prompt_session is None:
        # 配置快捷键
        bindings = KeyBindings()

        # Ctrl+O 插入换行（更可靠的换行方式）
        @bindings.add('c-o')
        def insert_newline(event):
            event.current_buffer.insert_text('\n')

        # Enter 提交输入（当没有选中文字时）
        @bindings.add('enter', filter=~has_selection)
        def submit_input(event):
            event.current_buffer.validate_and_handle()

        _prompt_session = PromptSession(
            message=[('class:prompt', '> ')],
            style=_prompt_style,
            key_bindings=bindings,
            multiline=True,
            wrap_lines=True,
        )
    return _prompt_session


def _prompt_input() -> str:
    """使用 prompt_toolkit 获取输入，支持多字节字符"""
    session = _get_prompt_session()
    return session.prompt()


# 核心模块
from huaqi.core.config_simple import init_config_manager, ConfigManager
from huaqi.core.personality_simple import PersonalityEngine
from huaqi.core.hooks_simple import HookManager
from huaqi.core.growth_simple import GrowthTracker
from huaqi.core.diary_simple import DiaryStore
from huaqi.core.git_auto_commit import GitAutoCommit
from huaqi.core.llm import LLMConfig, Message, LLMManager
from huaqi.memory.storage.markdown_store import MarkdownMemoryStore

console = Console()
app = typer.Typer(
    name="huaqi",
    help="个人 AI 同伴系统",
    no_args_is_help=False,
)

# 数据目录
DATA_DIR: Path = Path("/Users/lianzimeng/workspace/huaqi")
MEMORY_DIR: Path = Path("/Users/lianzimeng/workspace/huaqi/memory")

# 核心组件缓存
_config: Optional[ConfigManager] = None
_personality: Optional[PersonalityEngine] = None
_hooks: Optional[HookManager] = None
_growth: Optional[GrowthTracker] = None
_diary: Optional[DiaryStore] = None
_memory_store: Optional[MarkdownMemoryStore] = None
_git: Optional[GitAutoCommit] = None


def ensure_initialized():
    """确保核心组件已初始化"""
    global _config, _personality, _hooks, _growth, _diary, _memory_store, _git
    
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    if _config is None:
        _config = init_config_manager(DATA_DIR)
    if _personality is None:
        _personality = PersonalityEngine(MEMORY_DIR)
    if _hooks is None:
        _git = GitAutoCommit(MEMORY_DIR)
        _hooks = HookManager(MEMORY_DIR, git_committer=_git)
    if _growth is None:
        _growth = GrowthTracker(MEMORY_DIR, git_committer=_git)
    if _diary is None:
        _diary = DiaryStore(MEMORY_DIR, git_committer=_git)
    if _memory_store is None:
        _memory_store = MarkdownMemoryStore(MEMORY_DIR / "conversations")


def _build_system_prompt(include_diary: bool = True) -> str:
    """构建系统提示词
    
    Args:
        include_diary: 是否包含最近日记内容
    """
    p = _personality.profile
    skills = _growth.list_skills()
    goals = _growth.list_goals()
    
    skills_text = ", ".join([s.name for s in skills[:3]]) if skills else "暂无"
    goals_text = ", ".join([g.title for g in goals[:2]]) if goals else "暂无"
    
    # 获取最近日记上下文
    diary_context = ""
    if include_diary and _diary:
        recent_diary = _diary.get_recent_context(days=7)
        if recent_diary:
            diary_context = f"""

## 用户最近日记
{recent_diary}"""
    
    return f"""你是 {p.name}，用户的个人 AI {p.role}。

## 你的性格
- 沟通风格: {p.tone}
- 正式程度: {p.formality}
- 共情水平: {p.empathy}
- 幽默程度: {p.humor}

## 用户当前状态
- 技能: {skills_text}
- 目标: {goals_text}{diary_context}

## 行为准则
- 主动关心用户的目标进展
- 适时挑战用户的想法，帮助成长
- 适时给出建议，但不强加
- 参考用户日记了解其近况和情绪

## 交互方式
- 简洁友好的回复
- 可以主动询问用户近况
- 记住用户的偏好和习惯"""


def _generate_response(user_input: str, history: List[Dict[str, str]], system_prompt: str, stream: bool = False) -> Union[str, Iterator[str]]:
    """生成回复（调用 LLM），支持流式输出"""
    try:
        llm_manager = LLMManager()
        
        config = _config.load_config()
        provider_name = config.llm_default_provider
        
        if provider_name not in config.llm_providers:
            msg = "[LLM 未配置] 请先运行: huaqi config set-llm"
            if stream:
                def _iter():
                    yield msg
                return _iter()
            return msg
        
        provider_config = config.llm_providers[provider_name]
        
        # 创建 LLM 配置
        llm_config = LLMConfig(
            provider=provider_config.name,
            model=provider_config.model,
            api_key=provider_config.api_key,
            api_base=provider_config.api_base,
            temperature=provider_config.temperature,
            max_tokens=provider_config.max_tokens,
        )
        
        llm_manager.add_config(llm_config)
        llm_manager.set_active(provider_config.name)
        
        # 构建消息列表
        messages = [Message.system(system_prompt)]
        
        # 添加历史对话
        for h in history[-5:]:
            messages.append(Message.user(h["user"]))
            messages.append(Message.assistant(h["assistant"]))
        
        messages.append(Message.user(user_input))
        
        if stream:
            # 流式输出：返回迭代器
            return llm_manager.chat(messages, stream=True)
        else:
            # 非流式输出：显示思考中动画
            sys.stdout.write("\033[2m\033[36m⠋ 思考中 ...\033[0m")
            sys.stdout.flush()
            try:
                response = llm_manager.chat(messages)
            finally:
                sys.stdout.write("\r\033[2K")
                sys.stdout.flush()
            return response.content
        
    except Exception as e:
        error_msg = f"抱歉，对话出现了问题：{str(e)}"
        console.print(f"[red]LLM 调用失败: {e}[/red]")
        if stream:
            def _iter():
                yield error_msg
            return _iter()
        return error_msg


def _generate_streaming_response(user_input: str, history: List[Dict[str, str]], system_prompt: str) -> Iterator[str]:
    """生成流式回复（迭代器）"""
    try:
        llm_manager = LLMManager()
        
        config = _config.load_config()
        provider_name = config.llm_default_provider
        
        if provider_name not in config.llm_providers:
            yield "[LLM 未配置] 请先运行: huaqi config set-llm"
            return
        
        provider_config = config.llm_providers[provider_name]
        
        llm_config = LLMConfig(
            provider=provider_config.name,
            model=provider_config.model,
            api_key=provider_config.api_key,
            api_base=provider_config.api_base,
            temperature=provider_config.temperature,
            max_tokens=provider_config.max_tokens,
        )
        
        llm_manager.add_config(llm_config)
        llm_manager.set_active(provider_config.name)
        
        # 构建消息列表
        messages = [Message.system(system_prompt)]
        
        for h in history[-5:]:
            messages.append(Message.user(h["user"]))
            messages.append(Message.assistant(h["assistant"]))
        
        messages.append(Message.user(user_input))
        
        for chunk in llm_manager.chat(messages, stream=True):
            yield chunk
            
    except Exception as e:
        console.print(f"[red]LLM 调用失败: {e}[/red]")
        yield f"抱歉，对话出现了问题：{str(e)}"


def _handle_local_response(user_input: str) -> str:
    """本地降级响应"""
    import random
    responses = [
        "明白了，能告诉我更多吗？",
        "我在听，请继续。",
        "这很有意思，你有什么想法？",
        "了解了，需要我帮你记录什么吗？",
    ]
    return random.choice(responses)


def _handle_slash_command(command: str) -> bool:
    """处理斜杠命令，返回 True 表示命令已处理"""
    parts = command[1:].split()
    cmd = parts[0] if parts else ""
    
    if cmd == "skill":
        if len(parts) >= 2:
            skill_name = " ".join(parts[1:])
            _growth.add_skill(skill_name, "other")
            console.print(f"[green]✅ 已添加技能: {skill_name}[/green]")
        else:
            console.print("[yellow]用法: /skill <技能名称>[/yellow]")
        return True
    
    elif cmd == "log":
        if len(parts) >= 3:
            try:
                skill_name = parts[1]
                hours = float(parts[2])
                if _growth.log_practice(skill_name, hours):
                    console.print(f"[green]✅ 已记录 {hours} 小时 {skill_name} 练习[/green]")
                else:
                    console.print(f"[yellow]⚠️ 技能 '{skill_name}' 不存在，已自动创建[/yellow]")
                    _growth.add_skill(skill_name, "other")
                    _growth.log_practice(skill_name, hours)
                    console.print(f"[green]✅ 已创建并记录 {hours} 小时 {skill_name} 练习[/green]")
            except ValueError:
                console.print("[red]错误: 小时数必须是数字[/red]")
        else:
            console.print("[yellow]用法: /log <技能名称> <小时数>[/yellow]")
        return True
    
    elif cmd == "goal":
        if len(parts) >= 2:
            title = " ".join(parts[1:])
            _growth.add_goal(title)
            console.print(f"[green]✅ 已添加目标: {title}[/green]")
        else:
            console.print("[yellow]用法: /goal <目标标题>[/yellow]")
        return True
    
    elif cmd == "status":
        _show_detailed_status()
        return True

    elif cmd == "skills":
        _show_skills_list()
        return True

    elif cmd == "goals":
        _show_goals_list()
        return True

    elif cmd == "diary":
        _handle_diary_command(parts)
        return True

    elif cmd == "history" or cmd == "h":
        _handle_history_command(parts)
        return True

    elif cmd == "help" or cmd == "?":
        _show_chat_help()
        return True

    return False


def _handle_history_command(parts: list):
    """处理历史对话命令"""
    if len(parts) < 2:
        _show_recent_history()
        return

    subcmd = parts[1]

    if subcmd == "list" or subcmd == "l":
        _show_history_list()
    elif subcmd == "search" or subcmd == "s":
        if len(parts) >= 3:
            query = " ".join(parts[2:])
            _search_history(query)
        else:
            console.print("[yellow]用法: /history search <关键词>[/yellow]")
    else:
        console.print("[yellow]用法: /history [list|search <关键词>][/yellow]")


def _handle_diary_command(parts: list):
    """处理日记命令"""
    if len(parts) < 2:
        # 默认写入今天的日记
        _write_diary_interactive()
        return

    subcmd = parts[1]

    if subcmd == "today" or subcmd == "t":
        _write_diary_interactive()
    elif subcmd == "list" or subcmd == "l":
        _show_diary_list()
    elif subcmd == "search" or subcmd == "s":
        if len(parts) >= 3:
            query = " ".join(parts[2:])
            _search_diary(query)
        else:
            console.print("[yellow]用法: /diary search <关键词>[/yellow]")
    elif subcmd == "import" or subcmd == "i":
        if len(parts) >= 3:
            source_path = parts[2]
            _import_diary_from_path(source_path)
        else:
            console.print("[yellow]用法: /diary import <文件或目录路径>[/yellow]")
    else:
        console.print("[yellow]用法: /diary [today|list|search <关键词>|import <路径>][/yellow]")


def _write_diary_interactive():
    """交互式写入日记"""
    from datetime import datetime

    date = datetime.now().strftime("%Y-%m-%d")
    console.print(f"\n[bold cyan]📝 写日记 - {date}[/bold cyan]")
    console.print("[dim]输入情绪 (可选，如: 开心、焦虑、平静)，直接回车跳过:[/dim]")

    mood = _prompt_input().strip() or None

    console.print("[dim]输入标签 (可选，用空格分隔)，直接回车跳过:[/dim]")
    tags_input = _prompt_input().strip()
    tags = tags_input.split() if tags_input else []

    console.print("[dim]输入日记内容 (Ctrl+O 换行，Enter 提交):[/dim]")
    content = _prompt_input().strip()

    if not content:
        console.print("[yellow]日记内容为空，已取消[/yellow]")
        return

    entry = _diary.save(date, content, mood, tags)
    console.print(f"[green]✅ 已保存日记 ({len(content)} 字)[/green]\n")


def _show_diary_list():
    """显示日记列表"""
    entries = _diary.list_entries(limit=10)

    if not entries:
        console.print("\n[yellow]暂无日记[/yellow]")
        console.print("[dim]使用 /diary 或 /diary today 添加日记[/dim]\n")
        return

    console.print("\n[bold cyan]📝 日记列表[/bold cyan]\n")

    for entry in entries:
        mood_icon = f" [{entry.mood}]" if entry.mood else ""
        tags_str = f" ({', '.join(entry.tags)})" if entry.tags else ""
        # 显示前 50 字符作为摘要
        preview = entry.content[:50].replace("\n", " ")
        if len(entry.content) > 50:
            preview += "..."

        console.print(f"[cyan]{entry.date}[/cyan]{mood_icon}{tags_str}")
        console.print(f"  {preview}")
        console.print()


def _search_diary(query: str):
    """搜索日记"""
    entries = _diary.search(query)

    if not entries:
        console.print(f"\n[yellow]未找到包含 '{query}' 的日记[/yellow]\n")
        return

    console.print(f"\n[bold cyan]📝 搜索结果 ({len(entries)} 篇)[/bold cyan]\n")

    for entry in entries:
        mood_icon = f" [{entry.mood}]" if entry.mood else ""
        console.print(f"[cyan]{entry.date}[/cyan]{mood_icon}")
        # 显示包含关键词的上下文
        lines = entry.content.split("\n")
        for i, line in enumerate(lines):
            if query.lower() in line.lower():
                console.print(f"  ...{line[:100]}...")
                break
        console.print()


def _show_recent_history():
    """显示最近对话历史"""
    conversations = _memory_store.list_conversations(limit=5)

    if not conversations:
        console.print("\n[yellow]暂无历史对话[/yellow]")
        console.print("[dim]对话将在退出时自动保存[/dim]\n")
        return

    console.print("\n[bold cyan]💬 最近对话[/bold cyan]\n")

    for conv in conversations:
        created = conv.get("created_at", "")[:16] if conv.get("created_at") else "未知"
        turns = conv.get("turns", 0)
        console.print(f"[cyan]{created}[/cyan] - {turns} 轮对话")

    console.print()


def _show_history_list():
    """显示历史对话列表"""
    conversations = _memory_store.list_conversations(limit=20)

    if not conversations:
        console.print("\n[yellow]暂无历史对话[/yellow]\n")
        return

    console.print("\n[bold cyan]💬 历史对话列表[/bold cyan]\n")

    for i, conv in enumerate(conversations, 1):
        created = conv.get("created_at", "")[:16] if conv.get("created_at") else "未知"
        turns = conv.get("turns", 0)
        filepath = conv.get("filepath", "")
        console.print(f"{i}. [cyan]{created}[/cyan] - {turns} 轮对话 [dim]{filepath}[/dim]")

    console.print()


def _search_history(query: str):
    """搜索历史对话"""
    results = _memory_store.search_conversations(query)

    if not results:
        console.print(f"\n[yellow]未找到包含 '{query}' 的对话[/yellow]\n")
        return

    console.print(f"\n[bold cyan]💬 搜索结果 ({len(results)} 条)[/bold cyan]\n")

    for result in results:
        created = result.get("created_at", "")[:16] if result.get("created_at") else "未知"
        console.print(f"[cyan]{created}[/cyan]")
        # 显示上下文
        context = result.get("context", "")[:200]
        if len(result.get("context", "")) > 200:
            context += "..."
        console.print(f"  {context}")
        console.print()


def _import_diary_from_path(source_path: str):
    """从路径导入日记"""
    from pathlib import Path

    path = Path(source_path).expanduser()

    if not path.exists():
        console.print(f"[red]路径不存在: {source_path}[/red]")
        return

    console.print(f"[dim]正在从 {source_path} 导入日记...[/dim]")
    count = _diary.import_from_markdown(path)
    console.print(f"[green]✅ 成功导入 {count} 篇日记[/green]\n")


def _show_chat_help():
    """显示帮助"""
    console.print("\n[bold cyan]📚 可用命令[/bold cyan]\n")

    console.print("[bold]快捷命令:[/bold]")
    console.print("  [cyan]/skill <名称>[/cyan]        - 添加技能")
    console.print("  [cyan]/log <技能> <小时>[/cyan]   - 记录练习时间")
    console.print("  [cyan]/goal <标题>[/cyan]         - 添加目标")
    console.print("  [cyan]/diary[/cyan]               - 写日记")
    console.print("  [cyan]/diary list[/cyan]          - 查看日记列表")
    console.print("  [cyan]/diary search <关键词>[/cyan] - 搜索日记")
    console.print("  [cyan]/diary import <路径>[/cyan]  - 从 Markdown 导入日记")
    console.print("  [cyan]/history[/cyan]             - 查看最近对话")
    console.print("  [cyan]/history list[/cyan]        - 查看历史对话列表")
    console.print("  [cyan]/history search <关键词>[/cyan] - 搜索历史对话")
    console.print("  [cyan]/skills[/cyan]              - 查看技能列表")
    console.print("  [cyan]/goals[/cyan]               - 查看目标列表")
    console.print("  [cyan]/status[/cyan]              - 查看详细状态")
    console.print("  [cyan]/help[/cyan]                - 显示此帮助")

    console.print("\n[bold]对话命令:[/bold]")
    console.print("  [cyan]help[/cyan]                  - 显示帮助")
    console.print("  [cyan]status[/cyan]                - 查看状态")
    console.print("  [cyan]exit/quit[/cyan]             - 退出对话")

    console.print("\n[bold]多行输入:[/bold]")
    console.print("  [cyan]Ctrl+O[/cyan]                - 换行")
    console.print("  [cyan]Enter[/cyan]                  - 提交\n")


def _show_status_inline():
    """显示简洁状态"""
    skills = _growth.list_skills()
    goals = _growth.list_goals()
    p = _personality.profile
    
    console.print(f"\n[dim]👤 {p.role} | 技能: {len(skills)} | 目标: {len(goals)}[/dim]\n")


def _show_detailed_status():
    """显示详细状态"""
    skills = _growth.list_skills()
    goals = _growth.list_goals()
    p = _personality.profile
    
    # 用户画像面板
    console.print("\n[bold cyan]👤 用户画像[/bold cyan]\n")
    
    persona_table = Table(show_header=False, box=box.ROUNDED)
    persona_table.add_column(style="cyan", width=15)
    persona_table.add_column()
    
    persona_table.add_row("名称", p.name)
    persona_table.add_row("角色", p.role)
    persona_table.add_row("沟通风格", p.tone)
    persona_table.add_row("正式程度", f"{p.formality:.1f}")
    persona_table.add_row("共情水平", f"{p.empathy:.1f}")
    persona_table.add_row("幽默程度", f"{p.humor:.1f}")
    
    console.print(persona_table)
    
    # 技能统计
    if skills:
        console.print("\n[bold green]🎯 技能进展[/bold green]\n")
        skill_table = Table(box=box.SIMPLE)
        skill_table.add_column("技能", style="cyan")
        skill_table.add_column("类型", style="dim")
        skill_table.add_column("总时长", justify="right")
        skill_table.add_column("练习次数", justify="right")
        skill_table.add_column("当前等级", justify="center")
        
        for skill in skills:
            skill_table.add_row(
                skill.name,
                skill.category,
                f"{skill.total_hours:.1f}h",
                str(len([p for p in [] if hasattr(p, 'skill_name') and p.skill_name == skill.name])),  # 简化显示
                skill.current_level
            )
        console.print(skill_table)
    else:
        console.print("\n[dim]暂无技能记录，使用 /skill <名称> 添加[/dim]\n")
    
    # 目标列表
    if goals:
        console.print("\n[bold yellow]🎯 目标追踪[/bold yellow]\n")
        goal_table = Table(box=box.SIMPLE)
        goal_table.add_column("目标", style="cyan")
        goal_table.add_column("进度", width=20)
        goal_table.add_column("状态", justify="center")
        goal_table.add_column("创建时间", style="dim")
        
        for goal in goals:
            progress_bar = "█" * (goal.progress // 10) + "░" * (10 - goal.progress // 10)
            status = "✅ 完成" if goal.status == "completed" else "⏳ 进行中"
            created = goal.created_at[:10] if goal.created_at else "未知"
            goal_table.add_row(
                goal.title,
                f"{progress_bar} {goal.progress}%",
                status,
                created
            )
        console.print(goal_table)
    else:
        console.print("\n[dim]暂无目标，使用 /goal <标题> 添加[/dim]\n")
    
    # 系统信息
    console.print("\n[bold blue]⚙️ 系统信息[/bold blue]\n")
    sys_table = Table(show_header=False, box=box.SIMPLE)
    sys_table.add_column(style="cyan", width=15)
    sys_table.add_column()
    
    sys_table.add_row("数据目录", str(DATA_DIR))
    sys_table.add_row("记忆目录", str(MEMORY_DIR))
    
    git_status = _git.get_status() if _git else {}
    sys_table.add_row("Git同步", "✅ 已启用" if git_status.get("initialized") else "❌ 未启用")
    
    llm_provider = _config.load_config().llm_default_provider
    sys_table.add_row("LLM提供商", llm_provider)
    
    console.print(sys_table)
    console.print()


def _show_skills_list():
    """显示技能列表"""
    skills = _growth.list_skills()
    
    if not skills:
        console.print("\n[yellow]暂无技能记录[/yellow]")
        console.print("[dim]使用 /skill <名称> 添加技能[/dim]\n")
        return
    
    console.print("\n[bold green]🎯 技能列表[/bold green]\n")
    
    table = Table(box=box.ROUNDED)
    table.add_column("技能名称", style="cyan bold")
    table.add_column("类型", style="dim")
    table.add_column("等级", justify="center")
    table.add_column("总时长", justify="right")
    table.add_column("练习次数", justify="right")
    table.add_column("经验值", justify="right")
    
    for skill in skills:
        table.add_row(
            skill.name,
            skill.category,
            skill.current_level,
            f"{skill.total_hours:.1f}h",
            "-",  # practice count not tracked in simple version
            "-"   # xp not tracked in simple version
        )
    
    console.print(table)
    console.print()


def _show_goals_list():
    """显示目标列表"""
    goals = _growth.list_goals()
    
    if not goals:
        console.print("\n[yellow]暂无目标[/yellow]")
        console.print("[dim]使用 /goal <标题> 添加目标[/dim]\n")
        return
    
    console.print("\n[bold yellow]🎯 目标列表[/bold yellow]\n")
    
    for i, goal in enumerate(goals, 1):
        progress_bar = "█" * (goal.progress // 5) + "░" * (20 - goal.progress // 5)
        status_icon = "✅" if goal.status == "completed" else "⏳"
        
        console.print(f"{status_icon} [bold]{goal.title}[/bold]")
        console.print(f"   进度: [{progress_bar}] {goal.progress}%")
        console.print(f"   描述: {goal.description or '无'}")
        console.print(f"   创建: {goal.created_at[:10] if goal.created_at else '未知'}\n")


def chat_mode():
    """交互式对话模式"""
    ensure_initialized()
    
    # 欢迎界面
    console.print("\n" + "=" * 50)
    console.print("[bold magenta]🌸 Huaqi[/bold magenta] - 你的 AI 同伴", justify="center")
    console.print("[dim]输入 /help 查看命令, exit 退出对话[/dim]", justify="center")
    console.print("=" * 50 + "\n")
    
    system_prompt = _build_system_prompt()
    conversation_history: List[Dict[str, str]] = []
    
    # 显示当前状态
    _show_status_inline()
    
    while True:
        try:
            # 获取用户输入（默认多行模式，空行结束）
            user_input = _prompt_input().strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("exit", "quit", "退出"):
                # 保存对话历史
                if conversation_history:
                    from datetime import datetime as dt
                    session_id = dt.now().strftime("%Y%m%d_%H%M%S")
                    turns = [{"user_message": t["user"], "assistant_response": t["assistant"]} for t in conversation_history]
                    _memory_store.save_conversation(
                        session_id=session_id,
                        timestamp=dt.now(),
                        turns=turns,
                        metadata={"type": "chat_session", "turns": len(turns)}
                    )
                console.print("\n[dim]👋 再见！期待下次与你交流。[/dim]\n")
                break
            
            if user_input.lower() == "help":
                _show_chat_help()
                continue
            
            if user_input.lower() == "status":
                _show_detailed_status()
                continue
            
            if user_input.lower().startswith("/"):
                if _handle_slash_command(user_input):
                    continue
                else:
                    console.print("[yellow]未知命令。输入 /help 查看帮助[/yellow]\n")
                    continue
            
            # 生成流式回复 - 使用 rich Live 实现真正的流式渲染
            from datetime import datetime
            from rich.live import Live
            
            timestamp = datetime.now().strftime("%H:%M")
            full_response = []
            
            # 创建动态更新的 Panel
            def _create_response_panel(text: str, is_streaming: bool = True) -> Panel:
                md = Markdown(text)
                footer = "[dim]✨ 生成中...[/dim]" if is_streaming else ""
                return Panel(
                    md,
                    title=f"[bold magenta]🌸 Huaqi[/bold magenta] [dim]{timestamp}[/dim]",
                    title_align="left",
                    border_style="magenta",
                    padding=(0, 1),
                )
            
            # 显示思考中状态
            thinking_panel = Panel(
                "[dim]🤔 正在思考...[/dim]",
                title=f"[bold magenta]🌸 Huaqi[/bold magenta] [dim]{timestamp}[/dim]",
                title_align="left",
                border_style="magenta dim",
                padding=(0, 1),
            )
            
            with Live(thinking_panel, console=console, refresh_per_second=20, transient=False) as live:
                first_chunk = True
                for chunk in _generate_streaming_response(user_input, conversation_history, system_prompt):
                    if first_chunk:
                        first_chunk = False
                    full_response.append(chunk)
                    response_text = "".join(full_response)
                    live.update(_create_response_panel(response_text, is_streaming=True))
                
                # 完成后更新为最终状态
                response_text = "".join(full_response)
                live.update(_create_response_panel(response_text, is_streaming=False))
            
            console.print()  # 换行
            
            # 保存对话历史
            conversation_history.append({"user": user_input, "assistant": response_text})
            if len(conversation_history) > 10:
                conversation_history = conversation_history[-10:]
                
        except KeyboardInterrupt:
            console.print("\n\n[dim]已中断对话[/dim]\n")
            break
        except EOFError:
            console.print("\n\n[dim]再见！[/dim]\n")
            break


# ============ 配置管理 ============

config_app = typer.Typer(name="config", help="系统配置管理")
app.add_typer(config_app)


@config_app.command("show")
def config_show():
    """显示当前配置"""
    ensure_initialized()
    
    config = _config.load_config()
    
    console.print("\n[bold blue]⚙️ 系统配置[/bold blue]\n")
    
    table = Table(show_header=False, box=box.ROUNDED)
    table.add_column(style="cyan", width=20)
    table.add_column()
    
    table.add_row("数据目录", str(DATA_DIR))
    table.add_row("LLM 提供商", config.llm_default_provider)
    
    for name, provider in config.llm_providers.items():
        table.add_row(f"LLM {name}", f"{provider.model} @ {provider.api_base or 'default'}")
    
    table.add_row("界面主题", config.interface_theme)
    
    console.print(table)
    console.print()


@config_app.command("set-llm")
def config_set_llm(
    provider: str = typer.Argument(..., help="提供商名称 (openai/claude/deepseek/dummy)"),
    api_key: str = typer.Option(None, "--api-key", "-k", help="API 密钥"),
    api_base: str = typer.Option(None, "--api-base", "-b", help="API 基础地址"),
    model: str = typer.Option(None, "--model", "-m", help="模型名称"),
):
    """配置 LLM"""
    ensure_initialized()
    
    from huaqi.core.config_simple import LLMProviderConfig
    
    # 读取环境变量中的 API key
    if api_key is None and provider == "openai":
        api_key = os.environ.get("WQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
    
    llm_config = LLMProviderConfig(
        name=provider,
        model=model or provider,
        api_key=api_key,
        api_base=api_base,
    )
    
    config = _config.load_config()
    config.llm_providers[provider] = llm_config
    config.llm_default_provider = provider
    _config.save_config()
    
    console.print(f"\n[green]✅ LLM 已配置: {provider}[/green]")
    if api_base:
        console.print(f"   地址: {api_base}")
    if api_key:
        console.print(f"   API Key: {'*' * 10} (已隐藏)")
    console.print()


@config_app.command("set-data-dir")
def config_set_data_dir(
    path: Path = typer.Argument(..., help="数据目录路径"),
):
    """配置数据存储地址"""
    ensure_initialized()
    
    global DATA_DIR, MEMORY_DIR
    
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    
    _config.set("data_dir", str(path))
    
    console.print(f"\n[green]✅ 数据目录已设置为: {path}[/green]\n")


@config_app.command("get")
def config_get(key: str = typer.Argument(..., help="配置项名称")):
    """获取配置项"""
    ensure_initialized()
    
    value = _config.get(key)
    console.print(f"{key}: {value}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="配置项名称"),
    value: str = typer.Argument(..., help="配置项值"),
):
    """设置配置项"""
    ensure_initialized()
    
    _config.set(key, value)
    console.print(f"[green]✅ 已设置 {key} = {value}[/green]")


# ============ 主命令 ============

@app.command("chat")
def chat_command(
    use_langgraph: bool = typer.Option(True, "--langgraph/--legacy", help="使用 LangGraph Agent 模式"),
):
    """启动对话模式 (新版 LangGraph Agent)"""
    ensure_initialized()
    
    if use_langgraph:
        _chat_langgraph_mode()
    else:
        chat_mode()


@app.command("status")
def show_status():
    """查看完整系统状态"""
    ensure_initialized()
    _show_detailed_status()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", "-d", help="数据目录"),
):
    """Huaqi - 个人 AI 同伴系统"""
    global DATA_DIR, MEMORY_DIR, _config, _personality, _hooks, _growth, _git
    
    if data_dir is not None:
        DATA_DIR = data_dir.expanduser().resolve()
        MEMORY_DIR = Path("/Users/lianzimeng/workspace/huaqi/memory")
        _config = _personality = _hooks = _growth = _git = None
    
    # 如果没有子命令，进入对话模式
    if ctx.invoked_subcommand is None:
        chat_mode()


# ============ Daemon 后台服务 ============

@app.command("daemon")
def daemon_command(
    action: str = typer.Argument(..., help="操作: start/stop/status/list"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="前台运行模式"),
):
    """管理后台定时任务服务"""
    ensure_initialized()
    
    from huaqi.scheduler import get_scheduler_manager, register_default_jobs, default_scheduler_config
    
    scheduler = get_scheduler_manager()
    
    if action == "start":
        if scheduler.is_running():
            console.print("[yellow]⚠️ Daemon 已在运行中[/yellow]")
            return
        
        # 注册默认任务
        register_default_jobs(default_scheduler_config)
        
        # 启动调度器
        scheduler.start()
        
        if foreground:
            console.print("[green]✅ Daemon 已启动 (前台模式)[/green]")
            console.print("[dim]按 Ctrl+C 停止[/dim]\n")
            try:
                # 保持运行
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                scheduler.shutdown()
                console.print("\n[dim]Daemon 已停止[/dim]")
        else:
            console.print("[green]✅ Daemon 已启动 (后台模式)[/green]")
            console.print("[dim]使用 'huaqi daemon stop' 停止[/dim]\n")
    
    elif action == "stop":
        if not scheduler.is_running():
            console.print("[yellow]⚠️ Daemon 未在运行[/yellow]")
            return
        
        scheduler.shutdown()
        console.print("[green]✅ Daemon 已停止[/green]\n")
    
    elif action == "status":
        if scheduler.is_running():
            console.print("[green]● Daemon 运行中[/green]")
            jobs = scheduler.list_jobs()
            if jobs:
                console.print(f"\n[bold]已注册任务 ({len(jobs)}):[/bold]")
                for job in jobs:
                    next_run = job.get("next_run_time", "N/A")
                    console.print(f"  • {job['id']}: {job['trigger']}")
                    console.print(f"    下次执行: {next_run}")
            else:
                console.print("\n[dim]暂无任务[/dim]")
        else:
            console.print("[dim]○ Daemon 未运行[/dim]")
        console.print()
    
    elif action == "list":
        jobs = scheduler.list_jobs()
        if jobs:
            table = Table(title="定时任务列表")
            table.add_column("ID", style="cyan")
            table.add_column("触发器", style="green")
            table.add_column("下次执行", style="yellow")
            
            for job in jobs:
                next_run = job.get("next_run_time", "N/A")
                if next_run:
                    next_run = str(next_run)[:19]
                table.add_row(
                    job["id"],
                    job["trigger"],
                    str(next_run),
                )
            console.print(table)
        else:
            console.print("[dim]暂无任务[/dim]")
        console.print()
    
    else:
        console.print(f"[red]❌ 未知操作: {action}[/red]")
        console.print("可用操作: start, stop, status, list\n")


if __name__ == "__main__":
    app()"}
