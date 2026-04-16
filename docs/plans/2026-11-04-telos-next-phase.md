# Telos 下一阶段 Implementation Plan

**Goal:** 实现 Telos 系统 7 条未实现项：Person 模型扩展、PeoplePipeline、search_person 工具注入、search_memory 工具（含向量检索前置）、asyncio 全链路改造。

**Architecture:** 按依赖链自底向上分 4 个 Week：数据层（Person 模型 + PeopleGraph 扩展）→ PeoplePipeline → Agent 工具层 → asyncio 全链路。每层产出独立可测。

**Tech Stack:** Python dataclasses, LangChain (.ainvoke), pytest-asyncio (asyncio_mode=auto), AsyncMock, SQLite RawSignalStore, Markdown 文件存储。

---

## 关键约定（先读，后动手）

- 测试运行命令：`pytest tests/ -v`
- 单文件测试：`pytest tests/path/test_file.py::ClassName::test_name -v`
- 无需 `@pytest.mark.asyncio`，`pyproject.toml` 已配置 `asyncio_mode = "auto"`
- `AsyncMock` 从 `unittest.mock` 导入，不能用普通 `MagicMock` 替代 `async` 方法
- 所有 Markdown 文件以 `utf-8` 读写
- 归档目录：`_archive/`（已在 telos_dir 下，people 没有，需新建）

---

## Week 1：Person 模型扩展（第 5+6+7 条）

### Task 1：新增 InteractionLog 和 EmotionalTimeline 数据类

**Files:**
- Modify: `huaqi_src/layers/growth/telos/dimensions/people/models.py`
- Test: `tests/unit/layers/growth/test_people_models.py`（新建）

**Step 1: 写失败测试**

新建 `tests/unit/layers/growth/test_people_models.py`：

```python
import datetime
from huaqi_src.layers.growth.telos.dimensions.people.models import (
    InteractionLog,
    EmotionalTimeline,
    Person,
)


def test_interaction_log_fields():
    log = InteractionLog(
        date="2026-10-01",
        signal_id="sig_abc123",
        interaction_type="合作",
        summary="一起推进了产品评审",
    )
    assert log.date == "2026-10-01"
    assert log.interaction_type == "合作"


def test_emotional_timeline_fields():
    entry = EmotionalTimeline(
        date="2026-10-01",
        score=0.7,
        trigger="合作顺畅",
    )
    assert entry.score == 0.7


def test_person_has_interaction_logs_field():
    person = Person(
        person_id="p1",
        name="张伟",
        relation_type="同事",
    )
    assert person.interaction_logs == []
    assert person.emotional_timeline == []


def test_person_accepts_interaction_logs():
    log = InteractionLog(
        date="2026-10-01",
        signal_id="sig_1",
        interaction_type="日常",
        summary="日常交流",
    )
    person = Person(
        person_id="p1",
        name="张伟",
        relation_type="同事",
        interaction_logs=[log],
    )
    assert len(person.interaction_logs) == 1
```

**Step 2: 运行确认失败**

```
pytest tests/unit/layers/growth/test_people_models.py -v
```
预期：`ImportError: cannot import name 'InteractionLog'`

**Step 3: 实现最小代码**

修改 `huaqi_src/layers/growth/telos/dimensions/people/models.py`，在 `Person` 类定义前新增两个 dataclass，并在 `Person` 中新增两个字段：

```python
import datetime
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class InteractionLog:
    date: str
    signal_id: str
    interaction_type: str
    summary: str


@dataclass
class EmotionalTimeline:
    date: str
    score: float
    trigger: str


@dataclass
class Person:
    person_id: str
    name: str
    relation_type: str
    alias: list[str] = field(default_factory=list)
    profile: str = ""
    emotional_impact: str = "中性"
    interaction_frequency: int = 0
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    interaction_logs: List[InteractionLog] = field(default_factory=list)
    emotional_timeline: List[EmotionalTimeline] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "person_id": self.person_id,
            "name": self.name,
            "relation_type": self.relation_type,
            "alias": self.alias,
            "profile": self.profile,
            "emotional_impact": self.emotional_impact,
            "interaction_frequency": self.interaction_frequency,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "interaction_logs": [
                {
                    "date": l.date,
                    "signal_id": l.signal_id,
                    "interaction_type": l.interaction_type,
                    "summary": l.summary,
                }
                for l in self.interaction_logs
            ],
            "emotional_timeline": [
                {
                    "date": e.date,
                    "score": e.score,
                    "trigger": e.trigger,
                }
                for e in self.emotional_timeline
            ],
        }
```

**Step 4: 运行确认通过**

```
pytest tests/unit/layers/growth/test_people_models.py -v
```
预期：4 个 PASS

**Step 5: Commit**

```
git add huaqi_src/layers/growth/telos/dimensions/people/models.py tests/unit/layers/growth/test_people_models.py
git commit -m "feat: add InteractionLog and EmotionalTimeline to Person model"
```

---

### Task 2：PeopleGraph 支持读写 InteractionLog + EmotionalTimeline

**Files:**
- Modify: `huaqi_src/layers/growth/telos/dimensions/people/graph.py`
- Test: `tests/unit/layers/growth/test_people_graph.py`（新建）

**扩展后的 Person.md 格式：**

```markdown
# 张伟

**关系类型:** 同事
**情感倾向:** 积极（huaqi 的观察）
**近30天互动次数:** 3

## 画像
产品经理，务实

## 备注
暂无

## 互动记录
| 日期 | 类型 | 摘要 | signal_id |
|------|------|------|-----------|
| 2026-10-01 | 合作 | 讨论产品方向 | sig_abc123 |

## 情感时序
| 日期 | 分值 | 触发原因 |
|------|------|---------|
| 2026-10-01 | 0.7 | 合作顺畅，共识多 |

<!-- person_id: ... -->
<!-- alias: [] -->
<!-- created_at: ... -->
<!-- updated_at: ... -->
```

**Step 1: 写失败测试**

新建 `tests/unit/layers/growth/test_people_graph.py`：

