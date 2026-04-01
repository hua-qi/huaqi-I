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
import sqlite3
import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class WeChatMessage:
    rowid: int
    contact: str
    timestamp: datetime.datetime
    content: str
    is_self: bool


class WeChatDBReader:
    TEXT_TYPE = 1

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _get_contact_tables(self, conn: sqlite3.Connection) -> List[str]:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Chat_%'"
        )
        return [row[0] for row in cursor.fetchall()]

    def read_since(self, last_rowid: int) -> List[WeChatMessage]:
        if not self.db_path.exists():
            return []
        try:
            conn = sqlite3.connect(str(self.db_path))
        except Exception:
            return []
        try:
            tables = self._get_contact_tables(conn)
            messages: List[WeChatMessage] = []
            for table in tables:
                contact = table[len("Chat_"):]
                try:
                    cursor = conn.execute(
                        f"SELECT id, CreateTime, Des, Message, Type FROM {table} "
                        f"WHERE id > ? AND Type = ? ORDER BY id ASC",
                        (last_rowid, self.TEXT_TYPE),
                    )
                    for row in cursor.fetchall():
                        rowid, create_time, des, message, msg_type = row
                        if not message:
                            continue
                        ts = datetime.datetime.fromtimestamp(create_time)
                        is_self = des == 0
                        messages.append(
                            WeChatMessage(
                                rowid=rowid,
                                contact=contact,
                                timestamp=ts,
                                content=message,
                                is_self=is_self,
                            )
                        )
                except Exception:
                    continue
            return messages
        finally:
            conn.close()
