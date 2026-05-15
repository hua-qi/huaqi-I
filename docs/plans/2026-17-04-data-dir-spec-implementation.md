# DATA_DIR 目录规范实施方案

**Goal:** 将 DATA_DIR 目录组织规范、文件命名规范、frontmatter 规范落地，包含现有数据迁移和写入逻辑修改。

**Architecture:** 分五个阶段独立推进：paths.py 新增 signals 目录支持 → WorkLogWriter 迁移到 signals/ → 各写入组件统一 frontmatter 字段 → 数据迁移脚本 → 各子目录补充 README。每个阶段都有独立测试验证，不影响已有功能。

**Tech Stack:** Python 3.11+, pathlib, pytest, PyYAML

---

## 背景阅读

实施前请先阅读：
- `docs/designs/2026-17-04-data-dir-spec.md` — 规范定义
- `huaqi_src/config/paths.py` — 路径管理，本次改动的核心文件
- `huaqi_src/layers/data/collectors/work_log_writer.py` — 当前写入 `work_logs/`，需迁移到 `signals/`
- `huaqi_src/layers/data/diary/store.py` — 日记写入，路径从 `YYYY-MM/` 改为 `YYYY/MM/DD/`
- `huaqi_src/layers/data/memory/storage/markdown_store.py` — 对话写入，路径从 `YYYY/MM/` 改为 `YYYY/MM/DD/`

运行已有测试确认基线：
```
pytest tests/ -v --tb=short 2>&1 | head -60
```

---

## Task 1: paths.py 新增 signals/ 目录支持

**Files:**
- Modify: `huaqi_src/config/paths.py`
- Create: `tests/unit/config/test_paths.py`

**Step 1: 写失败测试**

```python
# tests/unit/config/test_paths.py
import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.config import paths


def test_get_signals_dir_returns_signals_subdir(tmp_path):
    with patch.object(paths, "require_data_dir", return_value=tmp_path):
        result = paths.get_signals_dir()
    assert result == tmp_path / "signals"


def test_ensure_dirs_creates_signals_dir(tmp_path):
    with patch.object(paths, "_USER_DATA_DIR", tmp_path):
        paths.ensure_dirs()
    assert (tmp_path / "signals").exists()
```

**Step 2: 运行确认失败**

```
pytest tests/unit/config/test_paths.py -v
```
期望：`AttributeError: module has no attribute 'get_signals_dir'`

**Step 3: 在 `paths.py` 末尾添加函数，并更新 `ensure_dirs`**

在 `get_telos_dir()` 之后添加：
```python
def get_signals_dir() -> Path:
    return require_data_dir() / "signals"
```

将 `ensure_dirs()` 中的 `dirs` 列表添加 `get_signals_dir()`：
```python
def ensure_dirs():
    dirs = [
        get_memory_dir(),
        get_drafts_dir(),
        get_vector_db_dir(),
        get_models_cache_dir(),
        get_pending_reviews_dir(),
        get_learning_dir(),
        get_signals_dir(),   # 新增
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
```

**Step 4: 运行确认通过**

```
pytest tests/unit/config/test_paths.py -v
```
期望：2 passed

---

## Task 2: WorkLogWriter 迁移到 signals/ 目录

**背景：** 当前 `WorkLogWriter.write()` 写到 `{data_dir}/work_logs/{YYYY-MM}/` 目录，违反规范。新路径应为 `{data_dir}/signals/{YYYY}/{MM}/{DD}/`，文件名为 `worklog_{thread_id}.md`，frontmatter 新增 `type: worklog` 和 `source: codeflicker`。

**Files:**
- Modify: `huaqi_src/layers/data/collectors/work_log_writer.py`
- Modify: `tests/unit/layers/data/collectors/test_work_log_writer.py`

**Step 1: 读取现有测试文件了解测试结构**

```
# 先读取现有测试文件
cat tests/unit/layers/data/collectors/test_work_log_writer.py
```

**Step 2: 在现有测试文件中添加新路径断言**