```python
from pathlib import Path
import pytest
from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph
from huaqi_src.layers.growth.telos.dimensions.people.models import (
    Person,
    InteractionLog,
    EmotionalTimeline,
)


@pytest.fixture
def graph(tmp_path: Path) -> PeopleGraph:
    return PeopleGraph(data_dir=tmp_path)


def test_graph_writes_and_reads_interaction_logs(graph):
    log = InteractionLog(
        date="2026-10-01",
        signal_id="sig_1",
        interaction_type="合作",
        summary="讨论产品方向",
    )
    person = Person(
        person_id="p1",
        name="张伟",
        relation_type="同事",
        interaction_logs=[log],
    )
    graph.add_person(person)

    loaded = graph.get_person("张伟")
    assert loaded is not None
    assert len(loaded.interaction_logs) == 1
    assert loaded.interaction_logs[0].interaction_type == "合作"
    assert loaded.interaction_logs[0].signal_id == "sig_1"


def test_graph_writes_and_reads_emotional_timeline(graph):
    entry = EmotionalTimeline(date="2026-10-01", score=0.7, trigger="合作顺畅")
    person = Person(
        person_id="p1",
        name="李四",
        relation_type="朋友",
        emotional_timeline=[entry],
    )
    graph.add_person(person)

    loaded = graph.get_person("李四")
    assert loaded is not None
    assert len(loaded.emotional_timeline) == 1
    assert abs(loaded.emotional_timeline[0].score - 0.7) < 0.001
    assert loaded.emotional_timeline[0].trigger == "合作顺畅"


def test_graph_truncates_interaction_logs_at_50(graph):
    logs = [
        InteractionLog(date=f"2026-{i:02d}-01", signal_id=f"sig_{i}", interaction_type="日常", summary=f"第{i}次")
        for i in range(1, 60)
    ]
    person = Person(person_id="p1", name="王五", relation_type="同事", interaction_logs=logs)
    graph.add_person(person)

    loaded = graph.get_person("王五")
    assert loaded is not None
    assert len(loaded.interaction_logs) <= 50


def test_graph_archives_overflow_logs(graph, tmp_path):
    logs = [
        InteractionLog(date=f"2026-{(i % 12) + 1:02d}-01", signal_id=f"sig_{i}", interaction_type="日常", summary=f"第{i}次")
        for i in range(1, 60)
    ]
    person = Person(person_id="p1", name="赵六", relation_type="同事", interaction_logs=logs)
    graph.add_person(person)

    archive_dir = tmp_path / "people" / "_archive"
    archive_files = list(archive_dir.glob("赵六_*.md")) if archive_dir.exists() else []
    assert len(archive_files) >= 1


def test_graph_backward_compatible_without_new_sections(graph):
    old_md = """# 旧人物

**关系类型:** 朋友
**情感倾向:** 积极（huaqi 的观察）
**近30天互动次数:** 0

## 画像
暂无

## 备注
暂无

<!-- person_id: old-001 -->
<!-- alias: [] -->
<!-- created_at: 2026-01-01T00:00:00 -->
<!-- updated_at: 2026-01-01T00:00:00 -->
"""
    people_dir = graph._people_dir
    (people_dir / "旧人物.md").write_text(old_md, encoding="utf-8")

    loaded = graph.get_person("旧人物")
    assert loaded is not None
    assert loaded.interaction_logs == []
    assert loaded.emotional_timeline == []
```

**Step 2: 运行确认失败**

```
pytest tests/unit/layers/growth/test_people_graph.py -v
```
预期：大部分 FAIL，因为 `_write_markdown` 不含新 section，`_read_markdown` 不解析新 section

**Step 3: 实现最小代码**

修改 `huaqi_src/layers/growth/telos/dimensions/people/graph.py`，将 `_write_markdown` 和 `_read_markdown` 扩展。

在 `_write_markdown` 的 `<!-- person_id: ... -->` 注释之前插入两个新 section，并在写入前处理超限截断和归档：

