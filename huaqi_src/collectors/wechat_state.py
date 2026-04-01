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
import json
from pathlib import Path
from typing import Dict


class WeChatSyncState:
    def __init__(self, state_file: Path):
        self.state_file = Path(state_file)
        self._state: Dict[str, int] = self._load()

    def _load(self) -> Dict[str, int]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f)

    def get_last_rowid(self, db_name: str) -> int:
        return self._state.get(db_name, 0)

    def set_last_rowid(self, db_name: str, rowid: int) -> None:
        self._state[db_name] = rowid
        self._save()
