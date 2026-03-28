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
from rich.live import Live
import re

# Huaqi UI 工具
from huaqi_src.core.ui_utils import HuaqiUI, get_ui, HuaqiTheme

# Prompt Toolkit 输入组件
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.shortcuts import clear as pt_clear
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers import MarkdownLexer


class HuaqiCommandCompleter(Completer):
    """Huaqi 命令补全器 - 支持命令和历史文本补全"""

    COMMANDS = [
        "/help",
        "/reset",
        "/state",
        "/exit",
        "/quit",
        "/clear",
        "/history",
        "/status",
    ]

    def __init__(self):
        self._word_cache: Dict[str, int] = {}  # 词频缓存

    def _extract_words_from_history(self, history: FileHistory) -> None:
        """从历史记录中提取中文词组"""
        if self._word_cache:
            return

        # 读取历史记录中的所有文本
        texts = []
        try:
            # FileHistory 不直接提供 get_strings，从文件读取
            history_file = Path(history.filename)
            if history_file.exists():
                content = history_file.read_text(encoding='utf-8')
                # 历史文件格式：每两条记录之间有空行，以 "  " 开头的是多行内容
                lines = content.split('\n')
                current_entry = []
                for line in lines:
                    if line.startswith('  '):
                        current_entry.append(line[2:])
                    elif line.strip():
                        if current_entry:
                            texts.append('\n'.join(current_entry))
                            current_entry = []
                        current_entry.append(line)
                if current_entry:
                    texts.append('\n'.join(current_entry))
        except Exception:
            pass

        # 提取中文词组（2-6个字的词语）
        import re
        word_pattern = re.compile(r'[\u4e00-\u9fa5]{2,6}')

        for text in texts:
            # 提取所有可能的中文词组
            for i in range(len(text) - 1):
                for length in range(2, min(7, len(text) - i + 1)):
                    word = text[i:i + length]
                    if word_pattern.fullmatch(word):
                        self._word_cache[word] = self._word_cache.get(word, 0) + 1

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        if not text:
            return

        # 1. 命令补全（以 / 开头）
        if text.startswith("/"):
            for cmd in self.COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))
            return

        # 2. 从历史记录中提取词组进行补全
        if _input_history:
            self._extract_words_from_history(_input_history)

        # 获取当前输入的最后一个词
        words = text.split()
        if not words:
            return

        current_word = words[-1]
        if len(current_word) < 1:
            return

        # 按词频排序，优先返回高频词
        sorted_words = sorted(
            self._word_cache.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 匹配以当前词开头的词组
        for word, count in sorted_words:
            if word.startswith(current_word) and word != current_word:
                yield Completion(
                    word,
                    start_position=-len(current_word),
                    display=f"{word} ({count}次)"
                )


# 全局历史记录和组件
_input_history: Optional[FileHistory] = None
_command_completer = HuaqiCommandCompleter()


def _prompt_input(
    history_file: Optional[Path] = None,
    placeholder: str = "今天有什么想聊的？",
    multiline: bool = True,
) -> str:
    """获取用户输入，支持中文、历史记录、自动补全和多行输入

    Args:
        history_file: 历史记录文件路径，默认为 ~/.huaqi_history
        placeholder: 输入框占位提示文本
        multiline: 是否启用多行模式（默认启用，Esc+Enter 或 Ctrl+O 换行）
    """
    global _input_history

    if history_file is None:
        history_file = Path.home() / ".huaqi_history"

    # 确保历史文件目录存在
    history_file.parent.mkdir(parents=True, exist_ok=True)

    if _input_history is None:
        _input_history = FileHistory(str(history_file))

    bindings = KeyBindings()

    # Ctrl+C: 取消当前输入
    @bindings.add("c-c")
    def _(event):
        event.app.exit(result="")

    # Ctrl+L: 清屏
    @bindings.add("c-l")
    def _(event):
        event.app.output.erase_screen()
        event.app.output.cursor_goto(0, 0)
        event.app.invalidate()

    # Ctrl+O: 插入换行（多行输入模式）
    @bindings.add("c-o")
    def _(event):
        event.current_buffer.insert_text("\n")

    # Esc+Enter: 插入换行（替代 Shift+Enter）
    @bindings.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    # 构造带颜色的提示符
    from prompt_toolkit.formatted_text import ANSI

    # 使用 ANSI 颜色：magenta 的 🌸 和 cyan 的 huaqi
    prompt_message = ANSI("\x1b[35m🌸\x1b[0m \x1b[36mhuaqi\x1b[0m > ")

    try:
        result = prompt(
            prompt_message,
            history=_input_history,
            auto_suggest=AutoSuggestFromHistory(),
            completer=_command_completer,
            key_bindings=bindings,
            enable_suspend=True,
            multiline=False,  # 使用自定义键绑定处理换行
            complete_while_typing=True,
            wrap_lines=True,
        )

        # 空输入提示
        if not result or not result.strip():
            return ""

        return result
    except (EOFError, KeyboardInterrupt):
        return ""


def _clear_screen():
    """清屏"""
    console.clear()


# 核心模块
from huaqi_src.core.config_simple import init_config_manager, ConfigManager
from huaqi_src.core.personality_simple import PersonalityEngine
from huaqi_src.core.hooks_simple import HookManager
from huaqi_src.core.growth_simple import GrowthTracker
from huaqi_src.core.diary_simple import DiaryStore
from huaqi_src.core.git_auto_commit import GitAutoCommit
from huaqi_src.core.llm import LLMConfig, Message, LLMManager
from huaqi_src.memory.storage.markdown_store import MarkdownMemoryStore

def _run_langgraph_chat():
    """运行 LangGraph Agent 对话模式"""
    try:
        from huaqi_src.agent import ChatAgent
        
        console.print("\n[bold magenta]🌸 Huaqi Agent[/bold magenta] - 智能 AI 同伴")
        console.print("[dim]使用 LangGraph Agent 架构 | 输入 /help 查看命令, exit 退出对话[/dim]\n")
        
        agent = ChatAgent()
        
        while True:
            try:
                user_input = _prompt_input().strip()
                
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
                    _clear_screen()
                    continue
                
                if user_input == "/reset":
                    agent = ChatAgent()
                    console.print("[dim]会话已重置[/dim]\n")
                    continue
                
                if user_input == "/state":
                    state = agent.get_state()
                    console.print(f"\n[dim]当前状态: {state.get('current_node', 'unknown')}[/dim]\n")
                    continue
                
                # 使用 Agent 处理
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

console = Console()
app = typer.Typer(
    name="huaqi",
    help="个人 AI 同伴系统",
    no_args_is_help=False,
)

# 数据目录
DATA_DIR: Optional[Path] = None
MEMORY_DIR: Optional[Path] = None

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
    global DATA_DIR, MEMORY_DIR
    
    from huaqi_src.core.config_paths import require_data_dir, get_memory_dir
    
    # 确保数据目录已配置
    DATA_DIR = require_data_dir()
    MEMORY_DIR = get_memory_dir()
    
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
    
    # 获取用户画像信息
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
        
        # 优先从环境变量读取 API key
        api_key = provider_config.api_key or os.environ.get("WQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
        
        # 创建 LLM 配置（temperature 限制在 0-1 范围内）
        temperature = max(0.0, min(1.0, provider_config.temperature))
        llm_config = LLMConfig(
            provider=provider_config.name,
            model=provider_config.model,
            api_key=api_key,
            api_base=provider_config.api_base,
            temperature=temperature,
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
    """生成流式回复（迭代器），带超时和异常处理"""
    import socket
    from openai import APITimeoutError, APIError, APIConnectionError
    
    llm_manager = LLMManager()
    
    config = _config.load_config()
    provider_name = config.llm_default_provider
    
    if provider_name not in config.llm_providers:
        yield "[LLM 未配置] 请先运行: huaqi config set-llm"
        return
    
    provider_config = config.llm_providers[provider_name]
    
    # 优先从环境变量读取 API key，如果不存在则使用配置中的
    api_key = provider_config.api_key or os.environ.get("WQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        yield "[错误] 未配置 API Key。请先运行: huaqi config set-llm --api-key <key>"
        return
    
    # temperature 限制在 0-1 范围内
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
    
    # 构建消息列表
    messages = [Message.system(system_prompt)]
    
    for h in history[-5:]:
        messages.append(Message.user(h["user"]))
        messages.append(Message.assistant(h["assistant"]))
    
    messages.append(Message.user(user_input))
    
    # 调用 LLM，带完整的异常处理
    try:
        response_stream = llm_manager.chat(messages, stream=True)
        for chunk in response_stream:
            if chunk:
                yield chunk
    except APITimeoutError as e:
        yield "\n\n---\n*⏱️ 请求超时（60秒）。请检查网络连接或稍后重试。*"
    except APIConnectionError as e:
        yield "\n\n---\n*🔌 连接失败。请检查 API 地址和网络环境。*"
    except APIError as e:
        if "thinking" in str(e).lower() and "reasoning_content" in str(e).lower():
            # DeepSeek thinking 模式错误 - 使用非流式重试
            yield "\n\n---\n*🔄 模型 thinking 模式不兼容，尝试重新连接...*"
            try:
                # 清除消息中的 assistant 历史，避免 reasoning_content 问题
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
    
    # 确保至少返回一个结束标记
    yield ""


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

    elif cmd == "report":
        _handle_report_command(parts)
        return True
    
    elif cmd == "care":
        _handle_care_command(parts)
        return True
    
    elif cmd == "clear":
        _clear_screen()
        return True

    elif cmd == "help" or cmd == "?":
        _show_chat_help()
        return True

    return False


def _handle_report_command(parts: list):
    """处理报告命令"""
    from huaqi_src.core.pattern_learning import get_pattern_engine
    
    engine = get_pattern_engine()
    
    if len(parts) < 2:
        # 默认显示最新周报
        report = engine.get_latest_weekly_report()
        if report:
            console.print(f"\n{engine.format_weekly_report(report)}\n")
        else:
            # 生成新周报
            console.print("[dim]正在生成周报...[/dim]")
            report = engine.generate_weekly_report()
            if report:
                console.print(f"\n{engine.format_weekly_report(report)}\n")
            else:
                console.print("[yellow]数据不足，无法生成周报。再多聊几天吧！[/yellow]\n")
        return
    
    subcmd = parts[1]
    
    if subcmd == "weekly" or subcmd == "w":
        console.print("[dim]正在生成周报...[/dim]")
        report = engine.generate_weekly_report()
        if report:
            console.print(f"\n{engine.format_weekly_report(report)}\n")
        else:
            console.print("[yellow]数据不足，无法生成周报。再多聊几天吧！[/yellow]\n")
    elif subcmd == "insights" or subcmd == "i":
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
        # 手动触发检查
        console.print("[dim]正在检查是否需要关怀...[/dim]")
        record = engine.check_and_trigger()
        if record:
            console.print(f"\n[bold magenta]🌸 Huaqi[/bold magenta]: {record.care_content}\n")
            console.print("[dim]（这是基于你最近状态的关怀）[/dim]\n")
        else:
            console.print("[dim]你最近状态不错，不需要特别关怀。继续保持！[/dim]\n")
        return
    
    subcmd = parts[1]
    
    if subcmd == "status" or subcmd == "s":
        stats = engine.get_care_stats()
        console.print("\n[bold]💝 关怀统计[/bold]\n")
        console.print(f"总关怀次数: {stats['total_cares']}")
        console.print(f"用户回应率: {stats['acknowledgment_rate']*100:.0f}%")
        console.print(f"有用率: {stats['helpful_rate']*100:.0f}%")
        console.print()
    elif subcmd == "config":
        # 显示当前配置
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
    """显示帮助 - 使用新 UI"""
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
    """显示简洁状态卡片"""
    ui = get_ui(console)
    skills = _growth.list_skills()
    goals = _growth.list_goals()
    
    # 统计信息
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
    """显示详细状态 - 使用新 UI"""
    ui = get_ui(console)
    skills = _growth.list_skills()
    goals = _growth.list_goals()
    p = _personality.profile
    
    # 统计信息
    total_hours = sum(s.total_hours for s in skills)
    active_goals = sum(1 for g in goals if g.status == "active")
    completed_goals = sum(1 for g in goals if g.status == "completed")
    
    # 显示状态卡片
    ui.show_header("当前状态", ui.theme.EMOJI_TARGET)
    ui.show_status_card("成长概览", {
        "技能数": str(len(skills)),
        "总时长": f"{total_hours:.1f}h",
        "进行中目标": str(active_goals),
        "已完成目标": str(completed_goals),
    }, ui.theme.EMOJI_FIRE)
    ui.blank_line()
    
    # 用户画像
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
    
    # 技能列表
    if skills:
        ui.show_header("技能进展", ui.theme.EMOJI_STAR)
        table = ui.create_data_table([
            ("技能", "cyan", None),
            ("类型", "dim", 12),
            ("总时长", "", 10),
            ("等级", "", 10),
        ])
        for skill in skills:
            table.add_row(
                skill.name,
                skill.category,
                f"{skill.total_hours:.1f}h",
                skill.current_level
            )
        ui.console.print(table)
        ui.blank_line()
    else:
        ui.tip("暂无技能记录，使用 /skill <名称> 添加")
    
    # 目标列表
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
    
    # 系统信息
    ui.show_header("系统信息", "⚙️")
    git_status = _git.get_status() if _git else {}
    ui.show_status_card("", {
        "数据目录": str(DATA_DIR),
        "Git同步": "✅ 已启用" if git_status.get("initialized") else "❌ 未启用",
        "LLM提供商": _config.load_config().llm_default_provider,
    })


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
    """交互式对话模式 - 使用新 UI"""
    ensure_initialized()
    
    # 简单的欢迎信息，避免复杂的 UI 渲染影响终端
    console.print("\n[bold magenta]🌸 Huaqi[/bold magenta] - 个人 AI 同伴")
    console.print("[dim]输入 /help 查看命令, exit 退出对话[/dim]\n")
    
    # 启动时异步提取用户信息（后台执行，不阻塞用户输入）
    try:
        from huaqi_src.core.user_profile import get_data_extractor
        extractor = get_data_extractor()
        
        # 如果还没有提取过，启动后台提取
        if not extractor.is_extracting() and extractor.get_result() is None:
            _llm_for_extraction = LLMManager()
            config = _config.load_config()
            provider_name = config.llm_default_provider
            
            if provider_name in config.llm_providers:
                provider_config = config.llm_providers[provider_name]
                # 优先从环境变量读取 API key
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
        pass  # 提取失败不影响主流程
    
    # 启动时检查是否需要主动关怀
    last_message_time = None
    try:
        from huaqi_src.core.proactive_care import get_care_engine
        care_engine = get_care_engine()
        care_record = care_engine.check_and_trigger()
        if care_record:
            console.print(f"\n[bold magenta]🌸 Huaqi[/bold magenta]: {care_record.care_content}\n")
            console.print("[dim]（这是基于你最近状态的关怀，回复 /care feedback helpful/annoying 告诉我是否有用）[/dim]\n")
    except Exception:
        pass  # 关怀检查失败不影响主流程

    # 启动时检查是否需要生成本周报告（每周首次启动）
    try:
        from huaqi_src.core.pattern_learning import get_pattern_engine
        pattern_engine = get_pattern_engine()

        # 检查本周是否已生成过报告
        latest_report = pattern_engine.get_latest_weekly_report()
        now = datetime.now()
        current_week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

        if not latest_report or latest_report.week_start != current_week_start:
            # 本周首次启动，生成周报
            report = pattern_engine.generate_weekly_report()
            if report:
                console.print("\n" + pattern_engine.format_weekly_report(report) + "\n")
    except Exception:
        pass  # 报告生成失败不影响主流程

    system_prompt = _build_system_prompt()
    conversation_history: List[Dict[str, str]] = []
    last_message_time = datetime.now()
    
    while True:
        try:
            # 获取用户输入
            user_input = _prompt_input().strip()
            current_time = datetime.now()
            
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
            
            # 显示处理状态 - 逐步展示
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
            
            from rich.live import Live
            
            with Live(_create_status_panel(), console=console, refresh_per_second=10, transient=False) as live:
                # 调用 LLM
                steps.append("[dim]正在思考...[/dim]")
                live.update(_create_status_panel())
                
                # 生成流式回复
                full_response = []
                for chunk in _generate_streaming_response(user_input, conversation_history, system_prompt):
                    full_response.append(chunk)
                    response_text = "".join(full_response)
                    # 更新状态为生成中
                    steps[-1] = "[dim]2. 调用 LLM 中... ✨[/dim]"
                    live.update(Panel(
                        Markdown(response_text),
                        title=f"[bold magenta]🌸 Huaqi[/bold magenta] [dim]{timestamp}[/dim]",
                        title_align="left",
                        border_style="magenta",
                        padding=(0, 1),
                    ))
                
            console.print()  # 换行
            
            console.print()  # 换行
            
            # 保存对话历史
            conversation_history.append({"user": user_input, "assistant": response_text})
            if len(conversation_history) > 10:
                conversation_history = conversation_history[-10:]
            
            # 更新最后消息时间
            last_message_time = current_time
                
        except KeyboardInterrupt:
            console.print("\n\n[dim]已中断对话[/dim]\n")
            break
        except EOFError:
            console.print("\n\n[dim]再见！[/dim]\n")
            break


# ============ 配置管理 ============

config_app = typer.Typer(name="config", help="系统配置管理")
app.add_typer(config_app)


@config_app.callback(invoke_without_command=True)
def config_callback(ctx: typer.Context):
    """配置管理回调 - 无子命令时显示帮助"""
    if ctx.invoked_subcommand is None:
        ctx.get_help()


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
    api_key: str = typer.Option(..., "--api-key", "-k", help="API 密钥（必填）"),
    api_base: str = typer.Option(None, "--api-base", "-b", help="API 基础地址"),
    model: str = typer.Option(None, "--model", "-m", help="模型名称"),
):
    """配置 LLM"""
    ensure_initialized()
    
    from huaqi_src.core.config_simple import LLMProviderConfig
    
    # 如果没有指定模型，使用适合该提供商的默认模型
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
    
    config = _config.load_config()
    config.llm_providers[provider] = llm_config
    config.llm_default_provider = provider
    _config.save_config()
    
    console.print(f"\n[green]✅ LLM 已配置: {provider}[/green]")
    console.print(f"   模型: {model}")
    console.print(f"   API Key: {api_key[:8]}...{api_key[-4:]}")
    if api_base:
        console.print(f"   地址: {api_base}")
    console.print()  
    # 撤销从环境变量读取 API Key 的修改，只从配置文件读取
# 需要把之前的修改改回 provider_config.api_key
# 找到所有之前修改过的地方，改回原来的样子
    if api_base:
        console.print(f"   地址: {api_base}")
    if api_key:
        console.print(f"   API Key: {'*' * 10} (已隐藏)")
    console.print()


@config_app.command("set-data-dir")
def config_set_data_dir(
    path: Path = typer.Argument(..., help="数据目录路径（如: ~/huaqi 或 /path/to/dir）"),
    migrate: bool = typer.Option(True, "--migrate/--no-migrate", help="是否迁移现有数据"),
):
    """配置数据存储地址（支持数据迁移）"""
    global _config, DATA_DIR, MEMORY_DIR
    
    ensure_initialized()
    
    path_str = str(path)
    home_str = str(Path.home())
    
    # 处理 ~ 展开
    if path_str.startswith("~"):
        path_str = path_str.replace("~", home_str, 1)
    
    # 检测并修复重复的家目录路径 (如 /Users/name/Users/name/...)
    # 这种情况发生在用户输入 ~/Users/name/... 时
    if home_str in path_str and path_str.count(home_str.split("/")[-1]) > 1:
        # 用户可能错误地输入了 ~/Users/name/... 
        # 尝试提取正确的相对路径
        parts = path_str.split(home_str + "/")
        if len(parts) > 1 and parts[1].startswith("Users/"):
            # 找到第二个家目录出现的位置
            second_home = path_str.find(home_str, len(home_str))
            if second_home > 0:
                path_str = path_str[second_home:]
    
    path = Path(path_str).resolve()
    path.mkdir(parents=True, exist_ok=True)
    
    old_data_dir = DATA_DIR
    
    # 如果启用了迁移且有旧数据
    if migrate and old_data_dir.exists() and old_data_dir != path:
        console.print(f"\n[yellow]🔄 正在迁移数据...[/yellow]")
        console.print(f"   从: {old_data_dir}")
        console.print(f"   到: {path}")
        
        import shutil
        
        # 需要迁移的目录
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
        
        # 迁移配置文件
        old_config = old_data_dir / "memory" / "config.yaml"
        new_config = path / "memory" / "config.yaml"
        if old_config.exists() and not new_config.exists():
            new_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_config, new_config)
            console.print(f"   ✅  config.yaml")
        
        console.print(f"\n[green]✅ 数据迁移完成 ({migrated_count} 个目录)[/green]")
    
    # 更新配置（先重新初始化_config，因为原来的可能指向旧路径）
    from huaqi_src.core.config_simple import ConfigManager
    _new_config = ConfigManager(path)
    _new_config.set("data_dir", str(path))
    
    DATA_DIR = path
    MEMORY_DIR = path / "memory"
    _config = _new_config
    
    # 设置新的数据目录到全局配置
    from huaqi_src.core.config_paths import set_data_dir
    set_data_dir(path)
    
    console.print(f"\n[green]✅ 数据目录已设置为: {path}[/green]")
    console.print(f"\n[dim]提示: 旧数据仍保留在 {old_data_dir}[/dim]\n")


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


# ============ 用户画像管理 ============

profile_app = typer.Typer(name="profile", help="用户画像管理")
app.add_typer(profile_app)


@profile_app.command("show")
def profile_show():
    """显示用户画像"""
    ensure_initialized()
    
    from huaqi_src.core.user_profile import get_profile_manager
    
    profile_manager = get_profile_manager()
    profile = profile_manager.profile
    
    console.print("\n[bold magenta]👤 用户画像[/bold magenta]\n")
    
    # 身份信息
    identity_table = Table(box=box.ROUNDED, title="身份信息")
    identity_table.add_column("项目", style="cyan")
    identity_table.add_column("值")
    
    identity = profile.identity
    identity_table.add_row("名字", identity.name or "未设置")
    identity_table.add_row("昵称", identity.nickname or "未设置")
    identity_table.add_row("职业", identity.occupation or "未设置")
    identity_table.add_row("公司", identity.company or "未设置")
    identity_table.add_row("所在地", identity.location or "未设置")
    identity_table.add_row("生日", identity.birth_date or "未设置")
    
    console.print(identity_table)
    console.print()
    
    # 背景信息
    background_table = Table(box=box.ROUNDED, title="背景信息")
    background_table.add_column("项目", style="cyan")
    background_table.add_column("内容")
    
    background = profile.background
    background_table.add_row("教育", background.education or "未设置")
    background_table.add_row("技能", ", ".join(background.skills) if background.skills else "未设置")
    background_table.add_row("爱好", ", ".join(background.hobbies) if background.hobbies else "未设置")
    background_table.add_row("目标", ", ".join(background.life_goals) if background.life_goals else "未设置")
    
    console.print(background_table)
    console.print()
    
    # 元数据
    console.print(f"[dim]最后更新: {profile.updated_at}[/dim]")
    console.print(f"[dim]版本: {profile.version}[/dim]\n")


@profile_app.command("set")
def profile_set(
    field: str = typer.Argument(..., help="字段名 (name/nickname/occupation/location/...)"),
    value: str = typer.Argument(..., help="字段值"),
):
    """设置用户画像字段"""
    ensure_initialized()
    
    from huaqi_src.core.user_profile import get_profile_manager
    
    profile_manager = get_profile_manager()
    
    # 身份字段
    identity_fields = ["name", "nickname", "birth_date", "location", "occupation", "company"]
    if field in identity_fields:
        profile_manager.update_identity(**{field: value})
        console.print(f"[green]✅ 已更新 {field} = {value}[/green]")
        return
    
    # 背景字段（列表类型）
    background_list_fields = ["skills", "hobbies", "life_goals", "values"]
    if field in background_list_fields:
        # 解析逗号分隔的值
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


@profile_app.command("forget")
def profile_forget(
    field: str = typer.Argument(..., help="要删除的字段名"),
):
    """删除用户画像字段"""
    ensure_initialized()
    
    from huaqi_src.core.user_profile import get_profile_manager
    
    profile_manager = get_profile_manager()
    profile = profile_manager.profile
    
    # 身份字段
    identity_fields = ["name", "nickname", "birth_date", "location", "occupation", "company"]
    if field in identity_fields:
        setattr(profile.identity, field, None)
        profile_manager.save()
        console.print(f"[green]✅ 已删除 {field}[/green]")
        return
    
    # 背景字段
    background_list_fields = ["skills", "hobbies", "life_goals", "values"]
    if field in background_list_fields:
        setattr(profile.background, field, [])
        profile_manager.save()
        console.print(f"[green]✅ 已清空 {field}[/green]")
        return
    
    console.print(f"[yellow]❌ 未知字段: {field}[/yellow]")


# ============ 主命令 ============

@app.command("chat")
def chat_command(
    use_langgraph: bool = typer.Option(True, "--langgraph/--legacy", help="使用 LangGraph Agent 模式"),
):
    """启动对话模式 (新版 LangGraph Agent)"""
    ensure_initialized()
    
    if use_langgraph:
        # LangGraph Agent 模式
        _run_langgraph_chat()
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
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", "-d", help="数据目录路径"),
):
    """Huaqi - 个人 AI 同伴系统"""
    from huaqi_src.core.config_paths import (
        set_data_dir, get_data_dir, is_data_dir_set, save_data_dir_to_config
    )
    
    # 如果命令行指定了数据目录，使用它并保存到配置
    if data_dir is not None:
        set_data_dir(data_dir)
        save_data_dir_to_config(data_dir)
    
    # 检查数据目录是否已配置（命令行参数、环境变量、或配置文件）
    if not is_data_dir_set():
        console.print("\n[bold red]❌ 错误: 未指定数据目录[/bold red]\n")
        console.print("请使用以下方式之一指定数据存储目录:\n")
        console.print("  [cyan]1. 命令行参数:[/cyan]")
        console.print("     huaqi --data-dir /path/to/data\n")
        console.print("  [cyan]2. 环境变量:[/cyan]")
        console.print("     export HUAQI_DATA_DIR=/path/to/data")
        console.print("     huaqi\n")
        console.print("  [cyan]3. 简写形式:[/cyan]")
        console.print("     huaqi -d /path/to/data\n")
        raise typer.Exit(1)
    
    # 更新全局数据目录
    global DATA_DIR, MEMORY_DIR, _config, _personality, _hooks, _growth, _git
    DATA_DIR = get_data_dir()
    MEMORY_DIR = DATA_DIR / "memory"
    
    # 如果没有子命令，进入对话模式
    if ctx.invoked_subcommand is None:
        chat_mode()


# ============ Pipeline 内容流水线 ============

pipeline_app = typer.Typer(name="pipeline", help="内容流水线 - X/RSS 采集 → 小红书发布")
app.add_typer(pipeline_app)


@pipeline_app.command("run")
def pipeline_run(
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="预览模式，不实际发布"),
    limit: int = typer.Option(5, "--limit", "-n", help="每个源采集数量"),
    source: str = typer.Option("all", "--source", "-s", help="数据源: x/rss/all"),
):
    """执行内容流水线"""
    ensure_initialized()
    
    import asyncio
    from huaqi_src.pipeline import create_default_pipeline
    
    console.print("\n[bold cyan]🚀 启动内容流水线[/bold cyan]\n")
    
    async def _run():
        pipeline = create_default_pipeline()
        
        # 根据 source 参数筛选
        if source != "all":
            from huaqi_src.pipeline.sources import XMockSource, RSSMockSource
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
    
    from huaqi_src.pipeline.platforms import XiaoHongShuPublisher
    
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
    
    # 如果没有指定 task_id，列出所有待审核任务
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
    
    # 获取指定任务的待审核内容
    task_data = manager.get_pending_task(task_id)
    
    if task_data is None:
        console.print(f"\n[red]未找到任务: {task_id}[/red]\n")
        return
    
    items = task_data.get("items", [])
    
    # 执行审核操作
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
    
    # 发布已审核内容
    if publish:
        import asyncio
        count = asyncio.run(manager.publish_approved(task_id))
        console.print(f"\n[green]✅ 已发布 {count} 条内容[/green]\n")
        return
    
    # 显示任务详情
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