```python
import json
import datetime
from pathlib import Path
from typing import Optional

from .models import Person, Relation, InteractionLog, EmotionalTimeline

MAX_LOGS = 50


class PeopleGraph:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._people_dir = Path(data_dir) / "people"
        else:
            from huaqi_src.config.paths import get_people_dir
            self._people_dir = get_people_dir()
        self._people_dir.mkdir(parents=True, exist_ok=True)

    def _person_file(self, name: str) -> Path:
        return self._people_dir / f"{name}.md"

    def _archive_dir(self) -> Path:
        d = self._people_dir / "_archive"
        d.mkdir(exist_ok=True)
        return d

    def _archive_overflow_logs(self, person: Person, overflow: list[InteractionLog]) -> None:
        if not overflow:
            return
        year = datetime.datetime.now().year
        archive_file = self._archive_dir() / f"{person.name}_{year}.md"
        rows = "\n".join(
            f"| {l.date} | {l.interaction_type} | {l.summary} | {l.signal_id} |"
            for l in overflow
        )
        header = "| 日期 | 类型 | 摘要 | signal_id |\n|------|------|------|-----------|"
        content = f"## 互动记录归档（{year}）\n\n{header}\n{rows}\n"
        if archive_file.exists():
            existing = archive_file.read_text(encoding="utf-8")
            archive_file.write_text(existing + "\n" + content, encoding="utf-8")
        else:
            archive_file.write_text(content, encoding="utf-8")

    def _write_markdown(self, person: Person) -> None:
        interaction_logs = person.interaction_logs
        overflow: list[InteractionLog] = []
        if len(interaction_logs) > MAX_LOGS:
            overflow = interaction_logs[:-MAX_LOGS]
            interaction_logs = interaction_logs[-MAX_LOGS:]
            self._archive_overflow_logs(person, overflow)

        lines = [
            f"# {person.name}",
            "",
            f"**关系类型:** {person.relation_type}",
            f"**情感倾向:** {person.emotional_impact}（huaqi 的观察）",
            f"**近30天互动次数:** {person.interaction_frequency}",
            "",
            "## 画像",
            person.profile or "暂无",
            "",
            "## 备注",
            person.notes or "暂无",
            "",
        ]

        lines += [
            "## 互动记录",
            "| 日期 | 类型 | 摘要 | signal_id |",
            "|------|------|------|-----------|",
        ]
        for log in interaction_logs:
            lines.append(f"| {log.date} | {log.interaction_type} | {log.summary} | {log.signal_id} |")
        lines.append("")

        lines += [
            "## 情感时序",
            "| 日期 | 分值 | 触发原因 |",
            "|------|------|---------|",
        ]
        for entry in person.emotional_timeline:
            lines.append(f"| {entry.date} | {entry.score} | {entry.trigger} |")
        lines.append("")

        lines += [
            f"<!-- person_id: {person.person_id} -->",
            f"<!-- alias: {json.dumps(person.alias, ensure_ascii=False)} -->",
            f"<!-- created_at: {person.created_at} -->",
            f"<!-- updated_at: {person.updated_at} -->",
        ]
        self._person_file(person.name).write_text("\n".join(lines), encoding="utf-8")

    def _parse_interaction_logs(self, lines: list[str]) -> list[InteractionLog]:
        capturing = False
        logs = []
        for line in lines:
            if line == "## 互动记录":
                capturing = True
                continue
            if capturing:
                if line.startswith("## ") or line.startswith("<!-- "):
                    break
                if line.startswith("|") and "日期" not in line and "---" not in line and line.strip() != "|":
                    parts = [p.strip() for p in line.strip().strip("|").split("|")]
                    if len(parts) >= 4:
                        logs.append(InteractionLog(
                            date=parts[0],
                            interaction_type=parts[1],
                            summary=parts[2],
                            signal_id=parts[3],
                        ))
        return logs

    def _parse_emotional_timeline(self, lines: list[str]) -> list[EmotionalTimeline]:
        capturing = False
        entries = []
        for line in lines:
            if line == "## 情感时序":
                capturing = True
                continue
            if capturing:
                if line.startswith("## ") or line.startswith("<!-- "):
                    break
                if line.startswith("|") and "日期" not in line and "---" not in line and line.strip() != "|":
                    parts = [p.strip() for p in line.strip().strip("|").split("|")]
                    if len(parts) >= 3:
                        try:
                            score = float(parts[1])
                        except ValueError:
                            score = 0.0
                        entries.append(EmotionalTimeline(
                            date=parts[0],
                            score=score,
                            trigger=parts[2],
                        ))
        return entries

    def _read_markdown(self, name: str) -> Optional[Person]:
        f = self._person_file(name)
        if not f.exists():
            return None
        content = f.read_text(encoding="utf-8")
        lines = content.splitlines()

        def _extract_comment(key: str) -> str:
            for line in lines:
                if line.startswith(f"<!-- {key}:"):
                    return line.split(":", 1)[1].strip().rstrip(" -->").strip()
            return ""

        def _extract_field(label: str) -> str:
            prefix = f"**{label}:**"
            for line in lines:
                if line.startswith(prefix):
                    return line[len(prefix):].strip()
            return ""

        def _extract_section(heading: str) -> str:
            capturing = False
            result_lines = []
            for line in lines:
                if line == f"## {heading}":
                    capturing = True
                    continue
                if capturing:
                    if line.startswith("## ") or line.startswith("<!-- "):
                        break
                    result_lines.append(line)
            return "\n".join(result_lines).strip()

        person_id = _extract_comment("person_id")
        alias_raw = _extract_comment("alias")
        created_at = _extract_comment("created_at")
        updated_at = _extract_comment("updated_at")

        try:
            alias = json.loads(alias_raw) if alias_raw else []
        except Exception:
            alias = []

        relation_type_raw = _extract_field("关系类型")
        emotional_impact_raw = _extract_field("情感倾向")
        emotional_impact = emotional_impact_raw.split("（")[0].strip()
        interaction_frequency_raw = _extract_field("近30天互动次数")
        try:
            interaction_frequency = int(interaction_frequency_raw)
        except Exception:
            interaction_frequency = 0

        profile = _extract_section("画像")
        notes = _extract_section("备注")
        if profile == "暂无":
            profile = ""
        if notes == "暂无":
            notes = ""

        interaction_logs = self._parse_interaction_logs(lines)
        emotional_timeline = self._parse_emotional_timeline(lines)

        return Person(
            person_id=person_id or f"{name}-unknown",
            name=name,
            relation_type=relation_type_raw,
            alias=alias,
            profile=profile,
            emotional_impact=emotional_impact,
            interaction_frequency=interaction_frequency,
            notes=notes,
            created_at=created_at or datetime.datetime.now().isoformat(),
            updated_at=updated_at or datetime.datetime.now().isoformat(),
            interaction_logs=interaction_logs,
            emotional_timeline=emotional_timeline,
        )

    # 以下方法不变（add_person, get_person, list_people, update_person, delete_person, search）
    def add_person(self, person: Person) -> None:
        self._write_markdown(person)

    def get_person(self, name: str) -> Optional[Person]:
        return self._read_markdown(name)

    def list_people(self) -> list[Person]:
        people = []
        for f in sorted(self._people_dir.glob("*.md")):
            if f.parent.name == "_archive":
                continue
            p = self._read_markdown(f.stem)
            if p is not None:
                people.append(p)
        return people

    def update_person(self, name: str, **kwargs) -> bool:
        person = self.get_person(name)
        if person is None:
            return False
        for key, value in kwargs.items():
            if hasattr(person, key):
                setattr(person, key, value)
        person.updated_at = datetime.datetime.now().isoformat()
        self._write_markdown(person)
        return True

    def delete_person(self, name: str) -> bool:
        f = self._person_file(name)
        if not f.exists():
            return False
        f.unlink()
        return True

    def search(self, query: str) -> list[Person]:
        query_lower = query.lower()
        results = []
        for person in self.list_people():
            text = f"{person.name} {person.profile} {person.notes} {' '.join(person.alias)}".lower()
            if query_lower in text:
                results.append(person)
        return results
```

**Step 4: 运行确认通过**

```
pytest tests/unit/layers/growth/test_people_graph.py -v
```
预期：5 个 PASS

**Step 5: 确认现有测试不回归**

```
pytest tests/ -v
```

**Step 6: Commit**

```
git add huaqi_src/layers/growth/telos/dimensions/people/graph.py tests/unit/layers/growth/test_people_graph.py
git commit -m "feat: PeopleGraph supports InteractionLog and EmotionalTimeline read/write with 50-entry cap"
```

---

### Task 3：PeopleGraph.get_top_n（第 7 条）

**Files:**
- Modify: `huaqi_src/layers/growth/telos/dimensions/people/graph.py`
- Test: `tests/unit/layers/growth/test_people_graph.py`（追加测试）

**Step 1: 写失败测试**

在 `tests/unit/layers/growth/test_people_graph.py` 末尾追加：

```python
def test_get_top_n_returns_n_people(graph):
    for i in range(5):
        person = Person(
            person_id=f"p{i}",
            name=f"人物{i}",
            relation_type="同事",
            interaction_logs=[
                InteractionLog(date="2026-10-01", signal_id=f"s{i}", interaction_type="日常", summary="日常")
                for _ in range(i + 1)
            ],
            emotional_timeline=[EmotionalTimeline(date="2026-10-01", score=0.1 * (i + 1), trigger="test")],
        )
        graph.add_person(person)

    top = graph.get_top_n(n=3)
    assert len(top) == 3


def test_get_top_n_ranks_by_freq_and_emotion(graph):
    high = Person(
        person_id="ph",
        name="高频人",
        relation_type="同事",
        interaction_logs=[
            InteractionLog(date="2026-10-01", signal_id=f"s{i}", interaction_type="日常", summary="日常")
            for i in range(20)
        ],
        emotional_timeline=[EmotionalTimeline(date="2026-10-01", score=0.9, trigger="强情感")],
    )
    low = Person(
        person_id="pl",
        name="低频人",
        relation_type="同事",
        interaction_logs=[],
        emotional_timeline=[EmotionalTimeline(date="2026-10-01", score=0.1, trigger="弱情感")],
    )
    graph.add_person(high)
    graph.add_person(low)

    top = graph.get_top_n(n=2)
    assert top[0].name == "高频人"


def test_get_top_n_fallback_when_no_emotional_timeline(graph):
    person = Person(
        person_id="p1",
        name="无情感时序人",
        relation_type="同事",
        interaction_logs=[
            InteractionLog(date="2026-10-01", signal_id="s1", interaction_type="日常", summary="日常")
        ],
        emotional_timeline=[],
        emotional_impact="积极",
    )
    graph.add_person(person)

    top = graph.get_top_n(n=1)
    assert len(top) == 1
```

**Step 2: 运行确认失败**

