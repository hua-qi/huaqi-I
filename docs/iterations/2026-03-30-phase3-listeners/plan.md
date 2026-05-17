# Phase 3 监听采集实施计划

**Goal:** 实现 WeChatWatcher（监听 macOS 微信本地 SQLite DB 增量采集）和 CLIChatWatcher（监听 codeflicker / Claude 对话目录增量采集），将聊天数据归一化为 HuaqiDocument 写入数据湖，并注册对应 Tool 供 Agent 使用。

**Architecture:** 两个 Watcher 均基于 `watchdog` 文件系统监听器：检测到目标文件变化后触发回调，WeChatWatcher 用 `sqlite3` 增量读取微信 DB，CLIChatWatcher 读取新增的 `.md`/`.json` 对话文件；归一化后写入 Markdown + SQLite 双写模式（与 InboxProcessor 一致）；新增 `search_wechat_tool` 和 `search_cli_chats_tool` 两个 LangChain Tool；两个 Watcher 均默认关闭，通过 `modules.wechat` / `modules.cli_chat` 配置项开启。

**Tech Stack:** Python `watchdog>=4.0.0`（已在 requirements.txt）, `sqlite3`（标准库）, `dataclasses`, `langchain_core.tools.tool`, `pytest` + `tmp_path`, `unittest.mock.patch`

---

## 前置阅读（必读，10 分钟）

在开始编码前，先浏览以下文件了解约定：

- `huaqi_src/collectors/document.py` — HuaqiDocument 数据模型，所有文档的归一化格式
- `huaqi_src/collectors/inbox_processor.py` — 现有 Collector 的实现模式（参考 `_process_file` + `sync`）
- `huaqi_src/world/base_source.py` — BaseWorldSource 基类（了解接口设计风格）
- `huaqi_src/agent/tools.py` — Tool 用 `@tool` 装饰器定义，直接看现有 6 个工具的模式
- `huaqi_src/agent/graph/chat.py` — Tool 如何注册进 LangGraph 图（搜索 `tools =` 列表）
- `huaqi_src/core/config_paths.py` — `get_data_dir()` / `require_data_dir()` 获取数据目录
- `huaqi_src/core/config_manager.py` — `ConfigManager.is_enabled(module_name)` 检查模块开关
- `tests/collectors/test_inbox_processor.py` — 测试中用 `tmp_path` 隔离文件系统的完整示例

运行测试：`pytest tests/ -v`
Lint 检查：`ruff check huaqi_src/ tests/`

---

## 背景知识：微信本地 DB 位置

macOS 上微信将聊天记录存储在：

```
~/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/
└── <hash>/
    └── Message/
        └── msg_<N>.db   ← 多个 SQLite 数据库文件
```

核心表结构（通过 `sqlite3` 查询）：
```sql
-- 每个 msg_N.db 内
SELECT name FROM sqlite_master WHERE type='table';
-- 常见表名：Chat_<contactHash>
-- 列：CreateTime (Unix 时间戳), Des (0=自己发/1=对方发), Message (消息内容), Type (1=文字)
```

**注意**：实际 DB 可能被加密（早期版本）或表结构随版本变化。本计划针对可读版本（近年 macOS 版本通常可读）。加密版本超出本计划范围，遇到时降级处理（跳过并记录日志）。

---

## 背景知识：CLIChatWatcher 目录格式

codeflicker 对话历史默认存储在 `~/.codeflicker/conversations/` 下，每个会话是一个 `.md` 文件：

```markdown
# 对话标题

**User:** 消息内容

**Assistant:** 回复内容
```

Claude CLI 存储在 `~/.claude/` 下，格式为 JSON 或 Markdown，具体格式见 Task 3 的解析逻辑。

---

## Task 1: 微信监听状态持久化

WeChatWatcher 需要记录「上次同步到哪条消息（rowid）」，否则每次重启都会重复导入。用一个简单的 JSON 文件存储每个 DB 文件的最后同步 rowid。

**Files:**
- Create: `huaqi_src/collectors/wechat_state.py`
- Create: `tests/collectors/test_wechat_state.py`

### Step 1: 写失败测试

创建 `tests/collectors/test_wechat_state.py`：

```python
import pytest
from pathlib import Path
from huaqi_src.collectors.wechat_state import WeChatSyncState


def test_get_last_rowid_returns_zero_for_unknown_db(tmp_path):
    state = WeChatSyncState(state_file=tmp_path / "wechat_state.json")
    assert state.get_last_rowid("msg_0.db") == 0


def test_set_and_get_last_rowid(tmp_path):
    state = WeChatSyncState(state_file=tmp_path / "wechat_state.json")
    state.set_last_rowid("msg_0.db", 42)
    assert state.get_last_rowid("msg_0.db") == 42


def test_state_persists_across_instances(tmp_path):
    state_file = tmp_path / "wechat_state.json"
    state1 = WeChatSyncState(state_file=state_file)
    state1.set_last_rowid("msg_1.db", 100)

    state2 = WeChatSyncState(state_file=state_file)
    assert state2.get_last_rowid("msg_1.db") == 100


def test_multiple_dbs_tracked_independently(tmp_path):
    state = WeChatSyncState(state_file=tmp_path / "wechat_state.json")
    state.set_last_rowid("msg_0.db", 10)
    state.set_last_rowid("msg_1.db", 99)
    assert state.get_last_rowid("msg_0.db") == 10
    assert state.get_last_rowid("msg_1.db") == 99
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/collectors/test_wechat_state.py -v
```

预期：`ImportError: cannot import name 'WeChatSyncState'`

### Step 3: 实现最小代码

创建 `huaqi_src/collectors/wechat_state.py`：