在现有测试末尾添加：
```python
def test_write_uses_signals_dir_with_date_hierarchy(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    result = writer.write(
        messages=[CLIChatMessage(role="user", content="hello")],
        thread_id="abc123",
        time_start="2026-04-17T10:00:00Z",
        time_end="2026-04-17T10:30:00Z",
    )
    assert result is not None
    assert "signals" in result.parts
    assert "2026" in result.parts
    assert "04" in result.parts
    assert "17" in result.parts


def test_write_frontmatter_includes_type_and_source(tmp_path):
    writer = WorkLogWriter(data_dir=tmp_path)
    result = writer.write(
        messages=[CLIChatMessage(role="user", content="hello")],
        thread_id="abc123",
        time_start="2026-04-17T10:00:00Z",
        time_end="2026-04-17T10:30:00Z",
    )
    content = result.read_text(encoding="utf-8")
    assert "type: worklog" in content
    assert "source: codeflicker" in content
```

**Step 3: 运行确认失败**

```
pytest tests/unit/layers/data/collectors/test_work_log_writer.py -v -k "signals or frontmatter"
```
期望：2 FAILED

**Step 4: 修改 `work_log_writer.py` 的 `write()` 方法**

将路径构建部分从：
```python
month_key = time_start[:7]
out_dir = self._data_dir / "work_logs" / month_key
filename = f"{date_part}_{time_part}_{thread_id}.md"
```

改为：
```python
year = time_start[:4]
month = time_start[5:7]
day = time_start[8:10]
out_dir = self._data_dir / "signals" / year / month / day
filename = f"worklog_{thread_id}.md"
```

将 frontmatter 从：
```python
frontmatter = (
    f"---\n"
    f"date: {time_start[:10]}\n"
    f"time_start: {time_start}\n"
    f"time_end: {time_end}\n"
    f"thread_id: {thread_id}\n"
    f"source: codeflicker\n"
    f"---\n"
)
```

改为：
```python
frontmatter = (
    f"---\n"
    f"type: worklog\n"
    f"created_at: {time_start}\n"
    f"updated_at: {time_end}\n"
    f"date: {time_start[:10]}\n"
    f"time_start: {time_start}\n"
    f"time_end: {time_end}\n"
    f"thread_id: {thread_id}\n"
    f"source: codeflicker\n"
    f"tags: []\n"
    f"---\n"
)
```

**Step 5: 运行所有 WorkLogWriter 测试**

```
pytest tests/unit/layers/data/collectors/test_work_log_writer.py -v
```
期望：全部 PASSED

---

## Task 3: DiaryStore 路径改为 YYYY/MM/DD/ 三级目录

**背景：** 当前 `DiaryStore._get_diary_path()` 生成路径为 `diary/{YYYY-MM}/{YYYY-MM-DD}.md`，新规范要求 `diary/{YYYY}/{MM}/{DD}/daily.md`（同一天内如有多篇则用 `suffix` 区分）。

**Files:**
- Modify: `huaqi_src/layers/data/diary/store.py`
- Modify: `tests/unit/layers/data/` 下相关测试（如存在）

**Step 1: 确认测试文件位置**

```
find tests/ -name "*diary*" -o -name "*diary_store*" 2>/dev/null
```

**Step 2: 写失败测试**

在对应测试文件（如不存在则创建 `tests/unit/layers/data/test_diary_store.py`）中添加：
```python
from pathlib import Path
from huaqi_src.layers.data.diary.store import DiaryStore


def test_diary_path_uses_three_level_date_hierarchy(tmp_path):
    store = DiaryStore(memory_dir=tmp_path)
    store.save(date="2026-04-17", content="test content")
    expected = tmp_path / "diary" / "2026" / "04" / "17" / "daily.md"
    assert expected.exists()


def test_diary_path_with_suffix_creates_separate_file(tmp_path):
    store = DiaryStore(memory_dir=tmp_path)
    store.save(date="2026-04-17", content="first", suffix="morning")
    store.save(date="2026-04-17", content="second", suffix="evening")
    morning = tmp_path / "diary" / "2026" / "04" / "17" / "morning.md"
    evening = tmp_path / "diary" / "2026" / "04" / "17" / "evening.md"
    assert morning.exists()
    assert evening.exists()
```

**Step 3: 运行确认失败**