```
pytest tests/unit/layers/growth/test_people_graph.py::test_get_top_n_returns_n_people -v
```
预期：`AttributeError: 'PeopleGraph' object has no attribute 'get_top_n'`

**Step 3: 实现**

在 `PeopleGraph` 类末尾追加方法：

```python
def get_top_n(self, n: int = 5) -> list[Person]:
    people = self.list_people()

    def score(p: Person) -> float:
        freq_score = min(len(p.interaction_logs) / 50, 1.0)
        if p.emotional_timeline:
            latest_emotion = abs(p.emotional_timeline[-1].score)
        else:
            _impact_map = {"积极": 0.6, "消极": 0.6, "中性": 0.3}
            latest_emotion = _impact_map.get(p.emotional_impact, 0.3)
        return freq_score * 0.5 + latest_emotion * 0.5

    return sorted(people, key=score, reverse=True)[:n]
```

**Step 4: 运行确认通过**

```
pytest tests/unit/layers/growth/test_people_graph.py -v
```
预期：全部 PASS

**Step 5: Commit**

```
git add huaqi_src/layers/growth/telos/dimensions/people/graph.py tests/unit/layers/growth/test_people_graph.py
git commit -m "feat: PeopleGraph.get_top_n with freq+emotion scoring"
```

---

## Week 2：PeoplePipeline 完整实现（第 4 条）

### Task 4：新建 PeoplePipeline

**Files:**
- Create: `huaqi_src/layers/growth/telos/dimensions/people/pipeline.py`
- Test: `tests/unit/layers/growth/test_people_pipeline.py`（新建）

**PeoplePipeline 的职责：**
1. 对 Signal 中提到的每个人名，调用 LLM 提取互动信息（一次调用提取所有人）
2. 已存在的人 → 追加 InteractionLog + EmotionalTimeline，可选更新 profile
3. 不存在的人 → 调用 PersonExtractor 建档，再追加首次互动记录

**LLM 输出格式（新 Prompt）：**

```json
[
  {
    "name": "张伟",
    "interaction_type": "合作",
    "emotional_score": 0.6,
    "summary": "一起推进了产品评审",
    "new_profile": null,
    "new_relation_type": null
  }
]
```

**Step 1: 写失败测试**

新建 `tests/unit/layers/growth/test_people_pipeline.py`：

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
from huaqi_src.layers.growth.telos.dimensions.people.pipeline import PeoplePipeline
from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph
from huaqi_src.layers.growth.telos.dimensions.people.models import Person


@pytest.fixture
def graph(tmp_path: Path) -> PeopleGraph:
    return PeopleGraph(data_dir=tmp_path)


@pytest.fixture
def signal() -> RawSignal:
    return RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=datetime.now(timezone.utc),
        content="今天和张伟一起推进了产品评审，进展很顺利。",
    )


def test_pipeline_appends_interaction_log_to_existing_person(graph, signal):
    existing = Person(person_id="p1", name="张伟", relation_type="同事")
    graph.add_person(existing)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps([
        {
            "name": "张伟",
            "interaction_type": "合作",
            "emotional_score": 0.6,
            "summary": "一起推进了产品评审",
            "new_profile": None,
            "new_relation_type": None,
        }
    ]))

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm)
    pipeline.process(signal=signal, mentioned_names=["张伟"])

    updated = graph.get_person("张伟")
    assert updated is not None
    assert len(updated.interaction_logs) == 1
    assert updated.interaction_logs[0].interaction_type == "合作"
    assert updated.interaction_logs[0].signal_id == signal.id


def test_pipeline_appends_emotional_timeline_to_existing_person(graph, signal):
    existing = Person(person_id="p1", name="张伟", relation_type="同事")
    graph.add_person(existing)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps([
        {
            "name": "张伟",
            "interaction_type": "合作",
            "emotional_score": 0.7,
            "summary": "进展顺利",
            "new_profile": None,
            "new_relation_type": None,
        }
    ]))

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm)
    pipeline.process(signal=signal, mentioned_names=["张伟"])

    updated = graph.get_person("张伟")
    assert len(updated.emotional_timeline) == 1
    assert abs(updated.emotional_timeline[0].score - 0.7) < 0.001


def test_pipeline_creates_new_person_via_extractor_when_unknown(graph, signal):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps([
        {
            "name": "新人物",
            "interaction_type": "初识",
            "emotional_score": 0.5,
            "summary": "第一次见面",
            "new_profile": "工程师",
            "new_relation_type": "同事",
        }
    ]))

    mock_extractor = MagicMock()
    new_person = Person(person_id="pnew", name="新人物", relation_type="同事", profile="工程师")
    mock_extractor.extract_from_text.return_value = [new_person]

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm, person_extractor=mock_extractor)
    pipeline.process(signal=signal, mentioned_names=["新人物"])

    mock_extractor.extract_from_text.assert_called_once()


def test_pipeline_makes_single_llm_call_for_multiple_names(graph, signal):
    for name in ["张伟", "李四"]:
        graph.add_person(Person(person_id=name, name=name, relation_type="同事"))

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps([
        {"name": "张伟", "interaction_type": "合作", "emotional_score": 0.5, "summary": "s1", "new_profile": None, "new_relation_type": None},
        {"name": "李四", "interaction_type": "日常", "emotional_score": 0.3, "summary": "s2", "new_profile": None, "new_relation_type": None},
    ]))

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm)
    pipeline.process(signal=signal, mentioned_names=["张伟", "李四"])

    assert mock_llm.invoke.call_count == 1


def test_pipeline_returns_empty_list_on_llm_parse_error(graph, signal):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="不是合法JSON")

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm)
    result = pipeline.process(signal=signal, mentioned_names=["张伟"])
    assert result == []
```

**Step 2: 运行确认失败**

```
pytest tests/unit/layers/growth/test_people_pipeline.py -v
```
预期：`ImportError: cannot import name 'PeoplePipeline'`

**Step 3: 实现**

新建 `huaqi_src/layers/growth/telos/dimensions/people/pipeline.py`：

```python
import json
import datetime
from typing import Any, List, Optional

from huaqi_src.layers.data.raw_signal.models import RawSignal
from .graph import PeopleGraph
from .models import Person, InteractionLog, EmotionalTimeline


_PROMPT = """\
分析以下信号文本，提取其中出现的人物互动信息。

信号文本：
{content}

已知人物列表（摘要）：
{known_people}

本次信号中提到的人名：{mentioned_names}

对每个提到的人物，提取：
- interaction_type: 从 [合作, 冲突, 日常, 初识, 久未联系] 中选择
- emotional_score: 此次互动对用户情感的影响，-1.0（极负面）到 1.0（极正面）
- summary: 一句话描述此次互动
- new_profile: 若发现新的画像信息（职位/性格/兴趣），填写；否则 null
- new_relation_type: 若关系类型发生变化，填写；否则 null

只返回 JSON 数组，不要其他内容：
[
  {{
    "name": "姓名",
    "interaction_type": "...",
    "emotional_score": 0.0,
    "summary": "...",
    "new_profile": null,
    "new_relation_type": null
  }}
]"""


