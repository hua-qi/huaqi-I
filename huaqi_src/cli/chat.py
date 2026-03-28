"""对话模式

chat_mode：传统对话主循环
run_langgraph_chat：LangGraph Agent 对话模式
所有 _handle_* 斜杠命令处理函数
"""

import os
import sys
import random
import socket
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Union

from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live

from huaqi_src.cli.context import (
    console, ensure_initialized,
    _config, _personality, _growth, _diary, _memory_store, _git,
    DATA_DIR,
)
from huaqi_src.cli.ui import prompt_input, clear_screen
from huaqi_src.core.llm import LLMConfig, Message, LLMManager
from huaqi_src.core.ui_utils import get_ui, HuaqiTheme


def _build_system_prompt(include_diary: bool = True) -> str:
    """构建系统提示词"""
    import huaqi_src.cli.context as ctx

    p = ctx._personality.profile
    skills = ctx._growth.list_skills()
    goals = ctx._growth.list_goals()

    skills_text = ", ".join([s.name for s in skills[:3]]) if skills else "暂无"
    goals_text = ", ".join([g.title for g in goals[:2]]) if goals else "暂无"

    diary_context = ""
    if include_diary and ctx._diary:
        recent_diary = ctx._diary.get_recent_context(days=7)
        if recent_diary:
            diary_context = f"\n\n## 用户最近日记\n{recent_diary}"

    user_profile_context = ""
    try:
        from huaqi_src.core.user_profile import get_profile_manager
        profile_manager = get_profile_manager()
        profile_summary = profile_manager.get_system_prompt_addition()
        if profile_summary:
            user_profile_context = f"\n{profile_summary}"
    except Exception:
        pass

    return f"""你是 {p.name}，用户的个人 AI {p.role}。{user_profile_context}

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


def _generate_streaming_response(
    user_input: str,
    history: List[Dict[str, str]],
    system_prompt: str
) -> Iterator[str]:
    """生成流式回复（迭代器），带超时和异常处理"""
    from openai import APITimeoutError, APIError, APIConnectionError
    import huaqi_src.cli.context as ctx

    llm_manager = LLMManager()
    config = ctx._config.load_config()
    provider_name = config.llm_default_provider

    if provider_name not in config.llm_providers:
        yield "[LLM 未配置] 请先运行: huaqi config set-llm"
        return

    provider_config = config.llm_providers[provider_name]
    api_key = provider_config.api_key or os.environ.get("WQ_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if not api_key:
        yield "[错误] 未配置 API Key。请先运行: huaqi config set-llm --api-key <key>"
        return

    temperature = max(0.0, min(1.0, provider_config.temperature))
    llm_config = LLMConfig(
        provider=provider_config.name,
        model=provider_config.model or "gpt-3.5-turbo",
        api_key=api_key,
        api_base=provider_config.api_base,
        temperature=temperature,
        max_tokens=provider_config.max_tokens,
    )

    llm_manager.add_config(llm_config)
    llm_manager.set_active(provider_config.name)

    messages = [Message.system(system_prompt)]
    for h in history[-5:]:
        messages.append(Message.user(h["user"]))
        messages.append(Message.assistant(h["assistant"]))
    messages.append(Message.user(user_input))

    try:
        response_stream = llm_manager.chat(messages, stream=True)
        for chunk in response_stream:
            if chunk:
                yield chunk
    except APITimeoutError:
        yield "\n\n---\n*⏱️ 请求超时（60秒）。请检查网络连接或稍后重试。*"
    except APIConnectionError:
        yield "\n\n---\n*🔌 连接失败。请检查 API 地址和网络环境。*"
    except APIError as e:
        if "thinking" in str(e).lower() and "reasoning_content" in str(e).lower():
            yield "\n\n---\n*🔄 模型 thinking 模式不兼容，尝试重新连接...*"
            try:
                messages = [Message.system(system_prompt), Message.user(user_input)]
                response = llm_manager.chat(messages, stream=False)
                yield response.content
            except Exception as retry_e:
                yield f"\n\n---\n*❌ 重试失败: {str(retry_e)[:100]}*"
        else:
            yield f"\n\n---\n*⚠️ API 错误: {str(e)[:100]}*"
    except socket.timeout:
        yield "\n\n---\n*⏱️ 网络超时。请检查网络连接或稍后重试。*"
    except Exception as e:
        yield f"\n\n---\n*❌ 发生错误: {str(e)[:100]}*"

    yield ""


def _handle_report_command(parts: list):
    """处理报告命令"""
    from huaqi_src.core.pattern_learning import get_pattern_engine

    engine = get_pattern_engine()

    if len(parts) < 2:
        report = engine.get_latest_weekly_report()
        if report:
            console.print(f"\n{engine.format_weekly_report(report)}\n")
        else:
            console.print("[dim]正在生成周报...[/dim]")
            report = engine.generate_weekly_report()
            if report:
                console.print(f"\n{engine.format_weekly_report(report)}\n")
            else:
                console.print("[yellow]数据不足，无法生成周报。再多聊几天吧！[/yellow]\n")
        return

    subcmd = parts[1]

    if subcmd in ("weekly", "w"):
        console.print("[dim]正在生成周报...[/dim]")
        report = engine.generate_weekly_report()
        if report:
            console.print(f"\n{engine.format_weekly_report(report)}\n")
        else:
            console.print("[yellow]数据不足，无法生成周报。再多聊几天吧！[/yellow]\n")
    elif subcmd in ("insights", "i"):
        insights = engine.get_active_insights()
        if insights:
            console.print("\n[bold]💡 你的模式洞察[/bold]\n")
            for insight in insights[:5]:
                emoji = "🔴" if insight.severity == "attention" else "🟡" if insight.severity == "warning" else "🟢" if insight.severity == "positive" else "🔵"
                console.print(f"{emoji} {insight.title}")
                console.print(f"   {insight.description}")
                if insight.recommendation:
                    console.print(f"   💡 {insight.recommendation}")
                console.print()
        else:
            console.print("[dim]暂无洞察，继续记录日记和对话，我会更了解你。[/dim]\n")
    else:
        console.print("[yellow]用法: /report [weekly|insights][/yellow]\n")


def _handle_care_command(parts: list):
    """处理关怀命令"""
    from huaqi_src.core.proactive_care import get_care_engine

    engine = get_care_engine()

    if len(parts) < 2:
        console.print("[dim]正在检查是否需要关怀...[/dim]")
        record = engine.check_and_trigger()
        if record:
            console.print(f"\n[bold magenta]🌸 Huaqi[/bold magenta]: {record.care_content}\n")
            console.print("[dim]（这是基于你最近状态的关怀）[/dim]\n")
        else:
            console.print("[dim]你最近状态不错，不需要特别关怀。继续保持！[/dim]\n")
        return

    subcmd = parts[1]

    if subcmd in ("status", "s"):
        stats = engine.get_care_stats()
        console.print("\n[bold]💝 关怀统计[/bold]\n")
        console.print(f"总关怀次数: {stats['total_cares']}")
        console.print(f"用户回应率: {stats['acknowledgment_rate']*100:.0f}%")
        console.print(f"有用率: {stats['helpful_rate']*100:.0f}%")
        console.print()
    elif subcmd == "config":
        config = engine.config
        console.print("\n[bold]⚙️ 关怀配置[/bold]\n")
        console.print(f"启用状态: {'✅' if config.enabled else '❌'}")
        console.print(f"关怀级别: {config.level}")
        console.print(f"每日最多: {config.max_per_day} 次")
        console.print(f"安静时段: {config.quiet_hours_start}:00 - {config.quiet_hours_end}:00")
        console.print()
        console.print("[dim]修改配置: /care config set <key> <value>[/dim]\n")
    elif subcmd == "set":
        if len(parts) >= 4:
            key, value = parts[2], parts[3]
            try:
                if key in ['max_per_day', 'max_per_week', 'min_silence_hours', 'anxiety_threshold']:
                    value = int(value)
                elif key in ['emotion_threshold']:
                    value = float(value)
                elif key in ['enabled']:
                    value = value.lower() in ['true', 'yes', '1']
                engine.update_config(**{key: value})
                console.print(f"[green]✅ 已更新 {key} = {value}[/green]\n")
            except Exception as e:
                console.print(f"[red]更新失败: {e}[/red]\n")
        else:
            console.print("[yellow]用法: /care set <key> <value>[/yellow]\n")
    else:
        console.print("[yellow]用法: /care [status|config|set <key> <value>][/yellow]\n")


def _handle_history_command(parts: list):
    """处理历史对话命令"""
    import huaqi_src.cli.context as ctx

    if len(parts) < 2:
        _show_recent_history()
        return

    subcmd = parts[1]

    if subcmd in ("list", "l"):
        _show_history_list()
    elif subcmd in ("search", "s"):
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
        _write_diary_interactive()
        return

    subcmd = parts[1]

    if subcmd in ("today", "t"):
        _write_diary_interactive()
    elif subcmd in ("list", "l"):
        _show_diary_list()
    elif subcmd in ("search", "s"):
        if len(parts) >= 3:
            query = " ".join(parts[2:])
            _search_diary(query)
        else:
            console.print("[yellow]用法: /diary search <关键词>[/yellow]")
    elif subcmd in ("import", "i"):
        if len(parts) >= 3:
            _import_diary_from_path(parts[2])
        else:
            console.print("[yellow]用法: /diary import <文件或目录路径>[/yellow]")
    else:
        console.print("[yellow]用法: /diary [today|list|search <关键词>|import <路径>][/yellow]")


def _handle_slash_command(command: str) -> bool:
    """处理斜杠命令，返回 True 表示命令已处理"""
    import huaqi_src.cli.context as ctx

    parts = command[1:].split()
    cmd = parts[0] if parts else ""

    if cmd == "skill":
        if len(parts) >= 2:
            skill_name = " ".join(parts[1:])
            ctx._growth.add_skill(skill_name, "other")
            console.print(f"[green]✅ 已添加技能: {skill_name}[/green]")
        else:
            console.print("[yellow]用法: /skill <技能名称>[/yellow]")
        return True

    elif cmd == "log":
        if len(parts) >= 3:
            try:
                skill_name = parts[1]
                hours = float(parts[2])
                if ctx._growth.log_practice(skill_name, hours):
                    console.print(f"[green]✅ 已记录 {hours} 小时 {skill_name} 练习[/green]")
                else:
                    console.print(f"[yellow]⚠️ 技能 '{skill_name}' 不存在，已自动创建[/yellow]")
                    ctx._growth.add_skill(skill_name, "other")
                    ctx._growth.log_practice(skill_name, hours)
                    console.print(f"[green]✅ 已创建并记录 {hours} 小时 {skill_name} 练习[/green]")
            except ValueError:
                console.print("[red]错误: 小时数必须是数字[/red]")
        else:
            console.print("[yellow]用法: /log <技能名称> <小时数>[/yellow]")
        return True

    elif cmd == "goal":
        if len(parts) >= 2:
            title = " ".join(parts[1:])
            ctx._growth.add_goal(title)
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

    elif cmd in ("history", "h"):
        _handle_history_command(parts)
        return True

    elif cmd == "report":
        _handle_report_command(parts)
        return True

    elif cmd == "care":
        _handle_care_command(parts)
        return True

    elif cmd == "clear":
        clear_screen(console)
        return True

    elif cmd in ("help", "?"):
        _show_chat_help()
        return True

    return False


def _write_diary_interactive():
    import huaqi_src.cli.context as ctx

    date = datetime.now().strftime("%Y-%m-%d")
    console.print(f"\n[bold cyan]📝 写日记 - {date}[/bold cyan]")
    console.print("[dim]输入情绪 (可选，如: 开心、焦虑、平静)，直接回车跳过:[/dim]")
    mood = prompt_input().strip() or None

    console.print("[dim]输入标签 (可选，用空格分隔)，直接回车跳过:[/dim]")
    tags_input = prompt_input().strip()
    tags = tags_input.split() if tags_input else []

    console.print("[dim]输入日记内容 (Ctrl+O 换行，Enter 提交):[/dim]")
    content = prompt_input().strip()

    if not content:
        console.print("[yellow]日记内容为空，已取消[/yellow]")
        return

    ctx._diary.save(date, content, mood, tags)
    console.print(f"[green]✅ 已保存日记 ({len(content)} 字)[/green]\n")


def _show_diary_list():
    import huaqi_src.cli.context as ctx

    entries = ctx._diary.list_entries(limit=10)
    if not entries:
        console.print("\n[yellow]暂无日记[/yellow]")
        console.print("[dim]使用 /diary 或 /diary today 添加日记[/dim]\n")
        return

    console.print("\n[bold cyan]📝 日记列表[/bold cyan]\n")
    for entry in entries:
        mood_icon = f" [{entry.mood}]" if entry.mood else ""
        tags_str = f" ({', '.join(entry.tags)})" if entry.tags else ""
        preview = entry.content[:50].replace("\n", " ")
        if len(entry.content) > 50:
            preview += "..."
        console.print(f"[cyan]{entry.date}[/cyan]{mood_icon}{tags_str}")
        console.print(f"  {preview}")
        console.print()


def _search_diary(query: str):
    import huaqi_src.cli.context as ctx

    entries = ctx._diary.search(query)
    if not entries:
        console.print(f"\n[yellow]未找到包含 '{query}' 的日记[/yellow]\n")
        return

    console.print(f"\n[bold cyan]📝 搜索结果 ({len(entries)} 篇)[/bold cyan]\n")
    for entry in entries:
        mood_icon = f" [{entry.mood}]" if entry.mood else ""
        console.print(f"[cyan]{entry.date}[/cyan]{mood_icon}")
        lines = entry.content.split("\n")
        for line in lines:
            if query.lower() in line.lower():
                console.print(f"  ...{line[:100]}...")
                break
        console.print()


def _show_recent_history():
    import huaqi_src.cli.context as ctx

    conversations = ctx._memory_store.list_conversations(limit=5)
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
    import huaqi_src.cli.context as ctx

    conversations = ctx._memory_store.list_conversations(limit=20)
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
    import huaqi_src.cli.context as ctx

    results = ctx._memory_store.search_conversations(query)
    if not results:
        console.print(f"\n[yellow]未找到包含 '{query}' 的对话[/yellow]\n")
        return

    console.print(f"\n[bold cyan]💬 搜索结果 ({len(results)} 条)[/bold cyan]\n")
    for result in results:
        created = result.get("created_at", "")[:16] if result.get("created_at") else "未知"
        console.print(f"[cyan]{created}[/cyan]")
        context = result.get("context", "")[:200]
        if len(result.get("context", "")) > 200:
            context += "..."
        console.print(f"  {context}")
        console.print()


def _import_diary_from_path(source_path: str):
    import huaqi_src.cli.context as ctx

    path = Path(source_path).expanduser()
    if not path.exists():
        console.print(f"[red]路径不存在: {source_path}[/red]")
        return

    console.print(f"[dim]正在从 {source_path} 导入日记...[/dim]")
    count = ctx._diary.import_from_markdown(path)
    console.print(f"[green]✅ 成功导入 {count} 篇日记[/green]\n")


def _show_chat_help():
    ui = get_ui(console)
    ui.show_header("可用命令", ui.theme.EMOJI_INFO)

    commands = {
        "/skill <名称>": "添加新技能",
        "/log <技能> <小时>": "记录练习时间",
        "/goal <标题>": "设定新目标",
        "/diary": "写日记",
        "/diary list": "查看日记列表",
        "/skills": "查看技能列表",
        "/goals": "查看目标列表",
        "/report": "查看本周报告",
        "/report insights": "查看模式洞察",
        "/care": "手动触发关怀检查",
        "/care status": "查看关怀统计",
        "/clear": "清屏",
        "/status": "查看详细状态",
        "/help": "显示此帮助",
        "exit / quit": "退出对话",
    }

    for cmd, desc in commands.items():
        console.print(f"  [bold cyan]{cmd:20}[/bold cyan] {desc}")

    console.print(f"\n[bold]快捷键:[/bold]")
    console.print(f"  [{HuaqiTheme.INFO}]↑/↓[/{HuaqiTheme.INFO}] 历史记录  •  [{HuaqiTheme.INFO}]Tab[/{HuaqiTheme.INFO}] 自动补全  •  [{HuaqiTheme.INFO}]Ctrl+R[/{HuaqiTheme.INFO}] 搜索历史")
    console.print(f"  [{HuaqiTheme.INFO}]Ctrl+L[/{HuaqiTheme.INFO}] 清屏  •  [{HuaqiTheme.INFO}]Ctrl+C[/{HuaqiTheme.INFO}] 取消输入")
    console.print(f"  [{HuaqiTheme.INFO}]Ctrl+O[/{HuaqiTheme.INFO}] 或 [{HuaqiTheme.INFO}]Esc+Enter[/{HuaqiTheme.INFO}] 换行  •  [{HuaqiTheme.INFO}]Enter[/{HuaqiTheme.INFO}] 提交")
    console.print()


def _show_status_compact():
    import huaqi_src.cli.context as ctx

    ui = get_ui(console)
    skills = ctx._growth.list_skills()
    goals = ctx._growth.list_goals()

    total_hours = sum(s.total_hours for s in skills)
    active_goals = sum(1 for g in goals if g.status == "active")
    completed_goals = sum(1 for g in goals if g.status == "completed")

    items = {
        "技能数": str(len(skills)),
        "总时长": f"{total_hours:.1f}h",
        "进行中目标": str(active_goals),
        "已完成目标": str(completed_goals),
    }

    ui.show_status_card("当前状态", items, ui.theme.EMOJI_TARGET)
    ui.blank_line()


def _show_detailed_status():
    import huaqi_src.cli.context as ctx
    from rich import box
    from rich.table import Table

    ui = get_ui(console)
    skills = ctx._growth.list_skills()
    goals = ctx._growth.list_goals()
    p = ctx._personality.profile

    total_hours = sum(s.total_hours for s in skills)
    active_goals = sum(1 for g in goals if g.status == "active")
    completed_goals = sum(1 for g in goals if g.status == "completed")

    ui.show_header("当前状态", ui.theme.EMOJI_TARGET)
    ui.show_status_card("成长概览", {
        "技能数": str(len(skills)),
        "总时长": f"{total_hours:.1f}h",
        "进行中目标": str(active_goals),
        "已完成目标": str(completed_goals),
    }, ui.theme.EMOJI_FIRE)
    ui.blank_line()

    ui.show_header("AI 人格", ui.theme.EMOJI_BOT)
    ui.show_status_card("", {
        "名称": p.name,
        "角色": p.role,
        "风格": p.tone,
        "正式程度": f"{p.formality:.1f}",
        "共情水平": f"{p.empathy:.1f}",
        "幽默程度": f"{p.humor:.1f}",
    })
    ui.blank_line()

    if skills:
        ui.show_header("技能进展", ui.theme.EMOJI_STAR)
        table = ui.create_data_table([
            ("技能", "cyan", None),
            ("类型", "dim", 12),
            ("总时长", "", 10),
            ("等级", "", 10),
        ])
        for skill in skills:
            table.add_row(skill.name, skill.category, f"{skill.total_hours:.1f}h", skill.current_level)
        ui.console.print(table)
        ui.blank_line()
    else:
        ui.tip("暂无技能记录，使用 /skill <名称> 添加")

    if goals:
        ui.show_header("目标追踪", ui.theme.EMOJI_TARGET)
        for goal in goals:
            progress = ui.show_progress_bar(goal.title, goal.progress, 100)
            status_icon = "✅" if goal.status == "completed" else "⏳"
            ui.console.print(f"{status_icon} [bold]{goal.title}[/bold]")
            ui.console.print(f"   {progress}")
        ui.blank_line()
    else:
        ui.tip("暂无目标，使用 /goal <标题> 添加")

    ui.show_header("系统信息", "⚙️")
    git_status = ctx._git.get_status() if ctx._git else {}
    ui.show_status_card("", {
        "数据目录": str(ctx.DATA_DIR),
        "Git同步": "✅ 已启用" if git_status.get("initialized") else "❌ 未启用",
        "LLM提供商": ctx._config.load_config().llm_default_provider,
    })


def _show_skills_list():
    import huaqi_src.cli.context as ctx
    from rich import box
    from rich.table import Table

    skills = ctx._growth.list_skills()
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
        table.add_row(skill.name, skill.category, skill.current_level, f"{skill.total_hours:.1f}h", "-", "-")

    console.print(table)
    console.print()


def _show_goals_list():
    import huaqi_src.cli.context as ctx

    goals = ctx._growth.list_goals()
    if not goals:
        console.print("\n[yellow]暂无目标[/yellow]")
        console.print("[dim]使用 /goal <标题> 添加目标[/dim]\n")
        return

    console.print("\n[bold yellow]🎯 目标列表[/bold yellow]\n")
    for goal in goals:
        progress_bar = "█" * (goal.progress // 5) + "░" * (20 - goal.progress // 5)
        status_icon = "✅" if goal.status == "completed" else "⏳"
        console.print(f"{status_icon} [bold]{goal.title}[/bold]")
        console.print(f"   进度: [{progress_bar}] {goal.progress}%")
        console.print(f"   描述: {goal.description or '无'}")
        console.print(f"   创建: {goal.created_at[:10] if goal.created_at else '未知'}\n")


def run_langgraph_chat():
    """运行 LangGraph Agent 对话模式"""
    try:
        from huaqi_src.agent import ChatAgent

        console.print("\n[bold magenta]🌸 Huaqi Agent[/bold magenta] - 智能 AI 同伴")
        console.print("[dim]使用 LangGraph Agent 架构 | 输入 /help 查看命令, exit 退出对话[/dim]\n")

        agent = ChatAgent()

        while True:
            try:
                user_input = prompt_input().strip()
                if not user_input:
                    continue

                if user_input.lower() in ("exit", "quit", "退出"):
                    console.print("\n[dim]👋 再见！[/dim]\n")
                    break

                if user_input == "/help":
                    console.print("\n[bold cyan]📚 可用命令[/bold cyan]")
                    console.print("  /reset - 重置会话")
                    console.print("  /state - 查看当前状态")
                    console.print("  /clear - 清屏")
                    console.print("  /help - 显示帮助")
                    console.print("  exit/quit - 退出对话")
                    console.print("\n[bold]快捷键:[/bold]")
                    console.print("  ↑/↓ 历史记录  •  Tab 自动补全  •  Ctrl+R 搜索历史")
                    console.print("  Ctrl+L 清屏  •  Ctrl+C 取消输入")
                    console.print("  Ctrl+O 或 Esc+Enter 换行  •  Enter 提交\n")
                    continue

                if user_input == "/clear":
                    clear_screen(console)
                    continue

                if user_input == "/reset":
                    agent = ChatAgent()
                    console.print("[dim]会话已重置[/dim]\n")
                    continue

                if user_input == "/state":
                    state = agent.get_state()
                    console.print(f"\n[dim]当前状态: {state.get('current_node', 'unknown')}[/dim]\n")
                    continue

                response = agent.run(user_input)
                console.print(f"\n[bold magenta]🌸 Huaqi[/bold magenta]: {response}\n")

            except KeyboardInterrupt:
                console.print("\n\n[dim]已中断[/dim]\n")
                break
            except EOFError:
                console.print("\n\n[dim]再见！[/dim]\n")
                break

    except ImportError as e:
        console.print(f"[red]LangGraph Agent 不可用: {e}[/red]")
        console.print("[dim]回退到传统模式...[/dim]\n")
        chat_mode()


def chat_mode():
    """交互式对话模式"""
    import huaqi_src.cli.context as ctx

    ensure_initialized()

    console.print("\n[bold magenta]🌸 Huaqi[/bold magenta] - 个人 AI 同伴")
    console.print("[dim]输入 /help 查看命令, exit 退出对话[/dim]\n")

    try:
        from huaqi_src.core.user_profile import get_data_extractor
        extractor = get_data_extractor()

        if not extractor.is_extracting() and extractor.get_result() is None:
            _llm_for_extraction = LLMManager()
            config = ctx._config.load_config()
            provider_name = config.llm_default_provider

            if provider_name in config.llm_providers:
                provider_config = config.llm_providers[provider_name]
                api_key = provider_config.api_key or os.environ.get("WQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
                llm_config = LLMConfig(
                    provider=provider_config.name,
                    model=provider_config.model,
                    api_key=api_key,
                    api_base=provider_config.api_base,
                    temperature=0.3,
                    max_tokens=1000,
                    timeout=30,
                )
                _llm_for_extraction.add_config(llm_config)
                _llm_for_extraction.set_active(provider_config.name)
                extractor.start_extraction(_llm_for_extraction)
                console.print("[dim]💡 正在分析你的日记和对话...[/dim]\n")
    except Exception:
        pass

    try:
        from huaqi_src.core.proactive_care import get_care_engine
        care_engine = get_care_engine()
        care_record = care_engine.check_and_trigger()
        if care_record:
            console.print(f"\n[bold magenta]🌸 Huaqi[/bold magenta]: {care_record.care_content}\n")
            console.print("[dim]（这是基于你最近状态的关怀，回复 /care feedback helpful/annoying 告诉我是否有用）[/dim]\n")
    except Exception:
        pass

    try:
        from huaqi_src.core.pattern_learning import get_pattern_engine
        pattern_engine = get_pattern_engine()
        latest_report = pattern_engine.get_latest_weekly_report()
        now = datetime.now()
        current_week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        if not latest_report or latest_report.week_start != current_week_start:
            report = pattern_engine.generate_weekly_report()
            if report:
                console.print("\n" + pattern_engine.format_weekly_report(report) + "\n")
    except Exception:
        pass

    system_prompt = _build_system_prompt()
    conversation_history: List[Dict[str, str]] = []
    last_message_time = datetime.now()

    while True:
        try:
            user_input = prompt_input().strip()
            current_time = datetime.now()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "退出"):
                if conversation_history:
                    from datetime import datetime as dt
                    session_id = dt.now().strftime("%Y%m%d_%H%M%S")
                    turns = [{"user_message": t["user"], "assistant_response": t["assistant"]} for t in conversation_history]
                    ctx._memory_store.save_conversation(
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

            timestamp = datetime.now().strftime("%H:%M")
            steps = []

            def _create_status_panel():
                content = "\n".join(steps) if steps else ""
                return Panel(
                    content,
                    title=f"[bold magenta]🌸 Huaqi[/bold magenta] [dim]{timestamp}[/dim]",
                    title_align="left",
                    border_style="magenta",
                    padding=(0, 1),
                )

            with Live(_create_status_panel(), console=console, refresh_per_second=10, transient=False) as live:
                steps.append("[dim]正在思考...[/dim]")
                live.update(_create_status_panel())

                full_response = []
                for chunk in _generate_streaming_response(user_input, conversation_history, system_prompt):
                    full_response.append(chunk)
                    response_text = "".join(full_response)
                    steps[-1] = "[dim]2. 调用 LLM 中... ✨[/dim]"
                    live.update(Panel(
                        Markdown(response_text),
                        title=f"[bold magenta]🌸 Huaqi[/bold magenta] [dim]{timestamp}[/dim]",
                        title_align="left",
                        border_style="magenta",
                        padding=(0, 1),
                    ))

            console.print()
            console.print()

            conversation_history.append({"user": user_input, "assistant": response_text})
            if len(conversation_history) > 10:
                conversation_history = conversation_history[-10:]

            last_message_time = current_time

        except KeyboardInterrupt:
            console.print("\n\n[dim]已中断对话[/dim]\n")
            break
        except EOFError:
            console.print("\n\n[dim]再见！[/dim]\n")
            break