```python
import json
from pathlib import Path


class WeChatSyncState:
    def __init__(self, state_file: Path):
        self._file = state_file
        self._data: dict[str, int] = self._load()

    def _load(self) -> dict[str, int]:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self._file.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")

    def get_last_rowid(self, db_name: str) -> int:
        return self._data.get(db_name, 0)

    def set_last_rowid(self, db_name: str, rowid: int):
        self._data[db_name] = rowid
        self._save()
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/collectors/test_wechat_state.py -v
```

预期：4 个测试全部 PASS

### Step 5: Commit

```bash
git add huaqi_src/collectors/wechat_state.py tests/collectors/test_wechat_state.py
git commit -m "feat: add WeChatSyncState for incremental wechat DB sync"
```

---

## Task 2: 微信 DB 增量读取器

从微信 SQLite DB 文件中增量读取新消息，返回结构化消息列表。这部分单独拆出来便于测试（不依赖 watchdog）。

**Files:**
- Create: `huaqi_src/collectors/wechat_reader.py`
- Create: `tests/collectors/test_wechat_reader.py`

### Step 1: 写失败测试

创建 `tests/collectors/test_wechat_reader.py`：

```python
import sqlite3
import pytest
from pathlib import Path
from huaqi_src.collectors.wechat_reader import WeChatDBReader, WeChatMessage


def _make_fake_wechat_db(db_path: Path, contact: str = "张三"):
    conn = sqlite3.connect(str(db_path))
    table = f"Chat_{contact}"
    conn.execute(
        f"CREATE TABLE {table} "
        "(id INTEGER PRIMARY KEY, CreateTime INTEGER, Des INTEGER, Message TEXT, Type INTEGER)"
    )
    conn.execute(
        f"INSERT INTO {table} (CreateTime, Des, Message, Type) VALUES (1743300000, 0, '你好', 1)"
    )
    conn.execute(
        f"INSERT INTO {table} (CreateTime, Des, Message, Type) VALUES (1743300060, 1, '你也好', 1)"
    )
    conn.commit()
    conn.close()


def test_read_messages_from_db(tmp_path):
    db_path = tmp_path / "msg_0.db"
    _make_fake_wechat_db(db_path, contact="张三")
    reader = WeChatDBReader(db_path)
    messages = reader.read_since(last_rowid=0)
    assert len(messages) == 2
    assert messages[0].content == "你好"
    assert messages[0].is_self is True
    assert messages[1].content == "你也好"
    assert messages[1].is_self is False


def test_read_since_rowid_only_returns_new(tmp_path):
    db_path = tmp_path / "msg_0.db"
    _make_fake_wechat_db(db_path, contact="张三")
    reader = WeChatDBReader(db_path)
    messages = reader.read_since(last_rowid=1)
    assert len(messages) == 1
    assert messages[0].content == "你也好"


def test_read_returns_empty_when_db_unreadable(tmp_path):
    db_path = tmp_path / "nonexistent.db"
    reader = WeChatDBReader(db_path)
    messages = reader.read_since(last_rowid=0)
    assert messages == []


def test_read_skips_non_text_messages(tmp_path):
    db_path = tmp_path / "msg_0.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE Chat_Alice "
        "(id INTEGER PRIMARY KEY, CreateTime INTEGER, Des INTEGER, Message TEXT, Type INTEGER)"
    )
    conn.execute("INSERT INTO Chat_Alice VALUES (1, 1743300000, 0, '[图片]', 43)")
    conn.execute("INSERT INTO Chat_Alice VALUES (2, 1743300060, 0, '文字消息', 1)")
    conn.commit()
    conn.close()

    reader = WeChatDBReader(db_path)
    messages = reader.read_since(last_rowid=0)
    assert len(messages) == 1
    assert messages[0].content == "文字消息"
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/collectors/test_wechat_reader.py -v
```

预期：`ImportError: cannot import name 'WeChatDBReader'`

### Step 3: 实现最小代码

创建 `huaqi_src/collectors/wechat_reader.py`：

```python
import sqlite3
import datetime
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WeChatMessage:
    rowid: int
    contact: str
    timestamp: datetime.datetime
    content: str
    is_self: bool


class WeChatDBReader:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    def _get_chat_tables(self, conn: sqlite3.Connection) -> list[str]:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Chat_%'"
        )
        return [row[0] for row in cursor.fetchall()]

    def read_since(self, last_rowid: int) -> list[WeChatMessage]:
        if not self._db_path.exists():
            return []
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except Exception:
            return []
        try:
            tables = self._get_chat_tables(conn)
            messages = []
            for table in tables:
                contact = table[len("Chat_"):]
                try:
                    cursor = conn.execute(
                        f"SELECT id, CreateTime, Des, Message, Type FROM {table} "
                        f"WHERE id > ? AND Type = 1 ORDER BY id ASC",
                        (last_rowid,),
                    )
                    for row in cursor.fetchall():
                        rowid, create_time, des, message_text, _ = row
                        if not message_text:
                            continue
                        messages.append(
                            WeChatMessage(
                                rowid=rowid,
                                contact=contact,
                                timestamp=datetime.datetime.fromtimestamp(create_time),
                                content=message_text,
                                is_self=(des == 0),
                            )
                        )
                except Exception:
                    continue
            messages.sort(key=lambda m: m.timestamp)
            return messages
        finally:
            conn.close()
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/collectors/test_wechat_reader.py -v
```

预期：4 个测试全部 PASS

### Step 5: Commit

```bash
git add huaqi_src/collectors/wechat_reader.py tests/collectors/test_wechat_reader.py
git commit -m "feat: add WeChatDBReader for incremental wechat message reading"
```

---

## Task 3: 微信消息写入数据湖

将 WeChatMessage 列表归一化为 HuaqiDocument，按联系人分类写入 Markdown 文件（`data_dir/memory/wechat/YYYY-MM/联系人.md`）。

**Files:**
- Create: `huaqi_src/collectors/wechat_writer.py`
- Create: `tests/collectors/test_wechat_writer.py`

### Step 1: 写失败测试