class PeoplePipeline:
    def __init__(
        self,
        graph: PeopleGraph,
        llm: Any,
        person_extractor: Optional[Any] = None,
    ) -> None:
        self._graph = graph
        self._llm = llm
        self._extractor = person_extractor

    def _known_people_summary(self, names: List[str]) -> str:
        lines = []
        for name in names:
            person = self._graph.get_person(name)
            if person:
                lines.append(f"- {name}（{person.relation_type}）: {person.profile[:50]}")
        return "\n".join(lines) if lines else "（无已知人物）"

    def process(self, signal: RawSignal, mentioned_names: List[str]) -> List[Person]:
        if not mentioned_names:
            return []

        prompt = _PROMPT.format(
            content=signal.content,
            known_people=self._known_people_summary(mentioned_names),
            mentioned_names="、".join(mentioned_names),
        )

        try:
            response = self._llm.invoke(prompt)
            raw = response.content.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            data = json.loads(raw)
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        results: List[Person] = []
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        for item in data:
            if not isinstance(item, dict) or "name" not in item:
                continue
            name = item["name"]
            existing = self._graph.get_person(name)

            if existing is None:
                if self._extractor is not None:
                    extracted = self._extractor.extract_from_text(signal.content)
                    existing = next((p for p in extracted if p.name == name), None)
                if existing is None:
                    continue

            log = InteractionLog(
                date=today,
                signal_id=signal.id,
                interaction_type=item.get("interaction_type", "日常"),
                summary=item.get("summary", ""),
            )
            emotion = EmotionalTimeline(
                date=today,
                score=float(item.get("emotional_score", 0.0)),
                trigger=item.get("summary", ""),
            )

            updated_logs = existing.interaction_logs + [log]
            updated_emotions = existing.emotional_timeline + [emotion]

            update_kwargs: dict = {
                "interaction_logs": updated_logs,
                "emotional_timeline": updated_emotions,
            }
            if item.get("new_profile"):
                merged = f"{existing.profile}\n{item['new_profile']}".strip()
                update_kwargs["profile"] = merged
            if item.get("new_relation_type"):
                update_kwargs["relation_type"] = item["new_relation_type"]

            self._graph.update_person(name, **update_kwargs)
            updated = self._graph.get_person(name)
            if updated:
                results.append(updated)

        return results
```

**Step 4: 运行确认通过**

```
pytest tests/unit/layers/growth/test_people_pipeline.py -v
```
预期：5 个 PASS

**Step 5: 接入 DistillationPipeline**

修改 `huaqi_src/layers/data/raw_signal/pipeline.py`，将原来的 `person_extractor` 替换为支持 `people_pipeline`，同时保留 `person_extractor` 向后兼容：

在 `DistillationPipeline.__init__` 中新增 `people_pipeline` 参数：

```python
def __init__(
    self,
    signal_store: RawSignalStore,
    event_store: GrowthEventStore,
    telos_manager: TelosManager,
    engine: TelosEngine,
    signal_threshold: int = 3,
    days_window: int = 30,
    person_extractor=None,
    people_pipeline=None,
) -> None:
    self._signal_store = signal_store
    self._event_store = event_store
    self._mgr = telos_manager
    self._engine = engine
    self._threshold = signal_threshold
    self._days_window = days_window
    self._person_extractor = person_extractor
    self._people_pipeline = people_pipeline
```

在 `process` 方法中，将人物处理逻辑替换为：

```python
if step1_result.has_people:
    if self._people_pipeline is not None:
        try:
            self._people_pipeline.process(
                signal=signal,
                mentioned_names=step1_result.mentioned_names,
            )
        except Exception:
            pass
    elif self._person_extractor is not None:
        try:
            self._person_extractor.extract_from_text(signal.content)
        except Exception:
            pass
```

**Step 6: 运行所有测试确认不回归**

```
pytest tests/ -v
```

**Step 7: Commit**

```
git add huaqi_src/layers/growth/telos/dimensions/people/pipeline.py huaqi_src/layers/data/raw_signal/pipeline.py tests/unit/layers/growth/test_people_pipeline.py
git commit -m "feat: PeoplePipeline - append InteractionLog/EmotionalTimeline per signal"
```

---

## Week 3：Agent 工具层（第 2+3 条）

### Task 5：注入 search_person_tool（第 3 条）

`search_person_tool` 在 `huaqi_src/agent/tools.py` 中已实现并注册到 `_TOOL_REGISTRY`（已可使用）。

**当前问题：** `chat_nodes.py` 的 `generate_response` 调用 `chat_model.bind_tools(_TOOL_REGISTRY)`，`_TOOL_REGISTRY` 包含所有工具（包括 `search_person_tool`）。

**先确认 search_person_tool 已在 _TOOL_REGISTRY 中：**

在 `tools.py` 中搜索 `search_person_tool`，可以看到它被 `@register_tool` 装饰，已自动加入 `_TOOL_REGISTRY`。

**结论：第 3 条已实现，无需改动代码。** 运行测试确认：

```
pytest tests/ -v -k "search_person"
```

若测试中不存在 `search_person` 测试，写一个快速验证：

**Files:**
- Test: `tests/unit/agent/test_tools.py`（追加一个用例）

**Step 1: 写测试**

在 `tests/unit/agent/test_tools.py` 文件（若不存在则新建）中追加：

```python
def test_search_person_tool_in_registry():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    tool_names = [t.name for t in _TOOL_REGISTRY if hasattr(t, "name")]
    assert "search_person_tool" in tool_names
```

**Step 2: 运行确认通过**

```
pytest tests/unit/agent/test_tools.py::test_search_person_tool_in_registry -v
```
预期：PASS

**Step 3: Commit**

```
git add tests/unit/agent/test_tools.py
git commit -m "test: verify search_person_tool is registered in _TOOL_REGISTRY"
```

---

### Task 6：search_memory 工具——RawSignal 向量检索前置工程（第 2 条）

**注意：** 这是独立前置工程，建议与其他任务独立排期。

#### Subtask 6.1：RawSignal 模型新增 embedding 字段

**Files:**
- Read first: `huaqi_src/layers/data/raw_signal/models.py`（先读取，确认字段）
- Modify: `huaqi_src/layers/data/raw_signal/models.py`
- Test: `tests/unit/layers/data/test_raw_signal_models.py`（新建）

**Step 1: 先读 models.py 确认当前字段**

```
cat huaqi_src/layers/data/raw_signal/models.py
```

**Step 2: 写失败测试**

新建 `tests/unit/layers/data/test_raw_signal_models.py`：

```python
from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
from datetime import datetime, timezone


def test_raw_signal_has_embedding_field():
    signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=datetime.now(timezone.utc),
        content="测试内容",
    )
    assert hasattr(signal, "embedding")
    assert signal.embedding is None