# ============ Daemon 后台服务 ============

@app.command("daemon")
def daemon_command(
    action: str = typer.Argument(..., help="操作: start/stop/status/list"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="前台运行模式"),
):
    """管理后台定时任务服务"""
    ensure_initialized()
    
    from huaqi_src.scheduler import get_scheduler_manager, register_default_jobs, default_scheduler_config
    
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


# ============ Personality 人格画像更新 ============

personality_app = typer.Typer(name="personality", help="人格画像管理")
app.add_typer(personality_app)


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
    
    # 列出待审核提案
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
    
    # 获取指定提案
    proposal = updater.get_proposal(proposal_id)
    
    if proposal is None:
        console.print(f"\n[red]未找到提案: {proposal_id}[/red]\n")
        return
    
    # 批准提案
    if approve:
        if updater.approve_proposal(proposal_id, notes):
            console.print("\n[green]✅ 已批准并应用画像更新[/green]\n")
        else:
            console.print("\n[red]❌ 操作失败[/red]\n")
        return
    
    # 拒绝提案
    if reject:
        if updater.reject_proposal(proposal_id, notes):
            console.print("\n[red]❌ 已拒绝画像更新提案[/red]\n")
        else:
            console.print("\n[red]❌ 操作失败[/red]\n")
        return
    
    # 显示提案详情
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
    ensure_initialized()
    
    from huaqi_src.core.personality_simple import PersonalityEngine
    
    engine = PersonalityEngine(DATA_DIR / "memory")
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