```
pytest tests/unit/layers/data/test_diary_store.py -v
```
期望：FAILED — 文件生成在旧路径

**Step 4: 修改 `DiaryStore._get_diary_path()`**

将：
```python
def _get_diary_path(self, date: str, suffix: str = "") -> Path:
    year_month = date[:7]  # YYYY-MM
    dir_path = self.diary_dir / year_month
    dir_path.mkdir(parents=True, exist_ok=True)
    if suffix:
        return dir_path / f"{date}-{suffix}.md"
    return dir_path / f"{date}.md"
```

改为：
```python
def _get_diary_path(self, date: str, suffix: str = "") -> Path:
    year, month, day = date[:4], date[5:7], date[8:10]
    dir_path = self.diary_dir / year / month / day
    dir_path.mkdir(parents=True, exist_ok=True)
    if suffix:
        return dir_path / f"{suffix}.md"
    return dir_path / "daily.md"
```

同时修改 `_build_markdown()` 中的 frontmatter，新增 `type` 和 `source` 字段：
```python
def _build_markdown(self, entry: DiaryEntry) -> str:
    lines = []
    lines.append("---")
    lines.append(f"type: diary")
    lines.append(f"date: {entry.date}")
    lines.append(f"created_at: {entry.created_at}")
    lines.append(f"updated_at: {entry.updated_at}")
    lines.append(f"source: manual")
    if entry.mood:
        lines.append(f"mood: {entry.mood}")
    tags_str = str(entry.tags) if entry.tags else "[]"
    lines.append(f"tags: {tags_str}")
    lines.append("---")
    lines.append("")
    lines.append(entry.content)
    lines.append("")
    return "\n".join(lines)
```

**Step 5: 修复受影响的 `list_entries()` 和 `search()` 方法**

`list_entries()` 使用 `self.diary_dir.rglob("*.md")` 和 `filepath.stem` 来解析日期，新路径下 stem 变成 `daily`，需要从父目录解析日期：

将 `list_entries()` 中的日期解析改为：
```python
for filepath in self.diary_dir.rglob("*.md"):
    try:
        # 从父目录结构解析日期：diary/YYYY/MM/DD/daily.md
        parts = filepath.parts
        diary_idx = next(i for i, p in enumerate(parts) if p == "diary")
        if len(parts) > diary_idx + 3:
            year_str = parts[diary_idx + 1]
            month_str = parts[diary_idx + 2]
            day_str = parts[diary_idx + 3]
            date_str = f"{year_str}-{month_str}-{day_str}"
        else:
            continue
        ...
```

**Step 6: 运行所有测试**

```
pytest tests/unit/layers/data/test_diary_store.py -v
```
期望：全部 PASSED

---

## Task 4: MarkdownMemoryStore 路径改为 YYYY/MM/DD/ 三级目录

**背景：** 当前 `MarkdownMemoryStore.save_conversation()` 生成路径为 `{YYYY}/{MM}/{timestamp}_{session_id}.md`，缺少 `DD` 层级，且无 `type` frontmatter 字段。

**Files:**
- Modify: `huaqi_src/layers/data/memory/storage/markdown_store.py`
- Create/Modify: `tests/unit/layers/data/memory/test_markdown_store.py`

**Step 1: 写失败测试**

```python
from pathlib import Path
from datetime import datetime
from huaqi_src.layers.data.memory.storage.markdown_store import MarkdownMemoryStore


def test_save_conversation_uses_three_level_date_hierarchy(tmp_path):
    store = MarkdownMemoryStore(base_dir=tmp_path)
    ts = datetime(2026, 4, 17, 14, 30, 0)
    store.save_conversation(
        session_id="sess001",
        timestamp=ts,
        turns=[{"user_message": "hi", "assistant_response": "hello"}],
    )
    files = list((tmp_path / "2026" / "04" / "17").glob("*.md"))
    assert len(files) == 1


def test_save_conversation_frontmatter_has_type(tmp_path):
    store = MarkdownMemoryStore(base_dir=tmp_path)
    ts = datetime(2026, 4, 17, 14, 30, 0)
    path = store.save_conversation(
        session_id="sess001",
        timestamp=ts,
        turns=[],
    )
    content = path.read_text(encoding="utf-8")
    assert "type: conversation" in content
    assert "source: cli" in content
```