def test_raw_signal_accepts_embedding_list():
    signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=datetime.now(timezone.utc),
        content="测试内容",
        embedding=[0.1, 0.2, 0.3],
    )
    assert signal.embedding == [0.1, 0.2, 0.3]
```

**Step 3: 在 `RawSignal` 中新增字段**

在 `models.py` 的 `RawSignal` 类中新增：

```python
from typing import Optional, List
# 在现有字段末尾添加：
embedding: Optional[List[float]] = None
```

**Step 4: 运行确认通过**

```
pytest tests/unit/layers/data/test_raw_signal_models.py -v
```

#### Subtask 6.2：RawSignalStore.search_by_embedding

**Files:**
- Read first: `huaqi_src/layers/data/raw_signal/store.py`
- Modify: `huaqi_src/layers/data/raw_signal/store.py`
- Test: `tests/unit/layers/data/test_raw_signal_store.py`（新建或追加）

**Step 1: 写失败测试**

```python
from pathlib import Path
from datetime import datetime, timezone
import pytest
from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter


@pytest.fixture
def store(tmp_path: Path) -> RawSignalStore:
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    return RawSignalStore(adapter=adapter)


def test_search_by_embedding_returns_top_k(store):
    for i in range(5):
        signal = RawSignal(
            user_id="u1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content=f"内容{i}",
            embedding=[float(i), 0.0, 0.0],
        )
        store.save(signal)

    query_vec = [4.0, 0.0, 0.0]
    results = store.search_by_embedding(user_id="u1", query_vec=query_vec, top_k=2)
    assert len(results) <= 2
    assert all(hasattr(r, "content") for r in results)


def test_search_by_embedding_returns_empty_when_no_embeddings(store):
    signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=datetime.now(timezone.utc),
        content="无向量内容",
    )
    store.save(signal)

    results = store.search_by_embedding(user_id="u1", query_vec=[1.0, 0.0], top_k=3)
    assert results == []
```

**Step 2: 运行确认失败**

```
pytest tests/unit/layers/data/test_raw_signal_store.py -v
```

**Step 3: 在 store.py 中实现 search_by_embedding**

先读 `huaqi_src/layers/data/raw_signal/store.py` 了解存储接口，然后新增方法。

余弦相似度计算（无需引入新依赖）：

```python
def _cosine_sim(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def search_by_embedding(
    self,
    user_id: str,
    query_vec: list[float],
    top_k: int = 5,
) -> list[RawSignal]:
    all_signals = self.query(RawSignalFilter(user_id=user_id, limit=1000))
    candidates = [s for s in all_signals if s.embedding is not None]
    if not candidates:
        return []
    scored = [(s, _cosine_sim(query_vec, s.embedding)) for s in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in scored[:top_k]]
```

**Step 4: 运行确认通过**

```
pytest tests/unit/layers/data/test_raw_signal_store.py -v
```

#### Subtask 6.3：search_memory_tool 实现

**Files:**
- Modify: `huaqi_src/agent/tools.py`
- Test: `tests/unit/agent/test_tools.py`（追加）

**Step 1: 写失败测试**

```python
def test_search_memory_tool_in_registry():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    tool_names = [t.name for t in _TOOL_REGISTRY if hasattr(t, "name")]
    assert "search_memory_tool" in tool_names
```

**Step 2: 运行确认失败**

```
pytest tests/unit/agent/test_tools.py::test_search_memory_tool_in_registry -v
```

**Step 3: 实现 search_memory_tool**

在 `huaqi_src/agent/tools.py` 中，在 `search_person_tool` 后面追加：

```python
@register_tool
@tool
def search_memory_tool(query: str) -> str:
    """语义检索用户的原始日记/笔记内容（RawSignal 原文）。
    当用户询问「我之前记录过什么」「我写过关于XX的内容」时使用。
    与 search_diary_tool 的区别：本工具检索所有来源的原始记录，包括自动采集的信号。
    """
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    from huaqi_src.layers.data.memory.vector import get_embedding_service
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.config.paths import get_data_dir

    data_dir = get_data_dir()
    if data_dir is None:
        return f"未找到关于 '{query}' 的记忆（数据目录未设置）。"

    try:
        embedder = get_embedding_service()
        query_vec = embedder.encode(query)
        query_vec_list = query_vec.tolist() if hasattr(query_vec, "tolist") else list(query_vec)

        adapter = SQLiteStorageAdapter(db_path=data_dir / "raw_signals.db")
        store = RawSignalStore(adapter=adapter)
        results = store.search_by_embedding(user_id="default", query_vec=query_vec_list, top_k=5)

        if not results:
            return f"未找到关于 '{query}' 的相关记忆。"

        formatted = [f"[{r.timestamp.strftime('%Y-%m-%d')}] {r.content[:200]}" for r in results]
        return "找到以下相关记忆：\n\n" + "\n---\n".join(formatted)
    except Exception as e:
        return f"记忆检索失败：{str(e)[:100]}"
```

**Step 4: 运行确认通过**

```
pytest tests/unit/agent/test_tools.py -v
```

**Step 5: Commit**

```
git add huaqi_src/layers/data/raw_signal/models.py huaqi_src/layers/data/raw_signal/store.py huaqi_src/agent/tools.py tests/
git commit -m "feat: search_memory_tool with RawSignal embedding vector search"
```

---

## Week 4：asyncio 全链路改造（第 1 条）

**改造目标：** `TelosEngine.step345_combined` → `async def`，`DistillationPipeline.process` 内各维度并行执行。

**改造范围总览：**

| 文件 | 改动 |
|------|------|
| `huaqi_src/layers/growth/telos/engine.py` | `step345_combined` → `async def`，`self._llm.invoke` → `self._llm.ainvoke` |
| `huaqi_src/layers/data/raw_signal/pipeline.py` | `process` → `async def`，维度循环改 `asyncio.gather` |
| `huaqi_src/layers/growth/telos/dimensions/people/pipeline.py` | `process` → `async def`，`self._llm.invoke` → `self._llm.ainvoke` |
| `huaqi_src/layers/growth/telos/manager.py` | 新增 `_meta_lock: asyncio.Lock`，`update` 保持同步 |
| 所有相关测试文件 | `mock_llm.invoke` → `mock_llm.ainvoke`（AsyncMock），`async def test_*` |

### Task 7：TelosEngine.step345_combined 改为 async

**Files:**
- Modify: `huaqi_src/layers/growth/telos/engine.py`
- Test: `tests/unit/layers/growth/test_telos_engine.py`（修改现有测试）

**Step 1: 写失败测试**

在 `tests/unit/layers/growth/test_telos_engine.py` 的 `TestStep345Combined` 类中，将所有测试改为 `async def`，并将 `mock_llm.invoke` 改为 `AsyncMock`：

```python
from unittest.mock import AsyncMock

class TestStep345Combined:
    async def test_step345_single_llm_call(self, telos_manager, mock_combined_step):
        import json
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps(mock_combined_step)))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = await engine.step345_combined(
            dimension="challenges",
            signal_summaries=["摘要1", "摘要2", "摘要3"],
            days=30,
            recent_signal_count=5,
        )

        assert mock_llm.ainvoke.call_count == 1
        assert result.should_update is True
        assert result.is_growth_event is True

    async def test_step345_calculates_confidence_correctly(self, telos_manager, mock_combined_step):
        import json
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps(mock_combined_step)))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = await engine.step345_combined(
            dimension="challenges",
            signal_summaries=["摘要"],
            days=30,
            recent_signal_count=5,
        )

        expected_count_score = min(5 / 10, 1.0)
        expected_confidence = expected_count_score * 0.4 + 0.8 * 0.6
        assert abs(result.confidence - expected_confidence) < 0.001

    async def test_step345_updates_manager_when_should_update(self, telos_manager, mock_combined_step):
        import json
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps(mock_combined_step)))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        await engine.step345_combined(
            dimension="challenges",
            signal_summaries=["摘要"],
            days=30,
            recent_signal_count=3,
        )

        dim = telos_manager.get("challenges")
        assert dim.update_count == 1
        assert "目标感缺失" in dim.content
