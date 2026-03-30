"""CLI UI 工具

HuaqiCommandCompleter：命令自动补全
_prompt_input：多行输入支持
_clear_screen：清屏
"""

import re
import sys
from pathlib import Path
from typing import Dict, Optional

from prompt_toolkit import PromptSession, prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI

from rich.console import Console


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
        self._word_cache: Dict[str, int] = {}

    def _extract_words_from_history(self, history: FileHistory) -> None:
        if self._word_cache:
            return

        texts = []
        try:
            history_file = Path(history.filename)
            if history_file.exists():
                content = history_file.read_text(encoding='utf-8')
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

        word_pattern = re.compile(r'[\u4e00-\u9fa5]{2,6}')
        for text in texts:
            for i in range(len(text) - 1):
                for length in range(2, min(7, len(text) - i + 1)):
                    word = text[i:i + length]
                    if word_pattern.fullmatch(word):
                        self._word_cache[word] = self._word_cache.get(word, 0) + 1

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        if not text:
            return

        if text.startswith("/"):
            for cmd in self.COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))
            return

        if _input_history:
            self._extract_words_from_history(_input_history)

        words = text.split()
        if not words:
            return

        current_word = words[-1]
        if len(current_word) < 1:
            return

        sorted_words = sorted(
            self._word_cache.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for word, count in sorted_words:
            if word.startswith(current_word) and word != current_word:
                yield Completion(
                    word,
                    start_position=-len(current_word),
                    display=f"{word} ({count}次)"
                )


_input_history: Optional[FileHistory] = None
_command_completer = HuaqiCommandCompleter()


def get_input_history() -> Optional[FileHistory]:
    return _input_history


def prompt_input(
    history_file: Optional[Path] = None,
    placeholder: str = "今天有什么想聊的？",
    multiline: bool = True,
    turn_count: int = 0,
    left_pad: int = 0,
) -> str:
    """获取用户输入，支持中文、历史记录、自动补全和多行输入"""
    global _input_history

    if history_file is None:
        history_file = Path.home() / ".huaqi_history"

    history_file.parent.mkdir(parents=True, exist_ok=True)

    if _input_history is None:
        _input_history = FileHistory(str(history_file))

    bindings = KeyBindings()

    @bindings.add("c-c")
    def _(event):
        event.app.exit(result="")

    @bindings.add("c-l")
    def _(event):
        event.app.output.erase_screen()
        event.app.output.cursor_goto(0, 0)
        event.app.invalidate()

    @bindings.add("c-o")
    def _(event):
        event.current_buffer.insert_text("\n")

    @bindings.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    pad_str = " " * left_pad
    if turn_count > 0:
        prompt_message = ANSI(f"{pad_str}\x1b[35m🌸\x1b[0m \x1b[36mhuaqi\x1b[0m \x1b[2m[{turn_count}]\x1b[0m > ")
    else:
        prompt_message = ANSI(f"{pad_str}\x1b[35m🌸\x1b[0m \x1b[36mhuaqi\x1b[0m > ")

    try:
        result = prompt(
            prompt_message,
            history=_input_history,
            auto_suggest=AutoSuggestFromHistory(),
            completer=_command_completer,
            key_bindings=bindings,
            enable_suspend=True,
            multiline=False,
            complete_while_typing=True,
            wrap_lines=True,
        )

        if not result or not result.strip():
            return ""

        return result
    except (EOFError, KeyboardInterrupt):
        return ""


def clear_screen(console: Console):
    """清屏"""
    console.clear()
