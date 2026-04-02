import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from huaqi_src.layers.data.raw_signal.converters.base import BaseConverter
from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType


def _parse_frontmatter(text: str):
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not match:
        return {}, text.strip()
    fm_text, body = match.group(1), match.group(2).strip()
    fm: Dict[str, Any] = {}
    current_list_key = None
    for line in fm_text.splitlines():
        if line.startswith("  - ") and current_list_key:
            if not isinstance(fm[current_list_key], list):
                fm[current_list_key] = []
            fm[current_list_key].append(line.strip().lstrip("- "))
        elif ": " in line:
            key, _, val = line.partition(": ")
            fm[key.strip()] = val.strip()
            current_list_key = None
        elif line.endswith(":"):
            key = line.rstrip(":")
            fm[key] = []
            current_list_key = key
    return fm, body


class DiaryConverter(BaseConverter):

    def convert(self, source: Path) -> List[RawSignal]:
        text = source.read_text(encoding="utf-8").strip()
        if not text:
            return []

        fm, body = _parse_frontmatter(text)
        if not body:
            return []

        timestamp = datetime.now(timezone.utc)
        if "date" in fm:
            try:
                timestamp = datetime.strptime(str(fm["date"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        metadata: Dict[str, Any] = {}
        if "mood" in fm:
            metadata["mood"] = fm["mood"]
        if "tags" in fm:
            tags = fm["tags"]
            metadata["tags"] = tags if isinstance(tags, list) else [tags]

        return [
            RawSignal(
                user_id=self._user_id,
                source_type=SourceType.JOURNAL,
                timestamp=timestamp,
                content=body,
                metadata=metadata if metadata else None,
            )
        ]
