import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CLIChatMessage:
    role: str
    content: str
    timestamp: Optional[str] = None


@dataclass
class CLIChatSession:
    session_id: str
    messages: list[CLIChatMessage] = field(default_factory=list)
    git_branch: Optional[str] = None
    project_dir: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None


def parse_cli_chat_file(file_path: Path, tool_type: str) -> list[CLIChatMessage]:
    """兼容旧接口，返回消息列表。"""
    session = parse_cli_chat_session(file_path, tool_type)
    if session is None:
        return []
    return session.messages


def parse_cli_chat_session(file_path: Path, tool_type: str) -> Optional[CLIChatSession]:
    if tool_type == "codeflicker":
        suffix = file_path.suffix.lower()
        if suffix == ".jsonl":
            return _parse_codeflicker_jsonl(file_path)
        return _session_from_messages(file_path.stem, _parse_markdown(file_path))
    elif tool_type == "claude":
        return _session_from_messages(file_path.stem, _parse_json(file_path))
    return None


def _parse_codeflicker_jsonl(file_path: Path) -> Optional[CLIChatSession]:
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return None

    session_id = file_path.stem
    messages: list[CLIChatMessage] = []
    git_branch: Optional[str] = None
    project_dir: Optional[str] = str(file_path.parent)

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        sid = obj.get("sessionId")
        if sid:
            session_id = sid

        role = obj.get("role", "")
        if role not in ("user", "assistant"):
            continue

        if not git_branch:
            git_branch = obj.get("gitBranch")

        text_content = _extract_text_content(obj.get("content", ""))
        if not text_content:
            continue

        messages.append(CLIChatMessage(
            role=role,
            content=text_content,
            timestamp=obj.get("timestamp"),
        ))

    if not messages:
        return None

    timestamps = [m.timestamp for m in messages if m.timestamp]
    return CLIChatSession(
        session_id=session_id,
        messages=messages,
        git_branch=git_branch,
        project_dir=project_dir,
        time_start=timestamps[0] if timestamps else None,
        time_end=timestamps[-1] if timestamps else None,
    )


def _extract_text_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                parts.append(item.get("text", "").strip())
        return "\n".join(p for p in parts if p)
    return ""


def _session_from_messages(
    session_id: str, messages: list[CLIChatMessage]
) -> Optional[CLIChatSession]:
    if not messages:
        return None
    return CLIChatSession(session_id=session_id, messages=messages)


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