```

**Step 2: 运行确认失败**

```
pytest tests/unit/layers/growth/test_telos_engine.py::TestStep345Combined -v
```
预期：FAIL，`step345_combined` 是同步方法，`await` 报错

**Step 3: 将 step345_combined 改为 async**

在 `huaqi_src/layers/growth/telos/engine.py` 中：

```python
async def step345_combined(
    self,
    dimension: str,
    signal_summaries: List[str],
    days: int,
    recent_signal_count: int,
) -> CombinedStepOutput:
    dim = self._mgr.get(dimension)
    prompt = _STEP345_COMBINED_PROMPT.format(
        telos_index=self._telos_index(),
        days=days,
        dimension=dimension,
        count=len(signal_summaries),
        signal_summaries="\n".join(f"- {s}" for s in signal_summaries),
        current_content=dim.content,
    )
    response = await self._llm.ainvoke(prompt)
    data = _parse_json(response.content)
    result = CombinedStepOutput(**data)

    count_score = min(recent_signal_count / 10, 1.0)
    consistency_score = result.consistency_score
    result.confidence = count_score * 0.4 + consistency_score * 0.6

    if result.should_update and result.new_content and result.history_entry:
        version = dim.update_count + 1
        entry = HistoryEntry(
            version=version,
            change=result.history_entry["change"],
            trigger=result.history_entry["trigger"],
            confidence=result.confidence,
            updated_at=datetime.now(timezone.utc),
        )
        self._mgr.update(
            name=dimension,
            new_content=result.new_content,
            history_entry=entry,
            confidence=result.confidence,
        )

    return result
```

**Step 4: 运行确认通过**

```
pytest tests/unit/layers/growth/test_telos_engine.py::TestStep345Combined -v
```

**Step 5: 确认其他测试不回归**

```
pytest tests/unit/layers/growth/test_telos_engine.py -v
```

---

### Task 8：DistillationPipeline.process 改为 async + asyncio.gather

**Files:**
- Modify: `huaqi_src/layers/data/raw_signal/pipeline.py`
- Modify: `huaqi_src/layers/growth/telos/manager.py`（新增 `_meta_lock`）
- Test: `tests/unit/layers/data/test_raw_signal_pipeline.py`（修改现有测试）

**Step 1: 修改 process 为 async**

修改 `tests/unit/layers/data/test_raw_signal_pipeline.py`，将调用 `pipeline.process` 的测试改为 `async def`：

```python
async def test_pipeline_step2_only_queries_within_days_window(tmp_path):
    pipeline, store = make_pipeline(tmp_path, days_window=7)
    # ... 同原来，但最后一行改为：
    result = await pipeline.process(new_signal)
    assert result["pipeline_runs"] == []


async def test_pipeline_strong_signal_bypasses_threshold(tmp_path):
    # ... 同原来，但最后一行改为：
    result = await pipeline.process(signal)
    assert len(result["pipeline_runs"]) > 0
```

同样修改 `TestDistillationPipelineCombinedStep` 和 `TestPeoplePipelineFork` 中调用 `pipeline.process` 的测试。

**Step 2: 运行确认失败**

```
pytest tests/unit/layers/data/test_raw_signal_pipeline.py -v
```

**Step 3: 实现 async process**

修改 `huaqi_src/layers/data/raw_signal/pipeline.py`：

```python
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.layers.growth.telos.engine import TelosEngine, SignalStrength
from huaqi_src.layers.growth.telos.growth_events import GrowthEvent, GrowthEventStore
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSION_LAYERS


class DistillationPipeline:

    def __init__(
        self,
        signal_store: RawSignalStore,
        event_store: GrowthEventStore,
        telos_manager: TelosManager,
        engine: TelosEngine,
        signal_threshold: int = 3,
        days_window: int = 30,
        person_extractor=None,
        people_pipeline=None,
    ) -> None:
        self._signal_store = signal_store
        self._event_store = event_store
        self._mgr = telos_manager
        self._engine = engine
        self._threshold = signal_threshold
        self._days_window = days_window
        self._person_extractor = person_extractor
        self._people_pipeline = people_pipeline

    async def process(self, signal: RawSignal) -> Dict[str, Any]:
        step1_result = self._engine.step1_analyze(signal)
        self._signal_store.mark_processed(signal.id)

        if step1_result.has_people:
            if self._people_pipeline is not None:
                try:
                    await self._people_pipeline.process(
                        signal=signal,
                        mentioned_names=step1_result.mentioned_names,
                    )
                except Exception:
                    pass
            elif self._person_extractor is not None:
                try:
                    self._person_extractor.extract_from_text(signal.content)
                except Exception:
                    pass

        results: Dict[str, Any] = {
            "signal_id": signal.id,
            "step1": step1_result,
            "pipeline_runs": [],
        }

        since = datetime.now(timezone.utc) - timedelta(days=self._days_window)
        is_strong = step1_result.signal_strength == SignalStrength.STRONG

        count = self._signal_store.count(
            RawSignalFilter(user_id=signal.user_id, processed=1, since=since)
        )

        if not is_strong and count < self._threshold:
            return results

        recent_signals = self._signal_store.query(
            RawSignalFilter(user_id=signal.user_id, processed=1, since=since, limit=self._threshold * 3)
        )

        async def process_dimension(dimension: str) -> Dict[str, Any]:
            summaries = [s.content[:80] for s in recent_signals if dimension in (s.metadata or {})]
            if not summaries:
                summaries = [s.content[:80] for s in recent_signals[:self._threshold]]

            combined_result = await self._engine.step345_combined(
                dimension=dimension,
                signal_summaries=summaries,
                days=self._days_window,
                recent_signal_count=count,
            )

            run_result: Dict[str, Any] = {
                "updated": combined_result.should_update,
                "growth_event": None,
            }

            if combined_result.should_update and combined_result.is_growth_event:
                dim = self._mgr.get(dimension)
                layer = STANDARD_DIMENSION_LAYERS.get(dimension)
                event = GrowthEvent(
                    user_id=signal.user_id,
                    dimension=dimension,
                    layer=layer.value if layer else "surface",
                    title=combined_result.growth_title or "",
                    narrative=combined_result.growth_narrative or "",
                    new_content=dim.content,
                    trigger_signals=[signal.id],
                    occurred_at=signal.timestamp,
                )
                self._event_store.save(event)
                run_result["growth_event"] = combined_result
                run_result["saved_event"] = event

            return run_result

        tasks = [process_dimension(dim) for dim in step1_result.dimensions]
        pipeline_runs = await asyncio.gather(*tasks, return_exceptions=False)
        results["pipeline_runs"] = list(pipeline_runs)

        return results