**Step 2: 运行确认失败**

```
pytest tests/unit/layers/data/memory/test_markdown_store.py -v
```

**Step 3: 修改 `save_conversation()` 中的路径构建**

将：
```python
date_dir = self.base_dir / timestamp.strftime("%Y/%m")
filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{session_id}.md"
```

改为：
```python
date_dir = self.base_dir / timestamp.strftime("%Y") / timestamp.strftime("%m") / timestamp.strftime("%d")
filename = f"{timestamp.strftime('%H%M%S')}_{session_id}.md"
```

**Step 4: 修改 `_build_conversation_markdown()` 添加标准 frontmatter 字段**

在 frontmatter 部分添加 `type` 和 `source`：
```python
lines.append("---")
lines.append(f"type: conversation")
lines.append(f"session_id: {session_id}")
lines.append(f"created_at: {timestamp.isoformat()}")
lines.append(f"updated_at: {timestamp.isoformat()}")
lines.append(f"turns: {len(turns)}")
lines.append(f"source: cli")
lines.append(f"tags: []")
```

**Step 5: 运行测试**

```
pytest tests/unit/layers/data/memory/test_markdown_store.py -v
```
期望：全部 PASSED

---

## Task 5: CLIChatWatcher frontmatter 新增标准字段

**背景：** `cli_chat_watcher.py` 的 codeflicker 路径已符合三级目录规范（`codeflicker/YYYY/MM/DD/`），仅需在 frontmatter 中新增 `type: conversation` 和 `tags: []`。

**Files:**
- Modify: `huaqi_src/layers/data/collectors/cli_chat_watcher.py`
- Modify: `tests/unit/layers/data/collectors/test_cli_chat_watcher.py`

**Step 1: 找到 frontmatter 构建位置**

在 `cli_chat_watcher.py` 中找到 `_process_codeflicker_session()` 方法里的 frontmatter 字符串。

**Step 2: 写失败测试**

```python
def test_codeflicker_frontmatter_has_standard_fields(tmp_path):
    # 假设已有构造 CLIChatWatcher 和调用的方式，参考现有测试写法
    # 验证输出文件包含 type 和 tags
    ...
    content = out_file.read_text(encoding="utf-8")
    assert "type: conversation" in content
    assert "tags: []" in content
```

**Step 3: 修改 frontmatter 字符串**

将：
```python
frontmatter = (
    f"---\n"
    f"session_id: {session.session_id}\n"
    f"date: {date_str}\n"
    f"time_start: {session.time_start or ''}\n"
    f"time_end: {session.time_end or ''}\n"
    f"project: {Path(session.project_dir).name if session.project_dir else ''}\n"
    f"git_branch: {session.git_branch or ''}\n"
    f"---\n\n"
)
```

改为：
```python
frontmatter = (
    f"---\n"
    f"type: conversation\n"
    f"created_at: {session.time_start or ''}\n"
    f"updated_at: {session.time_end or ''}\n"
    f"session_id: {session.session_id}\n"
    f"date: {date_str}\n"
    f"time_start: {session.time_start or ''}\n"
    f"time_end: {session.time_end or ''}\n"
    f"project: {Path(session.project_dir).name if session.project_dir else ''}\n"
    f"git_branch: {session.git_branch or ''}\n"
    f"source: cli\n"
    f"tags: []\n"
    f"---\n\n"
)
```

**Step 4: 运行测试**

```
pytest tests/unit/layers/data/collectors/test_cli_chat_watcher.py -v
```
期望：全部 PASSED

---

## Task 6: 数据迁移脚本

**背景：** 历史数据存在于旧路径，需要一次性迁移到新路径规范。主要涉及：
- `work_logs/` → `signals/YYYY/MM/DD/`
- `diary/YYYY-MM/` → `diary/YYYY/MM/DD/`
- `conversations/YYYY/MM/` → `conversations/YYYY/MM/DD/`（如存在）

**Files:**
- Create: `scripts/migrate_data_dir.py`

