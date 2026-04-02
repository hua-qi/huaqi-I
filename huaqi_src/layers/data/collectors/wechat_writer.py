# =============================================================================
# 封存声明 / ARCHIVED
#
# 微信采集相关代码已封存，不再提供任何对外入口（CLI 命令、Agent Tool、定时任务）。
# 原因：微信 4.x macOS 版本改用 SQLCipher 加密本地数据库，且 macOS SIP 保护
# 阻止对 /Applications 目录下二进制进行重签名，无法在不破坏系统安全策略的前提下
# 读取本地数据。
#
# 本文件仅作技术参考，非作者本人声明不得重新为 wechat 添加任何系统入口。
# =============================================================================
import uuid
import datetime
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Optional

from .document import HuaqiDocument
from .wechat_reader import WeChatMessage


class WeChatWriter:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._wechat_base = Path(data_dir) / "memory" / "wechat"
        else:
            from huaqi_src.config.paths import get_wechat_dir
            self._wechat_base = get_wechat_dir()

    def _wechat_dir(self, month_str: str) -> Path:
        return self._wechat_base / month_str

    def write(self, messages: List[WeChatMessage]) -> List[HuaqiDocument]:
        groups: Dict[tuple, List[WeChatMessage]] = defaultdict(list)
        for msg in messages:
            month_str = msg.timestamp.strftime("%Y-%m")
            groups[(msg.contact, month_str)].append(msg)

        docs: List[HuaqiDocument] = []
        for (contact, month_str), msgs in groups.items():
            out_dir = self._wechat_dir(month_str)
            out_dir.mkdir(parents=True, exist_ok=True)
            md_path = out_dir / f"{contact}.md"

            lines = []
            for m in sorted(msgs, key=lambda x: x.rowid):
                direction = "我" if m.is_self else contact
                ts = m.timestamp.strftime("%H:%M")
                lines.append(f"**{direction}** [{ts}]: {m.content}")

            block = "\n".join(lines)
            with open(md_path, "a", encoding="utf-8") as f:
                f.write(block + "\n")

            content = "\n".join(
                f"{'我' if m.is_self else contact} [{m.timestamp.strftime('%H:%M')}]: {m.content}"
                for m in sorted(msgs, key=lambda x: x.rowid)
            )
            docs.append(
                HuaqiDocument(
                    doc_id=str(uuid.uuid4()),
                    doc_type="wechat",
                    source=f"wechat:{contact}",
                    content=content,
                    timestamp=msgs[-1].timestamp,
                )
            )
        return docs