创建 `tests/collectors/test_wechat_writer.py`：

```python
import datetime
import pytest
from pathlib import Path
from huaqi_src.collectors.wechat_reader import WeChatMessage
from huaqi_src.collectors.wechat_writer import WeChatWriter


def _make_messages(contact: str) -> list[WeChatMessage]:
    return [
        WeChatMessage(
            rowid=1,
            contact=contact,
            timestamp=datetime.datetime(2026, 3, 30, 10, 0, 0),
            content="你好，在吗？",
            is_self=True,
        ),
        WeChatMessage(
            rowid=2,
            contact=contact,
            timestamp=datetime.datetime(2026, 3, 30, 10, 1, 0),
            content="在的，有什么事？",
            is_self=False,
        ),
    ]


def test_write_creates_markdown_file(tmp_path):
    writer = WeChatWriter(data_dir=tmp_path)
    msgs = _make_messages("张三")
    docs = writer.write(msgs)
    assert len(docs) == 1
    md_file = tmp_path / "memory" / "wechat" / "2026-03" / "张三.md"
    assert md_file.exists()


def test_write_appends_to_existing_file(tmp_path):
    writer = WeChatWriter(data_dir=tmp_path)
    msgs1 = _make_messages("张三")
    writer.write(msgs1)

    msgs2 = [
        WeChatMessage(
            rowid=3,
            contact="张三",
            timestamp=datetime.datetime(2026, 3, 30, 11, 0, 0),
            content="再聊",
            is_self=True,
        )
    ]
    writer.write(msgs2)

    md_file = tmp_path / "memory" / "wechat" / "2026-03" / "张三.md"
    content = md_file.read_text(encoding="utf-8")
    assert "你好，在吗？" in content
    assert "再聊" in content


def test_write_returns_huaqi_documents(tmp_path):
    writer = WeChatWriter(data_dir=tmp_path)
    msgs = _make_messages("李四")
    docs = writer.write(msgs)
    assert docs[0].doc_type == "wechat"
    assert docs[0].source == "wechat:李四"
    assert "你好，在吗？" in docs[0].content


def test_write_groups_by_contact_and_month(tmp_path):
    writer = WeChatWriter(data_dir=tmp_path)
    msgs = [
        WeChatMessage(1, "张三", datetime.datetime(2026, 3, 1), "三月消息", True),
        WeChatMessage(2, "李四", datetime.datetime(2026, 3, 1), "李四消息", False),
    ]
    docs = writer.write(msgs)
    assert len(docs) == 2
    assert (tmp_path / "memory" / "wechat" / "2026-03" / "张三.md").exists()
    assert (tmp_path / "memory" / "wechat" / "2026-03" / "李四.md").exists()
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/collectors/test_wechat_writer.py -v
```

预期：`ImportError: cannot import name 'WeChatWriter'`

### Step 3: 实现最小代码

创建 `huaqi_src/collectors/wechat_writer.py`：

```python
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Optional

from huaqi_src.collectors.document import HuaqiDocument
from huaqi_src.collectors.wechat_reader import WeChatMessage


class WeChatWriter:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from huaqi_src.core.config_paths import require_data_dir
            data_dir = require_data_dir()
        self._data_dir = Path(data_dir)

    def write(self, messages: list[WeChatMessage]) -> list[HuaqiDocument]:
        grouped: dict[tuple[str, str], list[WeChatMessage]] = defaultdict(list)
        for msg in messages:
            month_key = msg.timestamp.strftime("%Y-%m")
            grouped[(msg.contact, month_key)].append(msg)

        docs = []
        for (contact, month_key), msgs in grouped.items():
            doc = self._write_group(contact, month_key, msgs)
            docs.append(doc)
        return docs

    def _write_group(self, contact: str, month_key: str, messages: list[WeChatMessage]) -> HuaqiDocument:
        dir_path = self._data_dir / "memory" / "wechat" / month_key
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{contact}.md"

        lines = []
        for msg in messages:
            speaker = "我" if msg.is_self else contact
            ts = msg.timestamp.strftime("%H:%M")
            lines.append(f"**{speaker}** ({ts}): {msg.content}")

        new_text = "\n".join(lines) + "\n"

        if file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
            file_path.write_text(existing + new_text, encoding="utf-8")
            full_content = existing + new_text
        else:
            header = f"# 与 {contact} 的微信对话 - {month_key}\n\n"
            full_content = header + new_text
            file_path.write_text(full_content, encoding="utf-8")

        doc_id = hashlib.md5(f"wechat:{contact}:{month_key}:{messages[-1].rowid}".encode()).hexdigest()[:12]
        return HuaqiDocument(
            doc_id=doc_id,
            doc_type="wechat",
            source=f"wechat:{contact}",
            content=new_text,
            timestamp=messages[-1].timestamp,
            metadata={"contact": contact, "month": month_key},
        )
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/collectors/test_wechat_writer.py -v
```

预期：4 个测试全部 PASS

### Step 5: Commit

```bash
git add huaqi_src/collectors/wechat_writer.py tests/collectors/test_wechat_writer.py
git commit -m "feat: add WeChatWriter to persist wechat messages to data lake"
```

---

## Task 4: WeChatWatcher（watchdog 监听器）

用 `watchdog` 监听微信 DB 目录变化，变化时触发增量读取 + 写入数据湖。默认关闭，需配置 `modules.wechat: true` 开启。

**Files:**
- Create: `huaqi_src/collectors/wechat_watcher.py`
- Create: `tests/collectors/test_wechat_watcher.py`

### Step 1: 写失败测试

创建 `tests/collectors/test_wechat_watcher.py`：