# ============ System 系统管理 ============

system_app = typer.Typer(name="system", help="系统管理")
app.add_typer(system_app)


@system_app.command("migrate")
def system_migrate(
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="预览模式"),
    skip_backup: bool = typer.Option(False, "--skip-backup", help="跳过备份（不推荐）"),
):
    """执行数据迁移 v3 -> v4"""
    import subprocess
    import sys
    
    script_path = Path(__file__).parent / "scripts" / "migrate_v3_to_v4.py"
    
    if not script_path.exists():
        console.print("[red]迁移脚本不存在[/red]")
        return
    
    cmd = [sys.executable, str(script_path)]
    
    if dry_run:
        cmd.append("--dry-run")
    if skip_backup:
        cmd.append("--skip-backup")
    
    console.print("\n[bold cyan]🔄 执行数据迁移...[/bold cyan]\n")
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode == 0:
        console.print("\n[green]✅ 迁移完成[/green]\n")
    else:
        console.print("\n[red]❌ 迁移失败[/red]\n")


@system_app.command("hot-reload")
def system_hot_reload(
    action: str = typer.Argument("status", help="操作: start/stop/status"),
):
    """管理配置热重载"""
    ensure_initialized()
    
    from huaqi_src.core.config_hot_reload import get_hot_reload, init_hot_reload
    
    if action == "start":
        hot_reload = get_hot_reload()
        if hot_reload and hot_reload._running:
            console.print("[yellow]热重载已在运行中[/yellow]\n")
            return
        
        init_hot_reload(_config)
        console.print("[green]✅ 配置热重载已启动[/green]\n")
    
    elif action == "stop":
        hot_reload = get_hot_reload()
        if hot_reload:
            hot_reload.stop()
            console.print("[dim]热重载已停止[/dim]\n")
        else:
            console.print("[dim]热重载未运行[/dim]\n")
    
    elif action == "status":
        hot_reload = get_hot_reload()
        if hot_reload and hot_reload._running:
            console.print("[green]● 热重载运行中[/green]\n")
        else:
            console.print("[dim]○ 热重载未运行[/dim]\n")


@system_app.command("backup")
def system_backup():
    """创建数据备份"""
    from datetime import datetime
    import shutil
    
    backup_dir = DATA_DIR / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    memory_dir = DATA_DIR / "memory"
    
    if memory_dir.exists():
        shutil.copytree(memory_dir, backup_dir / "memory", dirs_exist_ok=True)
        console.print(f"\n[green]✅ 备份已创建: {backup_dir}[/green]\n")
    else:
        console.print("\n[yellow]无数据可备份[/yellow]\n")


if __name__ == "__main__":
    app()
