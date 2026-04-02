"""CLI UI 工具集

提供统一的界面组件、主题配置和交互模式
"""

import os
import random
from datetime import datetime
from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.layout import Layout
from rich.align import Align
from rich.markdown import Markdown
from rich import box


class HuaqiTheme:
    """Huaqi 主题配置"""
    
    # 主色调
    PRIMARY = "magenta"
    PRIMARY_BRIGHT = "bright_magenta"
    
    # 强调色
    SUCCESS = "green"
    SUCCESS_BRIGHT = "bright_green"
    WARNING = "yellow"
    WARNING_BRIGHT = "bright_yellow"
    ERROR = "red"
    ERROR_BRIGHT = "bright_red"
    INFO = "cyan"
    INFO_BRIGHT = "bright_cyan"
    
    # 中性色
    DIM = "dim"
    WHITE = "white"
    GREY = "grey70"
    
    # 表情符号
    EMOJI_BOT = "🌸"
    EMOJI_USER = "👤"
    EMOJI_SUCCESS = "✨"
    EMOJI_WARNING = "⚡"
    EMOJI_ERROR = "❌"
    EMOJI_INFO = "💡"
    EMOJI_THINKING = "🤔"
    EMOJI_HEART = "💖"
    EMOJI_STAR = "⭐"
    EMOJI_FIRE = "🔥"
    EMOJI_BOOK = "📚"
    EMOJI_TARGET = "🎯"
    EMOJI_ROCKET = "🚀"