```python
import sqlite3
import datetime
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from huaqi_src.collectors.wechat_watcher import WeChatWatcher, find_wechat_db_dir


def _make_wechat_db(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE Chat_张三 "
        "(id INTEGER PRIMARY KEY, CreateTime INTEGER, Des INTEGER, Message TEXT, Type INTEGER)"
    )
    conn.execute("INSERT INTO Chat_张三 VALUES (1, 1743300000, 1, '新消息', 1)")
    conn.commit()
    conn.close()


def test_sync_once_reads_new_messages(tmp_path):
    db_dir = tmp_path / "wechat_db"
    db_dir.mkdir()
    db_path = db_dir / "msg_0.db"
    _make_wechat_db(db_path)

    state_file = tmp_path / "wechat_state.json"
    watcher = WeChatWatcher(
        db_dir=db_dir,
        data_dir=tmp_path,
        state_file=state_file,
    )
    docs = watcher.sync_once()
    assert len(docs) == 1
    assert docs[0].doc_type == "wechat"


def test_sync_once_is_incremental(tmp_path):
    db_dir = tmp_path / "wechat_db"
    db_dir.mkdir()
    db_path = db_dir / "msg_0.db"
    _make_wechat_db(db_path)

    state_file = tmp_path / "wechat_state.json"
    watcher = WeChatWatcher(db_dir=db_dir, data_dir=tmp_path, state_file=state_file)
    watcher.sync_once()

    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO Chat_张三 VALUES (2, 1743300060, 0, '回复', 1)")
    conn.commit()
    conn.close()

    docs2 = watcher.sync_once()
    assert len(docs2) == 1
    assert "回复" in docs2[0].content


def test_sync_once_returns_empty_when_no_new_messages(tmp_path):
    db_dir = tmp_path / "wechat_db"
    db_dir.mkdir()
    db_path = db_dir / "msg_0.db"
    _make_wechat_db(db_path)

    state_file = tmp_path / "wechat_state.json"
    watcher = WeChatWatcher(db_dir=db_dir, data_dir=tmp_path, state_file=state_file)
    watcher.sync_once()
    docs2 = watcher.sync_once()
    assert docs2 == []


def test_watcher_disabled_when_module_off(tmp_path):
    db_dir = tmp_path / "wechat_db"
    db_dir.mkdir()

    with patch("huaqi_src.collectors.wechat_watcher.ConfigManager") as mock_cm:
        mock_cm.return_value.is_enabled.return_value = False
        watcher = WeChatWatcher(db_dir=db_dir, data_dir=tmp_path)
        assert not watcher.is_enabled()
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/collectors/test_wechat_watcher.py -v
```

预期：`ImportError: cannot import name 'WeChatWatcher'`

### Step 3: 实现最小代码

创建 `huaqi_src/collectors/wechat_watcher.py`：

```python
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from huaqi_src.collectors.document import HuaqiDocument
from huaqi_src.collectors.wechat_reader import WeChatDBReader
from huaqi_src.collectors.wechat_state import WeChatSyncState
from huaqi_src.collectors.wechat_writer import WeChatWriter
from huaqi_src.core.config_manager import ConfigManager


def find_wechat_db_dir() -> Optional[Path]:
    base = Path.home() / "Library" / "Containers" / "com.tencent.xinWeChat" / \
           "Data" / "Library" / "Application Support" / "com.tencent.xinWeChat"
    if not base.exists():
        return None
    for version_dir in sorted(base.iterdir()):
        for hash_dir in version_dir.iterdir():
            msg_dir = hash_dir / "Message"
            if msg_dir.exists() and any(msg_dir.glob("msg_*.db")):
                return msg_dir
    return None


class WeChatWatcher:
    def __init__(
        self,
        db_dir: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        state_file: Optional[Path] = None,
    ):
        if db_dir is None:
            db_dir = find_wechat_db_dir()
        self._db_dir = db_dir

        if data_dir is None:
            from huaqi_src.core.config_paths import require_data_dir
            data_dir = require_data_dir()
        self._data_dir = Path(data_dir)

        if state_file is None:
            state_file = self._data_dir / "wechat_sync_state.json"
        self._state = WeChatSyncState(state_file=state_file)
        self._writer = WeChatWriter(data_dir=self._data_dir)
        self._observer: Optional[Observer] = None
        self._config = ConfigManager()

    def is_enabled(self) -> bool:
        return self._config.is_enabled("wechat")

    def sync_once(self) -> list[HuaqiDocument]:
        if self._db_dir is None or not self._db_dir.exists():
            return []
        all_docs = []
        for db_path in sorted(self._db_dir.glob("msg_*.db")):
            db_name = db_path.name
            last_rowid = self._state.get_last_rowid(db_name)
            reader = WeChatDBReader(db_path)
            messages = reader.read_since(last_rowid=last_rowid)
            if not messages:
                continue
            docs = self._writer.write(messages)
            all_docs.extend(docs)
            max_rowid = max(m.rowid for m in messages)
            self._state.set_last_rowid(db_name, max_rowid)
        return all_docs

    def start(self):
        if not self.is_enabled() or self._db_dir is None:
            return
        self.sync_once()

        handler = _DBChangeHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._db_dir), recursive=False)
        self._observer.start()
        print(f"[WeChatWatcher] 开始监听: {self._db_dir}")

    def stop(self):
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()
            print("[WeChatWatcher] 已停止监听")


class _DBChangeHandler(FileSystemEventHandler):
    def __init__(self, watcher: WeChatWatcher):
        self._watcher = watcher

    def on_modified(self, event: FileModifiedEvent):
        if not event.is_directory and event.src_path.endswith(".db"):
            self._watcher.sync_once()
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/collectors/test_wechat_watcher.py -v
```

预期：4 个测试全部 PASS

### Step 5: Commit

```bash
git add huaqi_src/collectors/wechat_watcher.py tests/collectors/test_wechat_watcher.py
git commit -m "feat: add WeChatWatcher with watchdog-based incremental sync"
```

---

## Task 5: CLI 对话文件解析器

CLIChatWatcher 需要解析 codeflicker（Markdown 格式）和 Claude（JSON 格式）的对话文件，统一提取出「时间戳 + 消息列表」。

