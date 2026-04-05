from pathlib import Path
from typing import Optional

from huaqi_src.layers.data.collectors.cli_chat_parser import CLIChatMessage


class WorkLogWriter:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from huaqi_src.config.paths import require_data_dir
            data_dir = require_data_dir()
        self._data_dir = Path(data_dir)

    def write(
        self,
        messages: list[CLIChatMessage],
        thread_id: str,
        time_start: str,
        time_end: str,
    ) -> Optional[Path]:
        if not messages:
            return None

        date_part = time_start[:10].replace("-", "")
        time_part = time_start[11:19].replace(":", "")
        month_key = time_start[:7]

        out_dir = self._data_dir / "work_logs" / month_key
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{date_part}_{time_part}_{thread_id}.md"
        out_file = out_dir / filename

        summary = self._build_summary(messages)
        frontmatter = (
            f"---\n"
            f"date: {time_start[:10]}\n"
            f"time_start: {time_start}\n"
            f"time_end: {time_end}\n"
            f"thread_id: {thread_id}\n"
            f"source: codeflicker\n"
            f"---\n"
        )
        out_file.write_text(frontmatter + "\n" + summary + "\n", encoding="utf-8")
        return out_file

    def _build_summary(self, messages: list[CLIChatMessage]) -> str:
        user_msgs = [m.content for m in messages if m.role == "user"]
        assistant_msgs = [m.content for m in messages if m.role == "assistant"]

        parts = []
        if user_msgs:
            parts.append(user_msgs[0][:100])
        if assistant_msgs:
            parts.append(assistant_msgs[-1][:100])

        return "。".join(parts) if parts else ""
