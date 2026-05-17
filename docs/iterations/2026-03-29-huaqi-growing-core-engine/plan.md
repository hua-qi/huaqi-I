# Huaqi Growing Core Engine Implementation Plan

**Goal:** 构建 `huaqi-growing` 的底层事件总线、默认关闭（Opt-in）的配置管理以及本地 SQLite 安全存储基础。

**Architecture:** 采用轻量级 Python 模块化设计。配置管理器确保所有监控探针默认关闭。数据总线统一定义 `Event` 数据类，内嵌正则脱敏逻辑。存储层使用单机 `sqlite3` 数据库持久化结构化事件，不涉及任何云端同步。

**Tech Stack:** Python 3, dataclasses, sqlite3, pytest

---

### Task 1: Configuration Manager (Privacy First)

**Files:**
- Create: `huaqi_src/core/config_manager.py`
- Create: `tests/core/test_config_manager.py`

**Step 1: Write the failing test**

```python
# tests/core/test_config_manager.py
from huaqi_src.core.config_manager import ConfigManager

def test_modules_disabled_by_default():
    config = ConfigManager()
    assert config.is_enabled("wechat") is False
    assert config.is_enabled("network_proxy") is False

def test_enable_module():
    config = ConfigManager()
    config.enable("wechat")
    assert config.is_enabled("wechat") is True
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/test_config_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'huaqi_src.core.config_manager'"

**Step 3: Write minimal implementation**

```python
# huaqi_src/core/config_manager.py
class ConfigManager:
    def __init__(self):
        self._enabled_modules = set()

    def is_enabled(self, module_name: str) -> bool:
        return module_name in self._enabled_modules

    def enable(self, module_name: str) -> None:
        self._enabled_modules.add(module_name)
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/test_config_manager.py -v`
Expected: PASS

**Step 5: Commit**

Run: `git add huaqi_src/core/config_manager.py tests/core/test_config_manager.py && git commit -m "feat: add config manager with opt-in privacy defaults"`

---

### Task 2: Unified Event Structure & Data Redaction

**Files:**
- Create: `huaqi_src/core/event.py`
- Create: `tests/core/test_event.py`

**Step 1: Write the failing test**

```python
# tests/core/test_event.py
from huaqi_src.core.event import Event, redact_sensitive_info
import time

def test_redact_sensitive_info():
    raw_text = "Here is my key sk-proj-12345ABCDE and some text."
    redacted = redact_sensitive_info(raw_text)
    assert "sk-proj-12345ABCDE" not in redacted
    assert "sk-***" in redacted

def test_event_creation():
    event = Event(
        timestamp=int(time.time()),
        source="terminal/bash",
        actor="User",
        content="Testing key sk-abcde"
    )
    assert event.source == "terminal/bash"
    assert "sk-***" in event.content
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/test_event.py -v`
Expected: FAIL with "ImportError: cannot import name 'Event'"

**Step 3: Write minimal implementation**

```python
# huaqi_src/core/event.py
from dataclasses import dataclass
import re

def redact_sensitive_info(text: str) -> str:
    # 简单的正则匹配 OpenAI 或其他 sk- 开头的密钥
    return re.sub(r'sk-[a-zA-Z0-9\-]+', 'sk-***', text)

@dataclass
class Event:
    timestamp: int
    source: str
    actor: str
    content: str
    context_id: str = ""

    def __post_init__(self):
        self.content = redact_sensitive_info(self.content)
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/test_event.py -v`
Expected: PASS

**Step 5: Commit**

Run: `git add huaqi_src/core/event.py tests/core/test_event.py && git commit -m "feat: add unified event structure with auto-redaction"`

---

### Task 3: Local SQLite Storage Engine

**Files:**
- Create: `huaqi_src/core/db_storage.py`
- Create: `tests/core/test_db_storage.py`

**Step 1: Write the failing test**

```python
# tests/core/test_db_storage.py
from huaqi_src.core.db_storage import LocalDBStorage
from huaqi_src.core.event import Event
import sqlite3
import time

def test_db_insert_and_retrieve():
    # 使用内存数据库进行测试
    db = LocalDBStorage(":memory:")
    event = Event(
        timestamp=1700000000,
        source="wechat",
        actor="System",
        content="Hello world"
    )
    db.insert_event(event)
    
    results = db.get_recent_events(limit=1)
    assert len(results) == 1
    assert results[0].source == "wechat"
    assert results[0].content == "Hello world"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/test_db_storage.py -v`
Expected: FAIL with "ImportError: cannot import name 'LocalDBStorage'"

**Step 3: Write minimal implementation**

```python
# huaqi_src/core/db_storage.py
import sqlite3
from typing import List
from huaqi_src.core.event import Event

class LocalDBStorage:
    def __init__(self, db_path: str = "memory.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                source TEXT,
                actor TEXT,
                content TEXT,
                context_id TEXT
            )
        ''')
        self.conn.commit()

    def insert_event(self, event: Event):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO events (timestamp, source, actor, content, context_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (event.timestamp, event.source, event.actor, event.content, event.context_id))
        self.conn.commit()

    def get_recent_events(self, limit: int = 10) -> List[Event]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT timestamp, source, actor, content, context_id FROM events ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        return [Event(timestamp=r[0], source=r[1], actor=r[2], content=r[3], context_id=r[4]) for r in rows]
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/test_db_storage.py -v`
Expected: PASS

**Step 5: Commit**

Run: `git add huaqi_src/core/db_storage.py tests/core/test_db_storage.py && git commit -m "feat: implement local sqlite storage for events"`