**Files:**
- Create: `huaqi_src/collectors/cli_chat_parser.py`
- Create: `tests/collectors/test_cli_chat_parser.py`

### Step 1: 写失败测试

创建 `tests/collectors/test_cli_chat_parser.py`：

```python
import json
import pytest
from pathlib import Path
from huaqi_src.collectors.cli_chat_parser import parse_cli_chat_file, CLIChatMessage


def test_parse_codeflicker_markdown(tmp_path):
    md_file = tmp_path / "session.md"
    md_file.write_text(
        "# 关于 Python 的讨论\n\n"
        "**User:** 如何使用 watchdog？\n\n"
        "**Assistant:** watchdog 是一个文件系统监听库。\n",
        encoding="utf-8",
    )
    messages = parse_cli_chat_file(md_file, tool_type="codeflicker")
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert "watchdog" in messages[0].content
    assert messages[1].role == "assistant"


def test_parse_claude_json(tmp_path):
    json_file = tmp_path / "session.json"
    data = {
        "messages": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮你的？"},
        ]
    }
    json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    messages = parse_cli_chat_file(json_file, tool_type="claude")
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "你好"


def test_parse_unknown_format_returns_empty(tmp_path):
    f = tmp_path / "session.xyz"
    f.write_text("some content")
    messages = parse_cli_chat_file(f, tool_type="custom")
    assert messages == []


def test_parse_markdown_skips_header_line(tmp_path):
    md_file = tmp_path / "session.md"
    md_file.write_text(
        "# 标题行应被跳过\n\n**User:** 问题\n\n**Assistant:** 答案\n",
        encoding="utf-8",
    )
    messages = parse_cli_chat_file(md_file, tool_type="codeflicker")
    assert len(messages) == 2
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/collectors/test_cli_chat_parser.py -v
```

预期：`ImportError: cannot import name 'parse_cli_chat_file'`

### Step 3: 实现最小代码

创建 `huaqi_src/collectors/cli_chat_parser.py`：

```python
import json
import re
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
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/collectors/test_cli_chat_parser.py -v
```

预期：4 个测试全部 PASS

### Step 5: Commit

```bash
git add huaqi_src/collectors/cli_chat_parser.py tests/collectors/test_cli_chat_parser.py
git commit -m "feat: add CLIChatParser for codeflicker/claude conversation files"
```

---

## Task 6: CLIChatWatcher

监听用户配置的 CLI 工具对话目录，发现新文件或文件修改时解析并写入数据湖（`data_dir/memory/cli_chats/YYYY-MM/工具名-文件名.md`）。

**Files:**
- Create: `huaqi_src/collectors/cli_chat_watcher.py`
- Create: `tests/collectors/test_cli_chat_watcher.py`

### Step 1: 写失败测试

创建 `tests/collectors/test_cli_chat_watcher.py`：

```python
import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.collectors.cli_chat_watcher import CLIChatWatcher


def _make_md_session(path: Path, content: str = "**User:** 问题\n\n**Assistant:** 答案\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_process_file_creates_markdown_doc(tmp_path):
    conv_dir = tmp_path / "conversations"
    md_file = conv_dir / "session_001.md"
    _make_md_session(md_file)

    watch_paths = [{"type": "codeflicker", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    docs = watcher.process_file(md_file, tool_type="codeflicker")

    assert len(docs) == 1
    assert docs[0].doc_type == "cli_chat"
    assert docs[0].source.startswith("cli_chat:codeflicker:")


def test_process_file_writes_to_memory_dir(tmp_path):
    conv_dir = tmp_path / "conversations"
    md_file = conv_dir / "session_001.md"
    _make_md_session(md_file)

    watch_paths = [{"type": "codeflicker", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    watcher.process_file(md_file, tool_type="codeflicker")

    cli_chats_dir = tmp_path / "memory" / "cli_chats"
    md_files = list(cli_chats_dir.rglob("*.md"))
    assert len(md_files) == 1


def test_process_file_with_empty_messages_returns_empty(tmp_path):
    conv_dir = tmp_path / "conversations"
    md_file = conv_dir / "empty.md"
    _make_md_session(md_file, content="# 空文件\n\n没有对话内容\n")

    watch_paths = [{"type": "codeflicker", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    docs = watcher.process_file(md_file, tool_type="codeflicker")
    assert docs == []


def test_sync_all_processes_existing_files(tmp_path):
    conv_dir = tmp_path / "conversations"
    for i in range(3):
        _make_md_session(conv_dir / f"session_{i:03d}.md")

    watch_paths = [{"type": "codeflicker", "path": str(conv_dir)}]
    watcher = CLIChatWatcher(watch_paths=watch_paths, data_dir=tmp_path)
    docs = watcher.sync_all()
    assert len(docs) == 3
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/collectors/test_cli_chat_watcher.py -v
```

预期：`ImportError: cannot import name 'CLIChatWatcher'`

### Step 3: 实现最小代码

创建 `huaqi_src/collectors/cli_chat_watcher.py`：