**Step 1: 创建迁移脚本**

```python
#!/usr/bin/env python3
"""DATA_DIR 数据迁移脚本

将旧路径规范的数据文件迁移到新规范路径。
运行前请备份数据目录！
"""

import re
import shutil
import sys
from pathlib import Path


def migrate_work_logs(data_dir: Path, dry_run: bool = True) -> int:
    """work_logs/YYYY-MM/YYYYMMDD_HHMMSS_thread.md
       -> signals/YYYY/MM/DD/worklog_thread.md
    """
    count = 0
    work_logs_dir = data_dir / "work_logs"
    if not work_logs_dir.exists():
        return 0

    for f in work_logs_dir.rglob("*.md"):
        # 文件名格式：20260417_100000_abc123.md
        m = re.match(r"(\d{4})(\d{2})(\d{2})_\d{6}_(.+)\.md", f.name)
        if not m:
            print(f"  SKIP (cannot parse): {f}")
            continue
        year, month, day, thread_id = m.groups()
        new_dir = data_dir / "signals" / year / month / day
        new_file = new_dir / f"worklog_{thread_id}.md"
        print(f"  {'[DRY]' if dry_run else '[MOVE]'} {f} -> {new_file}")
        if not dry_run:
            new_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(new_file))
        count += 1

    return count


def migrate_diary(data_dir: Path, dry_run: bool = True) -> int:
    """diary/YYYY-MM/YYYY-MM-DD[-suffix].md
       -> diary/YYYY/MM/DD/daily.md (or suffix.md)
    """
    count = 0
    diary_dir = data_dir / "memory" / "diary"
    if not diary_dir.exists():
        return 0

    for f in diary_dir.rglob("*.md"):
        # 跳过已迁移的（路径中已有三级目录 YYYY/MM/DD）
        parts = f.relative_to(diary_dir).parts
        if len(parts) == 4:  # YYYY/MM/DD/file.md
            continue

        # 解析文件名中的日期
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})-?(.*)\.md", f.name)
        if not m:
            print(f"  SKIP (cannot parse): {f}")
            continue
        year, month, day, suffix = m.groups()
        new_dir = diary_dir / year / month / day
        filename = f"{suffix}.md" if suffix else "daily.md"
        new_file = new_dir / filename
        print(f"  {'[DRY]' if dry_run else '[MOVE]'} {f} -> {new_file}")
        if not dry_run:
            new_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(new_file))
        count += 1

    return count


def migrate_conversations(data_dir: Path, dry_run: bool = True) -> int:
    """conversations/YYYY/MM/YYYYMMDD_HHMMSS_session.md
       -> conversations/YYYY/MM/DD/HHMMSS_session.md
    """
    count = 0
    conv_dir = data_dir / "memory" / "conversations"
    if not conv_dir.exists():
        return 0

    for f in conv_dir.rglob("*.md"):
        parts = f.relative_to(conv_dir).parts
        if len(parts) == 4:  # YYYY/MM/DD/file.md — 已迁移
            continue

        m = re.match(r"(\d{4})(\d{2})(\d{2})_(\d{6})_(.+)\.md", f.name)
        if not m:
            print(f"  SKIP (cannot parse): {f}")
            continue
        year, month, day, time_part, session_id = m.groups()
        new_dir = conv_dir / year / month / day
        new_file = new_dir / f"{time_part}_{session_id}.md"
        print(f"  {'[DRY]' if dry_run else '[MOVE]'} {f} -> {new_file}")
        if not dry_run:
            new_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(new_file))
        count += 1

    return count


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/migrate_data_dir.py <DATA_DIR> [--execute]")
        print("  默认为 dry-run 模式，加 --execute 才实际移动文件")
        sys.exit(1)

    data_dir = Path(sys.argv[1]).expanduser().resolve()
    dry_run = "--execute" not in sys.argv

    if not data_dir.exists():
        print(f"ERROR: 目录不存在: {data_dir}")
        sys.exit(1)

    print(f"DATA_DIR: {data_dir}")
    print(f"模式: {'DRY RUN（仅预览）' if dry_run else '实际执行！'}")
    print()

    print("=== 迁移 work_logs -> signals ===")
    n1 = migrate_work_logs(data_dir, dry_run)
    print(f"  共 {n1} 个文件")

    print()
    print("=== 迁移 diary 路径 ===")
    n2 = migrate_diary(data_dir, dry_run)
    print(f"  共 {n2} 个文件")

    print()
    print("=== 迁移 conversations 路径 ===")
    n3 = migrate_conversations(data_dir, dry_run)
    print(f"  共 {n3} 个文件")

    print()
    print(f"合计：{n1 + n2 + n3} 个文件{'（预览，未实际移动）' if dry_run else '（已完成迁移）'}")

    if dry_run and (n1 + n2 + n3) > 0:
        print()
        print("确认无误后，运行以下命令执行实际迁移：")
        print(f"  python scripts/migrate_data_dir.py {data_dir} --execute")


if __name__ == "__main__":
    main()
```