class HuaqiUI:
    """Huaqi UI 组件库"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.theme = HuaqiTheme()
    
    # ============ 标题和头部 ============
    
    def show_welcome(self, version: str = "0.1.0"):
        """显示欢迎界面"""
        # 随机选择一条欢迎语
        greetings = [
            "不是使用 AI，而是养育 AI",
            "让每一次对话都留下痕迹",
            "你的成长，我都在见证",
            "今天想聊些什么？",
            "我在这里，随时可以开始",
        ]
        subtitle = random.choice(greetings)
        
        # 创建标题面板
        title = f"{self.theme.EMOJI_BOT} Huaqi [dim]v{version}[/dim]"
        
        content = Text()
        content.append(f"\n{subtitle}\n", style=f"italic {self.theme.DIM}")
        content.append("\n[dim]输入 /help 查看命令  •  exit 退出对话[/dim]")
        
        panel = Panel(
            Align.center(content),
            title=title,
            title_align="center",
            border_style=self.theme.PRIMARY,
            padding=(1, 4),
        )
        
        self.console.print()
        self.console.print(panel)
        self.console.print()
    
    def show_header(self, text: str, emoji: str = ""):
        """显示章节标题"""
        emoji_prefix = f"{emoji} " if emoji else ""
        self.console.print(f"\n[bold {self.theme.PRIMARY}]{emoji_prefix}{text}[/bold {self.theme.PRIMARY}]")
        self.console.print(f"[{self.theme.DIM}]" + "─" * 40 + f"[/{self.theme.DIM}]")
    
    # ============ 消息和对话 ============
    
    def bot_message(self, content: str, timestamp: Optional[str] = None):
        """显示 AI 消息"""
        time_str = timestamp or datetime.now().strftime("%H:%M")
        
        panel = Panel(
            content,
            title=f"[bold]{self.theme.EMOJI_BOT} Huaqi[/bold] [dim]{time_str}[/dim]",
            title_align="left",
            border_style=self.theme.PRIMARY,
            padding=(0, 1),
        )
        self.console.print(panel)
    
    def user_message(self, content: str, timestamp: Optional[str] = None):
        """显示用户消息"""
        time_str = timestamp or datetime.now().strftime("%H:%M")
        
        panel = Panel(
            f"[bold]{content}[/bold]",
            title=f"[bold]{self.theme.EMOJI_USER} 你[/bold] [dim]{time_str}[/dim]",
            title_align="left",
            border_style=self.theme.INFO,
            padding=(0, 1),
        )
        self.console.print(panel)
    
    def thinking_spinner(self, text: str = "正在思考..."):
        """返回思考中的 spinner"""
        return Panel(
            f"[{self.theme.DIM}]{self.theme.EMOJI_THINKING} {text}[/{self.theme.DIM}]",
            title=f"[bold]{self.theme.EMOJI_BOT} Huaqi[/bold]",
            title_align="left",
            border_style=f"{self.theme.PRIMARY} dim",
            padding=(0, 1),
        )
    
    # ============ 状态显示 ============
    
    def show_status_card(self, title: str, items: Dict[str, str], emoji: str = ""):
        """显示状态卡片"""
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column(style=f"{self.theme.INFO}", width=15)
        table.add_column()
        
        for key, value in items.items():
            table.add_row(key, value)
        
        panel = Panel(
            table,
            title=f"{emoji} {title}" if emoji else title,
            border_style=self.theme.INFO,
            padding=(0, 1),
        )
        self.console.print(panel)
    
    def show_progress_bar(self, label: str, current: int, total: int, width: int = 20):
        """显示进度条"""
        percentage = int(current / total * 100) if total > 0 else 0
        filled = int(current / total * width) if total > 0 else 0
        empty = width - filled
        
        bar = "█" * filled + "░" * empty
        return f"[{self.theme.SUCCESS}]{bar}[/{self.theme.SUCCESS}] {percentage}%"
    
    # ============ 列表和表格 ============
    
    def create_data_table(
        self,
        columns: List[tuple],  # [(name, style, width), ...]
        box_style = box.ROUNDED,
        title: Optional[str] = None,
    ) -> Table:
        """创建数据表格"""
        table = Table(box=box_style, title=title, title_style=f"bold {self.theme.PRIMARY}")
        
        for name, style, width in columns:
            table.add_column(name, style=style, width=width)
        
        return table
    
    def show_list(self, items: List[str], bullet: str = "•", style: str = ""):
        """显示列表"""
        style_prefix = f"[{style}]" if style else ""
        style_suffix = f"[/{style}]" if style else ""
        
        for item in items:
            self.console.print(f"  {style_prefix}{bullet} {item}{style_suffix}")
    
    # ============ 提示和反馈 ============
    
    def success(self, message: str):
        """显示成功消息"""
        self.console.print(f"[{self.theme.SUCCESS}]{self.theme.EMOJI_SUCCESS} {message}[/{self.theme.SUCCESS}]")
    
    def warning(self, message: str):
        """显示警告消息"""
        self.console.print(f"[{self.theme.WARNING}]{self.theme.EMOJI_WARNING} {message}[/{self.theme.WARNING}]")
    
    def error(self, message: str):
        """显示错误消息"""
        self.console.print(f"[{self.theme.ERROR}]{self.theme.EMOJI_ERROR} {message}[/{self.theme.ERROR}]")
    
    def info(self, message: str):
        """显示信息消息"""
        self.console.print(f"[{self.theme.INFO}]{self.theme.EMOJI_INFO} {message}[/{self.theme.INFO}]")
    
    def tip(self, message: str):
        """显示提示"""
        self.console.print(f"[dim]💭 {message}[/dim]")
    
    # ============ 菜单和帮助 ============
    
    def show_command_help(self, commands: Dict[str, str]):
        """显示命令帮助"""
        self.show_header("可用命令", self.theme.EMOJI_INFO)
        
        for cmd, desc in commands.items():
            self.console.print(f"  [bold cyan]{cmd:12}[/bold cyan]  {desc}")
        
        self.console.print()
    
    def show_menu(self, title: str, options: List[tuple]):
        """显示交互式菜单"""
        """
        options: [(key, label, description), ...]
        """
        self.show_header(title)
        
        for i, (key, label, desc) in enumerate(options, 1):
            self.console.print(f"  [bold]{i}.[/bold] [cyan]{label}[/cyan]")
            self.console.print(f"     [dim]{desc}[/dim]")
        
        self.console.print()
    
    # ============ 装饰性元素 ============
    
    def divider(self, char: str = "─", style: str = "dim"):
        """显示分隔线"""
        self.console.print(f"[{style}]{char * 50}[/{style}]")
    
    def blank_line(self, count: int = 1):
        """显示空行"""
        for _ in range(count):
            self.console.print()
    
    def show_quote(self, text: str, author: str = ""):
        """显示引用"""
        content = f"[italic]\"{text}\"[/italic]"
        if author:
            content += f"\n[dim]— {author}[/dim]"
        
        panel = Panel(
            content,
            border_style=self.theme.GREY,
            padding=(1, 2),
        )
        self.console.print(panel)


# 全局 UI 实例
_ui_instance: Optional[HuaqiUI] = None


def get_ui(console: Optional[Console] = None) -> HuaqiUI:
    """获取全局 UI 实例"""
    global _ui_instance
    if _ui_instance is None:
        _ui_instance = HuaqiUI(console)
    return _ui_instance


BUBBLE_MAX_WIDTH = 80


class BubbleLayout:
    """全左对齐布局 - 60% 终端宽度居中显示"""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.theme = HuaqiTheme()

    def _terminal_width(self) -> int:
        try:
            return os.get_terminal_size().columns
        except OSError:
            return 80

    def content_width(self) -> int:
        tw = self._terminal_width()
        return max(40, int(tw * 0.6))

    def left_pad(self) -> int:
        return 0

    def _pad(self) -> str:
        return ""

    def render_welcome(
        self,
        version: str = "",
        conversation_count: int = 0,
        last_chat: Optional[str] = None,
        has_report: bool = False,
    ):
        greetings = [
            "不是使用 AI，而是养育 AI",
            "让每一次对话都留下痕迹",
            "你的成长，我都在见证",
            "今天想聊些什么？",
            "我在这里，随时可以开始",
        ]
        subtitle = random.choice(greetings)
        cw = self.content_width()

        version_str = f"  ·  v{version}" if version else ""
        title_line = f"{self.theme.EMOJI_BOT} Huaqi{version_str}  ·  你的个人 AI 同伴"

        meta_parts = []
        now = datetime.now()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        meta_parts.append(f"今天是{weekdays[now.weekday()]}")
        if conversation_count > 0:
            meta_parts.append(f"共 {conversation_count} 次对话")
        if last_chat:
            meta_parts.append(f"上次{last_chat}")
        meta_line = "  ·  ".join(meta_parts)

        self.console.print()
        self.console.print(f"[bold magenta]{title_line}[/bold magenta]")
        self.console.print()
        if meta_line:
            self.console.print(f"[dim]{meta_line}[/dim]")
        self.console.print(f"[dim italic]「{subtitle}」[/dim italic]")
        self.console.print()
        if has_report:
            self.console.print(f"[dim]📊 本周报告就绪，/report 查看[/dim]")
            self.console.print()
        self.console.print(f"[dim]{'─' * cw}[/dim]")
        self.console.print()

    def render_ai_prefix(self, timestamp: Optional[str] = None):
        ts = timestamp or datetime.now().strftime("%H:%M")
        self.console.print(f"[bold magenta]{self.theme.EMOJI_BOT} 花期[/bold magenta]  [dim]{ts}[/dim]")

    def render_ai_thinking(self):
        self.console.print(f"[bold magenta]{self.theme.EMOJI_BOT} 花期[/bold magenta]  [dim]·  ·  ·[/dim]")

    def render_ai_message(self, content: str, timestamp: Optional[str] = None):
        self.render_ai_prefix(timestamp)
        lines = content.split("\n")
        for line in lines:
            self.console.print(f"[bright_yellow]{line}[/bright_yellow]")
        self.console.print()

    def render_user_message(self, content: str, timestamp: Optional[str] = None):
        pass
        self.console.print()

    def render_divider(self):
        cw = self.content_width()
        self.console.print(f"[dim]{'─' * cw}[/dim]")
        self.console.print()

    def render_care_message(self, content: str):
        self.console.print(f"[dim italic]{self.theme.EMOJI_BOT} {content}[/dim italic]")
        self.console.print()