```python
import datetime
import hashlib
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from huaqi_src.collectors.cli_chat_parser import parse_cli_chat_file
from huaqi_src.collectors.document import HuaqiDocument
from huaqi_src.core.config_manager import ConfigManager


class CLIChatWatcher:
    def __init__(
        self,
        watch_paths: Optional[list[dict]] = None,
        data_dir: Optional[Path] = None,
    ):
        if data_dir is None:
            from huaqi_src.core.config_paths import require_data_dir
            data_dir = require_data_dir()
        self._data_dir = Path(data_dir)
        self._watch_paths = watch_paths or self._load_watch_paths_from_config()
        self._observer: Optional[Observer] = None
        self._config = ConfigManager()

    def _load_watch_paths_from_config(self) -> list[dict]:
        return []

    def is_enabled(self) -> bool:
        return self._config.is_enabled("cli_chat")

    def process_file(self, file_path: Path, tool_type: str) -> list[HuaqiDocument]:
        messages = parse_cli_chat_file(file_path, tool_type=tool_type)
        if not messages:
            return []

        content_lines = [
            f"[{m.role}]: {m.content}" for m in messages
        ]
        content = "\n".join(content_lines)

        now = datetime.datetime.now()
        month_key = now.strftime("%Y-%m")
        out_dir = self._data_dir / "memory" / "cli_chats" / month_key
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / f"{tool_type}-{file_path.stem}.md"
        header = f"# {tool_type} 对话记录: {file_path.name}\n\n"
        out_file.write_text(header + content + "\n", encoding="utf-8")

        doc_id = hashlib.md5(f"cli_chat:{tool_type}:{file_path.name}:{len(messages)}".encode()).hexdigest()[:12]
        return [
            HuaqiDocument(
                doc_id=doc_id,
                doc_type="cli_chat",
                source=f"cli_chat:{tool_type}:{file_path.name}",
                content=content,
                timestamp=now,
                metadata={"tool_type": tool_type, "file": str(file_path)},
            )
        ]

    def sync_all(self) -> list[HuaqiDocument]:
        all_docs = []
        for watch_cfg in self._watch_paths:
            tool_type = watch_cfg.get("type", "custom")
            path = Path(watch_cfg.get("path", "")).expanduser()
            if not path.exists():
                continue
            for f in sorted(path.rglob("*.md")) + sorted(path.rglob("*.json")):
                docs = self.process_file(f, tool_type=tool_type)
                all_docs.extend(docs)
        return all_docs

    def start(self):
        if not self.is_enabled():
            return
        self.sync_all()
        self._observer = Observer()
        for watch_cfg in self._watch_paths:
            tool_type = watch_cfg.get("type", "custom")
            path = Path(watch_cfg.get("path", "")).expanduser()
            if not path.exists():
                continue
            handler = _FileChangeHandler(self, tool_type=tool_type)
            self._observer.schedule(handler, str(path), recursive=True)
        self._observer.start()

    def stop(self):
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()


class _FileChangeHandler(FileSystemEventHandler):
    def __init__(self, watcher: CLIChatWatcher, tool_type: str):
        self._watcher = watcher
        self._tool_type = tool_type

    def on_created(self, event: FileCreatedEvent):
        if not event.is_directory:
            self._watcher.process_file(Path(event.src_path), self._tool_type)

    def on_modified(self, event: FileModifiedEvent):
        if not event.is_directory:
            self._watcher.process_file(Path(event.src_path), self._tool_type)
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/collectors/test_cli_chat_watcher.py -v
```

预期：4 个测试全部 PASS

### Step 5: Commit

```bash
git add huaqi_src/collectors/cli_chat_watcher.py tests/collectors/test_cli_chat_watcher.py
git commit -m "feat: add CLIChatWatcher for codeflicker/claude chat history collection"
```

---

## Task 7: 新增 Agent Tools

为微信记录和 CLI 对话各增加一个 LangChain Tool，注册进 LangGraph Agent，使 Agent 能按需检索这两类数据。

**Files:**
- Modify: `huaqi_src/agent/tools.py`
- Modify: `huaqi_src/agent/graph/chat.py`（搜索 `tools =` 列表，添加两个新 Tool）
- Modify: `tests/agent/test_tools.py`

### Step 1: 写失败测试

在 `tests/agent/test_tools.py` 末尾追加：

```python
def test_search_wechat_tool_returns_string_when_no_data(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.agent.tools import search_wechat_tool
    result = search_wechat_tool.invoke({"query": "测试消息"})
    assert isinstance(result, str)


def test_search_cli_chats_tool_returns_string_when_no_data(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.agent.tools import search_cli_chats_tool
    result = search_cli_chats_tool.invoke({"query": "watchdog"})
    assert isinstance(result, str)
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/agent/test_tools.py -v -k "wechat or cli_chats"
```

预期：`ImportError: cannot import name 'search_wechat_tool'`

### Step 3: 在 tools.py 末尾追加两个新 Tool

在 `huaqi_src/agent/tools.py` 末尾添加：

```python
@tool
def search_wechat_tool(query: str) -> str:
    """搜索用户的微信聊天记录。当用户询问和某人的微信对话、特定聊天内容时使用。"""
    from pathlib import Path
    from huaqi_src.core.config_paths import get_data_dir

    data_dir = get_data_dir()
    if data_dir is None:
        return f"未找到包含 '{query}' 的微信记录（数据目录未设置）。"

    wechat_dir = Path(data_dir) / "memory" / "wechat"
    if not wechat_dir.exists():
        return f"未找到包含 '{query}' 的微信记录。"

    results = []
    query_lower = query.lower()
    for md_file in sorted(wechat_dir.rglob("*.md"), reverse=True)[:30]:
        try:
            content = md_file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                results.append(f"文件: {md_file.parent.name}/{md_file.name}\n摘要: {content[:300]}")
        except Exception:
            continue

    if not results:
        return f"未找到包含 '{query}' 的微信记录。"
    return "找到以下微信记录：\n\n" + "\n---\n".join(results[:3])


@tool
def search_cli_chats_tool(query: str) -> str:
    """搜索用户与其他 CLI Agent（如 codeflicker、Claude）的对话记录。当用户询问曾经的编程问题、讨论过的技术方案时使用。"""
    from pathlib import Path
    from huaqi_src.core.config_paths import get_data_dir

    data_dir = get_data_dir()
    if data_dir is None:
        return f"未找到包含 '{query}' 的 CLI 对话记录（数据目录未设置）。"

    cli_chats_dir = Path(data_dir) / "memory" / "cli_chats"
    if not cli_chats_dir.exists():
        return f"未找到包含 '{query}' 的 CLI 对话记录。"

    results = []
    query_lower = query.lower()
    for md_file in sorted(cli_chats_dir.rglob("*.md"), reverse=True)[:30]:
        try:
            content = md_file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                results.append(f"文件: {md_file.parent.name}/{md_file.name}\n摘要: {content[:300]}")
        except Exception:
            continue

    if not results:
        return f"未找到包含 '{query}' 的 CLI 对话记录。"
    return "找到以下 CLI 对话记录：\n\n" + "\n---\n".join(results[:3])
```