```

**Step 4: 修改 TelosManager 新增 _meta_lock**

在 `huaqi_src/layers/growth/telos/manager.py` 的 `__init__` 中新增 `asyncio.Lock`：

```python
import asyncio

class TelosManager:
    def __init__(self, telos_dir: Path, git_commit: bool = True) -> None:
        self._dir = telos_dir
        self._git_commit = git_commit
        self._meta_lock: asyncio.Lock = asyncio.Lock()
```

注意：`update` 方法本身保持同步（文件写入在此规模下不是瓶颈），但写入 `meta.md` 可在调用方用 `async with manager._meta_lock` 保护（暂时无需改动，锁仅备用）。

**Step 5: 运行确认通过**

```
pytest tests/unit/layers/data/test_raw_signal_pipeline.py -v
pytest tests/ -v
```

**Step 6: Commit**

```
git add huaqi_src/layers/growth/telos/engine.py huaqi_src/layers/data/raw_signal/pipeline.py huaqi_src/layers/growth/telos/manager.py tests/
git commit -m "feat: asyncio full pipeline - step345_combined and DistillationPipeline.process are now async"
```

---

### Task 9：PeoplePipeline.process 改为 async（配合全链路）

**Files:**
- Modify: `huaqi_src/layers/growth/telos/dimensions/people/pipeline.py`
- Test: `tests/unit/layers/growth/test_people_pipeline.py`（修改）

**Step 1: 修改测试为 async**

将 `test_people_pipeline.py` 中所有调用 `pipeline.process(...)` 的测试改为 `async def`，并将 `mock_llm.invoke` 改为 `AsyncMock`：

```python
from unittest.mock import AsyncMock

async def test_pipeline_appends_interaction_log_to_existing_person(graph, signal):
    existing = Person(person_id="p1", name="张伟", relation_type="同事")
    graph.add_person(existing)

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps([
        {
            "name": "张伟",
            "interaction_type": "合作",
            "emotional_score": 0.6,
            "summary": "一起推进了产品评审",
            "new_profile": None,
            "new_relation_type": None,
        }
    ])))

    pipeline = PeoplePipeline(graph=graph, llm=mock_llm)
    await pipeline.process(signal=signal, mentioned_names=["张伟"])

    updated = graph.get_person("张伟")
    assert updated is not None
    assert len(updated.interaction_logs) == 1
```

其他测试同样改为 `async def` + `await`，并将 `mock_llm.invoke` 全改为 `mock_llm.ainvoke = AsyncMock(...)`。

**Step 2: 运行确认失败**

```
pytest tests/unit/layers/growth/test_people_pipeline.py -v
```

**Step 3: 将 PeoplePipeline.process 改为 async**

修改 `pipeline.py` 中的 `process` 方法签名和 LLM 调用：

```python
async def process(self, signal: RawSignal, mentioned_names: List[str]) -> List[Person]:
    if not mentioned_names:
        return []

    prompt = _PROMPT.format(
        content=signal.content,
        known_people=self._known_people_summary(mentioned_names),
        mentioned_names="、".join(mentioned_names),
    )

    try:
        response = await self._llm.ainvoke(prompt)
        # ... 其余逻辑不变
```

**Step 4: 运行确认通过**

```
pytest tests/unit/layers/growth/test_people_pipeline.py -v
pytest tests/ -v
```

**Step 5: Commit**

```
git add huaqi_src/layers/growth/telos/dimensions/people/pipeline.py tests/unit/layers/growth/test_people_pipeline.py
git commit -m "feat: PeoplePipeline.process is now async"
```

---

### Task 10：修改 distillation_job.py 和 review_job.py 的入口

**Files:**
- Read first: `huaqi_src/scheduler/distillation_job.py`（先确认现状）
- Read first: `huaqi_src/scheduler/review_job.py`
- Modify: `huaqi_src/scheduler/distillation_job.py`（若已存在）

**Step 1: 确认入口是否已有 asyncio.run()**

读取 `huaqi_src/scheduler/distillation_job.py` 和 `huaqi_src/scheduler/review_job.py`，确认 `pipeline.process(signal)` 的调用处。

**Step 2: 将同步调用包裹为 asyncio.run()**

若文件中有类似：

```python
result = pipeline.process(signal)
```

改为：

```python
import asyncio
result = asyncio.run(pipeline.process(signal))
```

若调用者已在异步上下文（如 `async def run_distillation_job`），则改为：

```python
result = await pipeline.process(signal)
```

**Step 3: 运行全量测试确认无回归**

```
pytest tests/ -v
```

**Step 4: Commit**

```
git add huaqi_src/scheduler/distillation_job.py huaqi_src/scheduler/review_job.py
git commit -m "feat: scheduler jobs use asyncio.run/await for async pipeline.process"
```

---

## 验收清单

完成全部 Task 后，运行以下命令确认所有测试通过：

```
pytest tests/ -v --tb=short
```

预期：
- `tests/unit/layers/growth/test_people_models.py` — 全部 PASS
- `tests/unit/layers/growth/test_people_graph.py` — 全部 PASS
- `tests/unit/layers/growth/test_people_pipeline.py` — 全部 PASS
- `tests/unit/layers/growth/test_telos_engine.py` — 全部 PASS（含 async Step345）
- `tests/unit/layers/data/test_raw_signal_pipeline.py` — 全部 PASS（含 async process）
- `tests/unit/agent/test_tools.py` — 全部 PASS（含 search_person + search_memory 注册确认）
- 原有测试（test_telos_manager, test_telos_models 等）— 不回归

---

## 快速参考：关键接口

```python
# Task 1 新增数据类
InteractionLog(date, signal_id, interaction_type, summary)
EmotionalTimeline(date, score, trigger)
Person(..., interaction_logs=[], emotional_timeline=[])

# Task 2 新增方法
PeopleGraph.get_top_n(n=5) -> list[Person]

# Task 4 新增类
PeoplePipeline(graph, llm, person_extractor=None)
await pipeline.process(signal, mentioned_names) -> list[Person]

# Task 7 改为 async
await engine.step345_combined(dimension, signal_summaries, days, recent_signal_count)

# Task 8 改为 async
await distillation_pipeline.process(signal) -> dict

# Task 6 新工具
search_memory_tool(query: str) -> str
```