**Step 2: 预览迁移（不实际移动）**

```
python scripts/migrate_data_dir.py ~/your/data/dir
```
检查输出，确认迁移路径正确。

**Step 3: 执行迁移（备份后再运行）**

```
# 先备份
cp -r ~/your/data/dir ~/your/data/dir_backup_$(date +%Y%m%d)

# 执行迁移
python scripts/migrate_data_dir.py ~/your/data/dir --execute
```

**Step 4: 验证迁移结果**

```
# 确认 work_logs/ 目录为空或已不存在
ls ~/your/data/dir/work_logs/

# 确认 signals/ 已有文件
ls ~/your/data/dir/signals/
```

---

## Task 7: 各子目录补充 README.md

**背景：** DATA_DIR 的每个子目录需要有 `README.md`，格式见 `docs/designs/2026-17-04-data-dir-spec.md` 第 3.1 节模板。

**Files:**
- Create: `templates/data_dir_readme/` 下各子目录 README 模板（运行时复制到 DATA_DIR）
- Modify: `huaqi_src/config/paths.py` 中的 `ensure_dirs()` 在创建目录时自动写入 README

**Step 1: 在 `ensure_dirs()` 中调用 README 初始化**

在 `paths.py` 新增以下函数，并在 `ensure_dirs()` 末尾调用：

```python
_README_TEMPLATES: dict[str, str] = {
    "memory": """# memory

## 职责
存储用户的对话历史、日记、用户画像等已蒸馏的认知数据。

## 包含内容
- `diary/YYYY/MM/DD/`：日记文件
- `conversations/YYYY/MM/DD/`：对话历史
- `cli_chats/codeflicker/YYYY/MM/DD/`：CLI 工具对话记录
- `personality.yaml`：用户画像（档案数据）
- `growth.yaml`：成长数据（档案数据）

## 禁止放置
- 未处理的原始信号（放 signals/）
- 已蒸馏的认知维度结论（放 telos/）

## 相关目录
- `../signals/`：原始信号，处理后写入 memory
- `../telos/`：认知蒸馏结果
""",
    "signals": """# signals

## 职责
存储待处理的原始信号，包括工作日志、网页采集等未经蒸馏的原始内容。

## 包含内容
- `YYYY/MM/DD/worklog_<thread_id>.md`：工作日志信号
- `YYYY/MM/DD/web_capture.md`：网页采集信号

## 禁止放置
- 已蒸馏的认知结论（放 telos/）
- 对话历史（放 memory/conversations/）

## 相关目录
- `../memory/`：信号处理后的认知数据存储目标
- `../telos/`：信号蒸馏后的维度存储目标
""",
    "telos": """# telos

## 职责
存储 TELOS 8 维度认知蒸馏结果，按月组织。

## 包含内容
- `YYYY/MM/<dimension>.yaml`：各维度认知结论（月度更新）

## 禁止放置
- 原始信号或对话记录
- 未经蒸馏的数据

## 文件结构
```
telos/
└── 2026/
    └── 04/
        ├── work_style.yaml
        └── learning_pattern.yaml