### Step 4: 将新 Tool 注册进 LangGraph 图

打开 `huaqi_src/agent/graph/chat.py`，找到 `tools =` 列表，加入两个新工具：

```python
# 找到现有的 tools 列表，例如：
from huaqi_src.agent.tools import (
    search_diary_tool,
    search_work_docs_tool,
    search_events_tool,
    search_worldnews_tool,
    search_person_tool,
    get_relationship_map_tool,
    search_wechat_tool,       # 新增
    search_cli_chats_tool,    # 新增
)

tools = [
    search_diary_tool,
    search_work_docs_tool,
    search_events_tool,
    search_worldnews_tool,
    search_person_tool,
    get_relationship_map_tool,
    search_wechat_tool,       # 新增
    search_cli_chats_tool,    # 新增
]
```

### Step 5: 运行测试，确认通过

```bash
pytest tests/agent/test_tools.py -v
```

预期：所有测试 PASS（包括两个新测试）

### Step 6: Commit

```bash
git add huaqi_src/agent/tools.py huaqi_src/agent/graph/chat.py tests/agent/test_tools.py
git commit -m "feat: add search_wechat_tool and search_cli_chats_tool to agent"
```

---

## Task 8: CLI 命令 `huaqi collector`

为用户提供手动触发和状态查看的 CLI 入口。`huaqi collector status` 显示监听状态，`huaqi collector sync-wechat` 手动触发一次微信增量同步，`huaqi collector sync-cli` 手动触发一次 CLI 对话同步。

**Files:**
- Create: `huaqi_src/cli/commands/collector.py`
- Modify: `huaqi_src/cli/__init__.py`（挂载新子命令）
- Create: `tests/cli/test_collector_cli.py`

### Step 1: 写失败测试

创建 `tests/cli/test_collector_cli.py`：

```python
import os
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

runner = CliRunner()


def _get_app():
    from huaqi_src.cli.__init__ import app
    return app


def test_collector_status_exits_ok(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    app = _get_app()
    result = runner.invoke(app, ["collector", "status"])
    assert result.exit_code == 0


def test_collector_sync_wechat_calls_watcher(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    app = _get_app()
    with patch("huaqi_src.cli.commands.collector.WeChatWatcher") as mock_cls:
        mock_watcher = MagicMock()
        mock_watcher.sync_once.return_value = []
        mock_cls.return_value = mock_watcher
        result = runner.invoke(app, ["collector", "sync-wechat"])
    assert result.exit_code == 0


def test_collector_sync_cli_calls_watcher(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    app = _get_app()
    with patch("huaqi_src.cli.commands.collector.CLIChatWatcher") as mock_cls:
        mock_watcher = MagicMock()
        mock_watcher.sync_all.return_value = []
        mock_cls.return_value = mock_watcher
        result = runner.invoke(app, ["collector", "sync-cli"])
    assert result.exit_code == 0
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/cli/test_collector_cli.py -v
```

预期：`collector` 子命令不存在，`exit_code != 0`

### Step 3: 创建命令模块

创建 `huaqi_src/cli/commands/collector.py`：

```python
import typer
from pathlib import Path

app = typer.Typer(name="collector", help="数据采集器管理")


@app.command("status")
def status():
    """查看数据采集器状态"""
    from huaqi_src.core.config_manager import ConfigManager
    from huaqi_src.core.config_paths import get_data_dir

    cfg = ConfigManager()
    wechat_enabled = cfg.is_enabled("wechat")
    cli_chat_enabled = cfg.is_enabled("cli_chat")

    data_dir = get_data_dir()
    typer.echo(f"数据目录: {data_dir or '未设置'}")
    typer.echo(f"微信监听 (modules.wechat):    {'✓ 已开启' if wechat_enabled else '✗ 已关闭'}")
    typer.echo(f"CLI 对话监听 (modules.cli_chat): {'✓ 已开启' if cli_chat_enabled else '✗ 已关闭'}")


@app.command("sync-wechat")
def sync_wechat():
    """手动触发一次微信增量同步"""
    from huaqi_src.collectors.wechat_watcher import WeChatWatcher

    typer.echo("正在同步微信记录...")
    watcher = WeChatWatcher()
    docs = watcher.sync_once()
    if not docs:
        typer.echo("没有新的微信消息。")
    else:
        typer.echo(f"已同步 {len(docs)} 批次消息记录。")


@app.command("sync-cli")
def sync_cli():
    """手动触发一次 CLI 对话历史同步"""
    from huaqi_src.collectors.cli_chat_watcher import CLIChatWatcher

    typer.echo("正在同步 CLI 对话记录...")
    watcher = CLIChatWatcher()
    docs = watcher.sync_all()
    if not docs:
        typer.echo("没有新的 CLI 对话记录。")
    else:
        typer.echo(f"已同步 {len(docs)} 个对话文件。")
```

### Step 4: 将命令挂载到主 CLI

打开 `huaqi_src/cli/__init__.py`，找到其他 `app.add_typer(...)` 的地方，添加一行：

```python
from huaqi_src.cli.commands.collector import app as collector_app
app.add_typer(collector_app)
```

### Step 5: 运行测试，确认通过

```bash
pytest tests/cli/test_collector_cli.py -v
```

预期：3 个测试全部 PASS

### Step 6: Commit

