import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from huaqi_src.layers.data.raw_signal.converters.base import BaseConverter
from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

_MSG_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.+?)\n([\s\S]+?)(?=\n\d{4}-\d{2}-\d{2}|\Z)"
)


class WechatConverter(BaseConverter):

    def __init__(
        self,
        user_id: str,
        participants: Optional[List[str]] = None,
        chat_name: str = "",
    ) -> None:
        super().__init__(user_id)
        self._participants = participants or []
        self._chat_name = chat_name

    def convert(self, source: Path) -> List[RawSignal]:
        text = source.read_text(encoding="utf-8")
        signals = []

        for m in _MSG_PATTERN.finditer(text):
            ts_str, sender, content = m.group(1), m.group(2).strip(), m.group(3).strip()
            if not content:
                continue

            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            metadata = {
                "participants": self._participants or [sender],
                "chat_name": self._chat_name,
                "sender": sender,
            }

            signals.append(
                RawSignal(
                    user_id=self._user_id,
                    source_type=SourceType.WECHAT,
                    timestamp=ts,
                    content=f"{sender}：{content}",
                    metadata=metadata,
                )
            )

        return signals
