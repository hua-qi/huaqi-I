import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CLIChatMessage:
    role: str
    content: str


def parse_cli_chat_file(file_path: Path, tool_type: str) -> list[CLIChatMessage]:
    if tool_type in ("codeflicker",):
        return _parse_markdown(file_path)
    elif tool_type in ("claude",):
        return _parse_json(file_path)
    return []


def _parse_markdown(file_path: Path) -> list[CLIChatMessage]:
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return []
    messages = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("**User:**"):
            content = line[len("**User:**"):].strip()
            if content:
                messages.append(CLIChatMessage(role="user", content=content))
        elif line.startswith("**Assistant:**"):
            content = line[len("**Assistant:**"):].strip()
            if content:
                messages.append(CLIChatMessage(role="assistant", content=content))
    return messages


def _parse_json(file_path: Path) -> list[CLIChatMessage]:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    raw_messages = data.get("messages", [])
    messages = []
    for m in raw_messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role and content:
            messages.append(CLIChatMessage(role=role, content=content))
    return messages
