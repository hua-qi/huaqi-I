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
from pathlib import Path
from typing import List, Optional

from huaqi_src.config.manager import get_config_manager
from .document import HuaqiDocument
from .wechat_reader import WeChatDBReader
from .wechat_state import WeChatSyncState
from .wechat_writer import WeChatWriter


class WeChatWatcher:
    def __init__(
        self,
        db_dir: Path,
        data_dir: Path,
        state_file: Optional[Path] = None,
    ):
        self.db_dir = Path(db_dir)
        self.data_dir = Path(data_dir)
        if state_file is None:
            state_file = self.data_dir / "wechat_state.json"
        self.state = WeChatSyncState(state_file=state_file)
        self.writer = WeChatWriter(data_dir=self.data_dir)

    def is_enabled(self) -> bool:
        cfg = get_config_manager()
        return cfg.is_enabled("wechat")

    def sync_once(self) -> List[HuaqiDocument]:
        if not self.db_dir.exists():
            return []

        all_messages = []
        for db_path in sorted(self.db_dir.glob("*.db")):
            db_name = db_path.name
            last_rowid = self.state.get_last_rowid(db_name)
            reader = WeChatDBReader(db_path)
            messages = reader.read_since(last_rowid=last_rowid)
            if messages:
                max_rowid = max(m.rowid for m in messages)
                self.state.set_last_rowid(db_name, max_rowid)
                all_messages.extend(messages)

        if not all_messages:
            return []
        return self.writer.write(all_messages)