```

## 相关目录
- `../signals/`：待蒸馏的原始信号来源
""",
    "drafts": """# drafts

## 职责
存储正在编辑中、待发布的内容草稿。

## 包含内容
- 任何格式的编辑中内容

## 禁止放置
- 已发布内容
- 已废弃内容（直接删除）

## 相关目录
- `../pending_reviews/`：草稿经 AI 生成后待人工确认的内容
""",
    "pending_reviews": """# pending_reviews

## 职责
存储需要人工确认的 AI 输出内容，等待审核后移至目标目录。

## 包含内容
- AI 生成的待确认文件

## 禁止放置
- 已确认内容（移至目标目录后删除）

## 相关目录
- `../drafts/`：人工编辑中的草稿
""",
    "people": """# people

## 职责
存储关系人的长期档案信息。

## 包含内容
- `<name_slug>.md`：关系人档案（档案数据，无时间目录）

## 禁止放置
- 单次对话中仅提及的人名
- 临时联系人

## 文件结构
```
people/
├── zhang_wei.md
└── li_ming.md
```
""",
    "world": """# world

## 职责
存储世界知识、新闻摘要、行业动态等外部信息。

## 包含内容
- `<topic_slug>.md`：主题知识文件（档案数据）

## 禁止放置
- 个人工作日志
- 私人对话记录

## 相关目录
- `../memory/`：个人认知数据
""",
    "learning": """# learning

## 职责
存储学习记录与笔记。

## 包含内容
- 学习笔记、课程记录等

## 禁止放置
- 已蒸馏进 telos 的认知结论
- 工作日志（放 signals/）

## 相关目录
- `../telos/`：学习蒸馏后的认知维度
""",
}


def _ensure_readme(directory: Path, key: str) -> None:
    readme = directory / "README.md"
    if not readme.exists() and key in _README_TEMPLATES:
        readme.write_text(_README_TEMPLATES[key], encoding="utf-8")
```

在 `ensure_dirs()` 末尾追加：
```python
    _ensure_readme(get_memory_dir(), "memory")
    _ensure_readme(get_signals_dir(), "signals")
    _ensure_readme(get_telos_dir(), "telos")
    _ensure_readme(get_drafts_dir(), "drafts")
    _ensure_readme(get_pending_reviews_dir(), "pending_reviews")
    _ensure_readme(get_people_dir(), "people")
    _ensure_readme(get_world_dir(), "world")
    _ensure_readme(get_learning_dir(), "learning")
```

**Step 2: 写测试验证 README 自动创建**

```python
def test_ensure_dirs_creates_readmes(tmp_path):
    with patch.object(paths, "_USER_DATA_DIR", tmp_path):
        paths.ensure_dirs()
    assert (tmp_path / "memory" / "README.md").exists()
    assert (tmp_path / "signals" / "README.md").exists()
    content = (tmp_path / "signals" / "README.md").read_text()
    assert "原始信号" in content
```

**Step 3: 运行测试**

```
pytest tests/unit/config/test_paths.py -v
```
期望：全部 PASSED

---

## Task 8: 全量回归测试

**Step 1: 运行全部单元测试**

```
pytest tests/unit/ -v --tb=short 2>&1 | tail -30
```
期望：全部 PASSED，无 FAILED

**Step 2: 运行集成测试**

```
pytest tests/integration/ -v --tb=short 2>&1 | tail -30
```

**Step 3: 验证 .test_data/ 目录兼容性**

测试使用的是 `.test_data/`，检查是否需要补充该目录的结构：
```
ls .test_data/
```
如果 `.test_data/` 缺少 `signals/` 目录，在 `conftest.py` 或测试 fixture 中添加。

---

## 注意事项

1. **Task 3（DiaryStore）改动风险最高**：`list_entries()` 和 `search()` 都依赖文件路径解析日期，路径变化后必须同步修改，否则读取逻辑会失败。
2. **迁移脚本（Task 6）必须先 dry-run**：确认输出路径正确后再加 `--execute`。
3. **不要迁移 `memory/cli_chats/codeflicker/`**：该目录已符合三级目录规范，无需迁移。
4. **`telos/` 目录**：当前写入逻辑在 `telos/manager.py` 使用 `{name}.md` 扁平结构，规范要求月度目录，但 telos 写入逻辑改动较复杂，**本次计划不纳入**，单独规划。