```bash
git add huaqi_src/cli/commands/collector.py huaqi_src/cli/__init__.py tests/cli/test_collector_cli.py
git commit -m "feat: add collector CLI commands (status/sync-wechat/sync-cli)"
```

---

## Task 9: 在调度器中启动 Watcher

在 `huaqi_src/scheduler/jobs.py` 中注册一个「每 5 分钟触发一次微信增量同步」的后台任务，同时在调度器启动时检查是否开启了 Watcher，如果开启则启动 watchdog 监听。

**Files:**
- Modify: `huaqi_src/scheduler/jobs.py`
- Modify: `tests/scheduler/test_jobs.py`

### Step 1: 写失败测试

打开 `tests/scheduler/test_jobs.py`，追加：

```python
def test_register_default_jobs_includes_wechat_sync():
    from unittest.mock import MagicMock, patch
    from huaqi_src.scheduler.jobs import register_default_jobs

    mock_manager = MagicMock()
    with patch("huaqi_src.scheduler.jobs.ConfigManager") as mock_cm:
        mock_cm.return_value.is_enabled.return_value = True
        register_default_jobs(mock_manager)

    job_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "wechat_sync" in job_ids
```

### Step 2: 运行测试，确认失败

```bash
pytest tests/scheduler/test_jobs.py -v -k "wechat"
```

预期：FAIL，`wechat_sync` 未找到

### Step 3: 修改 jobs.py

在 `huaqi_src/scheduler/jobs.py` 中添加：

```python
def _run_wechat_sync():
    from huaqi_src.core.config_manager import ConfigManager
    if not ConfigManager().is_enabled("wechat"):
        return
    from huaqi_src.collectors.wechat_watcher import WeChatWatcher
    try:
        watcher = WeChatWatcher()
        docs = watcher.sync_once()
        if docs:
            print(f"[WeChatSync] 同步了 {len(docs)} 批次消息记录")
    except Exception as e:
        print(f"[WeChatSync] 同步失败: {e}")
```

在 `register_default_jobs` 函数末尾添加：

```python
    from huaqi_src.core.config_manager import ConfigManager
    if ConfigManager().is_enabled("wechat"):
        manager.add_cron_job(
            "wechat_sync",
            func=_run_wechat_sync,
            cron="*/5 * * * *",
        )
```

### Step 4: 运行测试，确认通过

```bash
pytest tests/scheduler/test_jobs.py -v
```

预期：所有测试 PASS

### Step 5: Commit

```bash
git add huaqi_src/scheduler/jobs.py tests/scheduler/test_jobs.py
git commit -m "feat: register wechat_sync cron job when wechat module enabled"
```

---

## Task 10: 全量测试 + Lint

确认所有测试通过，无 lint 错误。

### Step 1: 运行全量测试

```bash
pytest tests/ -v --tb=short
```

预期：所有测试 PASS，无 ERROR

### Step 2: 运行 Lint

```bash
ruff check huaqi_src/ tests/
```

预期：无报错

### Step 3: 如有失败，定位修复

常见问题：
- `ImportError`：检查新模块的 import 路径，确认 `huaqi_src/collectors/__init__.py` 存在（已有，但为空文件，不需要改）
- `watchdog` 未安装：运行 `pip install watchdog`（已在 requirements.txt，正常情况下已安装）
- `ruff` 报 unused import：删除对应 import 行

### Step 4: 最终 Commit

```bash
git add -A
git commit -m "feat: Phase 3 监听采集 - WeChatWatcher + CLIChatWatcher 完整实现"
```

---

## 功能验证（手动测试）

完成所有 Task 后，可手动验证功能：

```bash
# 查看采集器状态
huaqi collector status

# 开启微信监听（在 data_dir/memory/config.yaml 中设置 modules.wechat: true）
# 或通过环境变量：
HUAQI_ENABLE_WECHAT=1 huaqi collector sync-wechat

# 手动同步 CLI 对话
huaqi collector sync-cli

# 验证数据已写入
ls ~/.huaqi_data/memory/wechat/
ls ~/.huaqi_data/memory/cli_chats/

# 启动对话，验证 Agent 可检索
huaqi chat
> 我最近和张三聊了什么？
```

---

## 文件清单汇总

| 新增文件 | 说明 |
|----------|------|
| `huaqi_src/collectors/wechat_state.py` | 微信增量同步状态持久化 |
| `huaqi_src/collectors/wechat_reader.py` | 微信 SQLite DB 增量读取器 |
| `huaqi_src/collectors/wechat_writer.py` | 微信消息写入数据湖 |
| `huaqi_src/collectors/wechat_watcher.py` | watchdog 监听器（组合以上三个） |
| `huaqi_src/collectors/cli_chat_parser.py` | CLI 对话文件解析器 |
| `huaqi_src/collectors/cli_chat_watcher.py` | CLI 对话目录监听器 |
| `huaqi_src/cli/commands/collector.py` | `huaqi collector` 子命令 |
| `tests/collectors/test_wechat_state.py` | |
| `tests/collectors/test_wechat_reader.py` | |
| `tests/collectors/test_wechat_writer.py` | |
| `tests/collectors/test_wechat_watcher.py` | |
| `tests/collectors/test_cli_chat_parser.py` | |
| `tests/collectors/test_cli_chat_watcher.py` | |
| `tests/cli/test_collector_cli.py` | |

| 修改文件 | 说明 |
|----------|------|
| `huaqi_src/agent/tools.py` | 追加 `search_wechat_tool`、`search_cli_chats_tool` |
| `huaqi_src/agent/graph/chat.py` | 将两个新 Tool 加入 `tools` 列表 |
| `huaqi_src/scheduler/jobs.py` | 注册 `wechat_sync` 定时任务 |
| `huaqi_src/cli/__init__.py` | 挂载 `collector_app` |
| `tests/agent/test_tools.py` | 追加两个新 Tool 的测试 |
| `tests/scheduler/test_jobs.py` | 追加 wechat_sync 注册测试 |
