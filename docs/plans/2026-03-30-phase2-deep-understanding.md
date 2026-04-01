# Phase 2 深度理解实施计划

**Goal:** 构建人物关系引擎（PeopleGraph + PersonExtractor）并升级成长报告体系，支持日/周/季/年四档报告

**Architecture:** 新增 `huaqi_src/people/` 模块存储人物画像（Markdown + SQLite），PersonExtractor 用 LLM 从对话/日记中自动提取人物信息；报告体系在现有 `morning_brief.py` 模式上扩展出 `DailyReportAgent`、`WeeklyReportAgent`、`QuarterlyReportAgent`；每个新数据类型对应一个新 Tool 注册到 LangGraph Agent

**Tech Stack:** Python dataclasses, LangGraph (现有), SQLite (现有 `db_storage.py`), `langchain_core.tools.tool` 装饰器, pytest + `tmp_path`, Typer CLI (现有)

---

## 前置阅读（必读，5 分钟）

在开始编码前，先浏览以下文件了解约定：

- `huaqi_src/collectors/document.py` — HuaqiDocument 数据模型（所有文档的基类）
- `huaqi_src/agent/tools.py` — Tool 如何用 `@tool` 装饰器定义
- `huaqi_src/agent/graph/chat.py` — 如何把 Tool 注册进 LangGraph 图
- `huaqi_src/reports/morning_brief.py` — 报告 Agent 的现有模式（`_build_context` + `_generate_brief` + `run`）
- `huaqi_src/scheduler/jobs.py` — 如何注册定时任务
- `huaqi_src/core/config_paths.py` — `require_data_dir()` 获取数据目录，测试时用 `tmp_path`
- `tests/reports/test_morning_brief.py` — 测试中如何 mock LLM 调用（`patch.object(agent, "_generate_brief", ...)`）

运行测试命令：`pytest tests/ -v`

---

## Task 1: 人物数据模型

**文件：**
- 创建: `huaqi_src/people/__init__.py`
- 创建: `huaqi_src/people/models.py`
- 测试: `tests/people/__init__.py`
- 测试: `tests/people/test_models.py`

**Step 1: 写失败测试**

```python
# tests/people/test_models.py
import datetime
from huaqi_src.people.models import Person, Relation

def test_person_creation():
    p = Person(
        person_id="zhangsan-001",
        name="张三",
        relation_type="同事",
    )
    assert p.person_id == "zhangsan-001"
    assert p.name == "张三"
    assert p.alias == []
    assert p.profile == ""
    assert p.emotional_impact == "中性"
    assert p.interaction_frequency == 0
    assert p.notes == ""

def test_person_to_dict():
    p = Person(
        person_id="lisi-001",
        name="李四",
        relation_type="朋友",
        alias=["小李"],
        profile="直接说结论，技术能力强",
        emotional_impact="积极",
        interaction_frequency=5,
    )
    d = p.to_dict()
    assert d["name"] == "李四"
    assert d["alias"] == ["小李"]
    assert d["emotional_impact"] == "积极"

def test_relation_creation():
    r = Relation(
        from_person_id="me",
        to_person_id="zhangsan-001",
        relation_strength=75,
        topics=["技术", "项目"],
        history_summary="认识3年，合作密切",
    )
    assert r.relation_strength == 75
    assert "技术" in r.topics

def test_relation_to_dict():
    r = Relation(
        from_person_id="me",
        to_person_id="lisi-001",
        relation_strength=50,
    )
    d = r.to_dict()
    assert d["from_person_id"] == "me"
    assert d["relation_strength"] == 50
```

**Step 2: 运行测试，确认失败**

```
pytest tests/people/test_models.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.people'`

**Step 3: 创建空 `__init__.py`**

```python
# huaqi_src/people/__init__.py
```

```python
# tests/people/__init__.py
```

**Step 4: 实现 `models.py`**

```python
# huaqi_src/people/models.py
import datetime
from dataclasses import dataclass, field
from typing import Any


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
        }


@dataclass
class Relation:
    from_person_id: str
    to_person_id: str
    relation_strength: int = 50
    topics: list[str] = field(default_factory=list)
    history_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_person_id": self.from_person_id,
            "to_person_id": self.to_person_id,
            "relation_strength": self.relation_strength,
            "topics": self.topics,
            "history_summary": self.history_summary,
        }
```

**Step 5: 运行测试，确认通过**

```
pytest tests/people/test_models.py -v
```

预期：4 个测试全部 PASS

**Step 6: 提交**

```
git add huaqi_src/people/ tests/people/
git commit -m "feat: add people data models (Person, Relation)"
```

---

## Task 2: PeopleGraph（人物存储层）

**文件：**
- 创建: `huaqi_src/people/graph.py`
- 修改: `tests/people/test_models.py` → 新增 `tests/people/test_graph.py`

**背景：**
存储策略与现有系统保持一致（参考 `huaqi_src/world/storage.py`）：
- Markdown 文件存 `data_dir/people/{name}.md`，人类可读
- 方法签名遵循 `WorldNewsStorage` 的同种风格

**Step 1: 写失败测试**

```python
# tests/people/test_graph.py
import datetime
import pytest
from huaqi_src.people.graph import PeopleGraph
from huaqi_src.people.models import Person, Relation


def test_add_and_get_person(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    person = Person(
        person_id="zhangsan-001",
        name="张三",
        relation_type="同事",
        profile="喜欢直接说结论",
    )
    graph.add_person(person)
    result = graph.get_person("张三")
    assert result is not None
    assert result.name == "张三"
    assert result.profile == "喜欢直接说结论"


def test_add_person_creates_markdown_file(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    person = Person(person_id="lisi-001", name="李四", relation_type="朋友")
    graph.add_person(person)
    md_file = tmp_path / "people" / "李四.md"
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "李四" in content
    assert "朋友" in content


def test_list_people(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(person_id="p1", name="张三", relation_type="同事"))
    graph.add_person(Person(person_id="p2", name="李四", relation_type="朋友"))
    people = graph.list_people()
    names = [p.name for p in people]
    assert "张三" in names
    assert "李四" in names


def test_update_person(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    person = Person(person_id="p1", name="张三", relation_type="同事", notes="")
    graph.add_person(person)
    graph.update_person("张三", notes="喜欢喝咖啡", interaction_frequency=10)
    updated = graph.get_person("张三")
    assert updated.notes == "喜欢喝咖啡"
    assert updated.interaction_frequency == 10


def test_delete_person(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(person_id="p1", name="张三", relation_type="同事"))
    graph.delete_person("张三")
    assert graph.get_person("张三") is None
    assert not (tmp_path / "people" / "张三.md").exists()


def test_search_person(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="p1", name="张三", relation_type="同事",
        profile="Python 专家，喜欢开源"
    ))
    graph.add_person(Person(
        person_id="p2", name="李四", relation_type="朋友",
        profile="设计师，喜欢摄影"
    ))
    results = graph.search("Python")
    assert len(results) >= 1
    assert results[0].name == "张三"
```

**Step 2: 运行测试，确认失败**

```
pytest tests/people/test_graph.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.people.graph'`

**Step 3: 实现 `graph.py`**

```python
# huaqi_src/people/graph.py
import json
import datetime
from pathlib import Path
from typing import Optional

from .models import Person, Relation


class PeopleGraph:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from huaqi_src.core.config_paths import require_data_dir
            data_dir = require_data_dir()
        self._people_dir = Path(data_dir) / "people"
        self._people_dir.mkdir(parents=True, exist_ok=True)

    def _person_file(self, name: str) -> Path:
        return self._people_dir / f"{name}.md"

    def _write_markdown(self, person: Person) -> None:
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
            f"<!-- person_id: {person.person_id} -->",
            f"<!-- alias: {json.dumps(person.alias, ensure_ascii=False)} -->",
            f"<!-- created_at: {person.created_at} -->",
            f"<!-- updated_at: {person.updated_at} -->",
        ]
        self._person_file(person.name).write_text(
            "\n".join(lines), encoding="utf-8"
        )

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
            for line in lines:
                if line.startswith(f"**{label}:**"):
                    return line.split("**:", 1)[1].strip()
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
        )

    def add_person(self, person: Person) -> None:
        self._write_markdown(person)

    def get_person(self, name: str) -> Optional[Person]:
        return self._read_markdown(name)

    def list_people(self) -> list[Person]:
        people = []
        for f in sorted(self._people_dir.glob("*.md")):
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

**Step 4: 运行测试，确认通过**

```
pytest tests/people/test_graph.py -v
```

预期：6 个测试全部 PASS

**Step 5: 提交**

```
git add huaqi_src/people/graph.py tests/people/test_graph.py
git commit -m "feat: implement PeopleGraph with Markdown storage"
```

---

## Task 3: PersonExtractor（LLM 自动提取人物信息）

**文件：**
- 创建: `huaqi_src/people/extractor.py`
- 测试: `tests/people/test_extractor.py`

**背景：**
PersonExtractor 接收文本（对话/日记），调用 LLM 提取人物信息并写入 PeopleGraph。
测试时 mock LLM，不发真实请求——和 `test_morning_brief.py` 里用 `patch.object` 的方式一致。

**Step 1: 写失败测试**

```python
# tests/people/test_extractor.py
import pytest
from unittest.mock import patch, MagicMock
from huaqi_src.people.extractor import PersonExtractor
from huaqi_src.people.graph import PeopleGraph


def test_extract_from_text_returns_list(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    extractor = PersonExtractor(graph=graph)

    fake_llm_output = """[
      {
        "name": "张三",
        "relation_type": "同事",
        "profile": "技术负责人，逻辑清晰",
        "emotional_impact": "积极",
        "alias": []
      }
    ]"""

    with patch.object(extractor, "_call_llm", return_value=fake_llm_output):
        extracted = extractor.extract_from_text(
            "今天和张三开了个项目会议，他是技术负责人，表现很好"
        )

    assert len(extracted) == 1
    assert extracted[0].name == "张三"
    assert extracted[0].relation_type == "同事"


def test_extract_saves_to_graph(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    extractor = PersonExtractor(graph=graph)

    fake_llm_output = """[
      {
        "name": "李四",
        "relation_type": "朋友",
        "profile": "设计师",
        "emotional_impact": "中性",
        "alias": ["小李"]
      }
    ]"""

    with patch.object(extractor, "_call_llm", return_value=fake_llm_output):
        extractor.extract_from_text("和李四吃饭，他是设计师")

    person = graph.get_person("李四")
    assert person is not None
    assert "设计师" in person.profile


def test_extract_merges_existing_person(tmp_path):
    from huaqi_src.people.models import Person
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="zhangsan-001",
        name="张三",
        relation_type="同事",
        profile="Python 专家",
        interaction_frequency=3,
    ))

    extractor = PersonExtractor(graph=graph)
    fake_llm_output = """[
      {
        "name": "张三",
        "relation_type": "同事",
        "profile": "Python 专家，喜欢开源",
        "emotional_impact": "积极",
        "alias": []
      }
    ]"""

    with patch.object(extractor, "_call_llm", return_value=fake_llm_output):
        extractor.extract_from_text("张三今天分享了一个开源项目")

    person = graph.get_person("张三")
    assert person.interaction_frequency == 4


def test_extract_handles_invalid_llm_output(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    extractor = PersonExtractor(graph=graph)

    with patch.object(extractor, "_call_llm", return_value="这不是JSON"):
        result = extractor.extract_from_text("随意的文本")

    assert result == []
```

**Step 2: 运行测试，确认失败**

```
pytest tests/people/test_extractor.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.people.extractor'`

**Step 3: 实现 `extractor.py`**

```python
# huaqi_src/people/extractor.py
import json
import uuid
from typing import Optional

from .graph import PeopleGraph
from .models import Person


_EXTRACT_PROMPT = """\
分析以下文本，提取其中出现的人物信息。只提取明确出现的真实人物（不包括"我"/"用户"）。

文本：
{text}

请以 JSON 数组格式返回，每个元素包含：
- name: 姓名（字符串）
- relation_type: 关系类型，从 [家人, 朋友, 同事, 导师, 合作者, 其他] 中选择
- profile: 从文本中提取到的性格/职业/兴趣描述（字符串，可为空）
- emotional_impact: 此人对用户的情感影响，从 [积极, 中性, 消极] 中选择
- alias: 别名列表（数组）

如果文本中没有明确的人物，返回空数组 []。

只返回 JSON，不要其他内容。"""


class PersonExtractor:
    def __init__(self, graph: Optional[PeopleGraph] = None):
        if graph is None:
            graph = PeopleGraph()
        self._graph = graph

    def _call_llm(self, text: str) -> str:
        from huaqi_src.cli.context import build_llm_manager
        llm_mgr = build_llm_manager(temperature=0.2, max_tokens=1000)
        if llm_mgr is None:
            return "[]"

        active_name = llm_mgr.get_active_provider()
        if not active_name:
            return "[]"
        cfg = llm_mgr._configs[active_name]

        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        llm = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.2,
            max_tokens=1000,
        )
        prompt = _EXTRACT_PROMPT.format(text=text)
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content

    def extract_from_text(self, text: str) -> list[Person]:
        raw = self._call_llm(text)
        try:
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        extracted = []
        for item in data:
            if not isinstance(item, dict) or "name" not in item:
                continue
            name = item["name"]
            existing = self._graph.get_person(name)
            if existing is not None:
                new_profile = item.get("profile", "")
                if new_profile and new_profile not in existing.profile:
                    merged_profile = f"{existing.profile}\n{new_profile}".strip()
                else:
                    merged_profile = existing.profile
                self._graph.update_person(
                    name,
                    profile=merged_profile,
                    interaction_frequency=existing.interaction_frequency + 1,
                )
                extracted.append(self._graph.get_person(name))
            else:
                person = Person(
                    person_id=f"{name}-{uuid.uuid4().hex[:8]}",
                    name=name,
                    relation_type=item.get("relation_type", "其他"),
                    profile=item.get("profile", ""),
                    emotional_impact=item.get("emotional_impact", "中性"),
                    alias=item.get("alias", []),
                )
                self._graph.add_person(person)
                extracted.append(person)

        return extracted
```

**Step 4: 运行测试，确认通过**

```
pytest tests/people/test_extractor.py -v
```

预期：4 个测试全部 PASS

**Step 5: 提交**

```
git add huaqi_src/people/extractor.py tests/people/test_extractor.py
git commit -m "feat: implement PersonExtractor with LLM-based extraction"
```

---

## Task 4: 人物相关 Tools（供 Agent 调用）

**文件：**
- 修改: `huaqi_src/agent/tools.py`
- 修改: `huaqi_src/agent/graph/chat.py`（注册新 Tool）
- 测试: `tests/agent/test_tools.py`

**Step 1: 写失败测试**

在 `tests/agent/test_tools.py` 末尾追加：

```python
from huaqi_src.agent.tools import search_person_tool, get_relationship_map_tool

def test_search_person_tool_returns_string_when_no_data():
    result = search_person_tool.invoke({"name": "不存在的人xyz"})
    assert isinstance(result, str)
    assert "未找到" in result

def test_get_relationship_map_tool_returns_string():
    result = get_relationship_map_tool.invoke({})
    assert isinstance(result, str)
```

**Step 2: 运行测试，确认失败**

```
pytest tests/agent/test_tools.py -v
```

预期：`ImportError: cannot import name 'search_person_tool'`

**Step 3: 在 `tools.py` 中新增两个 Tool**

在 `huaqi_src/agent/tools.py` 末尾追加：

```python
@tool
def search_person_tool(name: str) -> str:
    """查询某人的画像和互动历史。当用户询问某个人的信息、与某人的关系、某人的性格特点时使用。"""
    from huaqi_src.people.graph import PeopleGraph
    try:
        graph = PeopleGraph()
    except RuntimeError:
        return f"未找到 '{name}' 的相关信息（数据目录未设置）。"

    person = graph.get_person(name)
    if person is None:
        results = graph.search(name)
        if not results:
            return f"未找到 '{name}' 的相关信息。"
        person = results[0]

    lines = [
        f"姓名: {person.name}",
        f"关系类型: {person.relation_type}",
        f"情感倾向: {person.emotional_impact}（huaqi 的观察）",
        f"近30天互动次数: {person.interaction_frequency}",
    ]
    if person.alias:
        lines.append(f"别名: {', '.join(person.alias)}")
    if person.profile:
        lines.append(f"画像: {person.profile}")
    if person.notes:
        lines.append(f"备注: {person.notes}")

    return "\n".join(lines)


@tool
def get_relationship_map_tool() -> str:
    """获取用户的关系网络全图，按亲密度排序列出所有关系人。当用户询问「我认识哪些人」「我的社交圈」时使用。"""
    from huaqi_src.people.graph import PeopleGraph
    try:
        graph = PeopleGraph()
    except RuntimeError:
        return "暂无关系人数据（数据目录未设置）。"

    people = graph.list_people()
    if not people:
        return "暂无关系人数据。"

    people.sort(key=lambda p: p.interaction_frequency, reverse=True)
    lines = ["你的关系网络：", ""]
    for p in people:
        line = f"- {p.name}（{p.relation_type}）"
        if p.interaction_frequency > 0:
            line += f"，近30天互动 {p.interaction_frequency} 次"
        if p.emotional_impact != "中性":
            line += f"，{p.emotional_impact}影响"
        lines.append(line)

    return "\n".join(lines)
```

**Step 4: 把新 Tool 注册到 `chat.py`**

在 `huaqi_src/agent/graph/chat.py` 中修改：

找到这行：
```python
from ..tools import search_diary_tool, search_events_tool, search_work_docs_tool, search_worldnews_tool
```

改为：
```python
from ..tools import (
    search_diary_tool,
    search_events_tool,
    search_work_docs_tool,
    search_worldnews_tool,
    search_person_tool,
    get_relationship_map_tool,
)
```

找到这行：
```python
tools = [search_diary_tool, search_events_tool, search_work_docs_tool, search_worldnews_tool]
```

改为：
```python
tools = [
    search_diary_tool,
    search_events_tool,
    search_work_docs_tool,
    search_worldnews_tool,
    search_person_tool,
    get_relationship_map_tool,
]
```

**Step 5: 运行测试，确认通过**

```
pytest tests/agent/test_tools.py -v
```

预期：所有测试 PASS

**Step 6: 提交**

```
git add huaqi_src/agent/tools.py huaqi_src/agent/graph/chat.py tests/agent/test_tools.py
git commit -m "feat: add search_person_tool and get_relationship_map_tool"
```

---

## Task 5: People CLI 命令

**文件：**
- 创建: `huaqi_src/cli/commands/people.py`
- 修改: `huaqi_src/cli/__init__.py`
- 测试: `tests/cli/test_people_cli.py`

**Step 1: 写失败测试**

```python
# tests/cli/test_people_cli.py
import pytest
from typer.testing import CliRunner
from unittest.mock import patch
from huaqi_src.cli.commands.people import people_app

runner = CliRunner()


def test_people_list_empty(tmp_path):
    with patch("huaqi_src.cli.commands.people.PeopleGraph") as MockGraph:
        mock_instance = MockGraph.return_value
        mock_instance.list_people.return_value = []
        result = runner.invoke(people_app, ["list"])
    assert result.exit_code == 0
    assert "暂无" in result.output


def test_people_add(tmp_path):
    with patch("huaqi_src.cli.commands.people.PeopleGraph") as MockGraph:
        mock_instance = MockGraph.return_value
        mock_instance.get_person.return_value = None
        result = runner.invoke(people_app, ["add", "张三", "--relation", "同事"])
    assert result.exit_code == 0
    mock_instance.add_person.assert_called_once()


def test_people_show_not_found(tmp_path):
    with patch("huaqi_src.cli.commands.people.PeopleGraph") as MockGraph:
        mock_instance = MockGraph.return_value
        mock_instance.get_person.return_value = None
        result = runner.invoke(people_app, ["show", "不存在的人"])
    assert result.exit_code == 0
    assert "未找到" in result.output


def test_people_note(tmp_path):
    with patch("huaqi_src.cli.commands.people.PeopleGraph") as MockGraph:
        mock_instance = MockGraph.return_value
        mock_instance.update_person.return_value = True
        result = runner.invoke(people_app, ["note", "张三", "喜欢喝咖啡"])
    assert result.exit_code == 0
    mock_instance.update_person.assert_called_once_with("张三", notes="喜欢喝咖啡")
```

**Step 2: 运行测试，确认失败**

```
pytest tests/cli/test_people_cli.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.cli.commands.people'`

**Step 3: 实现 `people.py`**

```python
# huaqi_src/cli/commands/people.py
import uuid
import typer
from typing import Optional
from rich.console import Console
from rich.table import Table

from huaqi_src.people.graph import PeopleGraph
from huaqi_src.people.models import Person

people_app = typer.Typer(name="people", help="管理人物关系网络")
console = Console()


@people_app.command("list")
def list_people():
    """列出所有关系人（按亲密度排序）"""
    graph = PeopleGraph()
    people = graph.list_people()
    if not people:
        console.print("[dim]暂无关系人数据[/dim]")
        return
    people.sort(key=lambda p: p.interaction_frequency, reverse=True)
    table = Table(title="关系网络")
    table.add_column("姓名")
    table.add_column("关系")
    table.add_column("情感倾向")
    table.add_column("近30天互动")
    for p in people:
        table.add_row(p.name, p.relation_type, p.emotional_impact, str(p.interaction_frequency))
    console.print(table)


@people_app.command("show")
def show_person(name: str = typer.Argument(..., help="人物姓名")):
    """查看某人详细画像"""
    graph = PeopleGraph()
    person = graph.get_person(name)
    if person is None:
        console.print(f"[red]未找到 '{name}'[/red]")
        return
    console.print(f"\n[bold]{person.name}[/bold]")
    console.print(f"关系类型: {person.relation_type}")
    console.print(f"情感倾向: {person.emotional_impact}（huaqi 的观察）")
    console.print(f"近30天互动: {person.interaction_frequency} 次")
    if person.alias:
        console.print(f"别名: {', '.join(person.alias)}")
    if person.profile:
        console.print(f"\n[bold]画像:[/bold]\n{person.profile}")
    if person.notes:
        console.print(f"\n[bold]备注:[/bold]\n{person.notes}")


@people_app.command("add")
def add_person(
    name: str = typer.Argument(..., help="姓名"),
    relation: str = typer.Option("其他", "--relation", "-r", help="关系类型"),
):
    """手动添加关系人"""
    graph = PeopleGraph()
    if graph.get_person(name) is not None:
        console.print(f"[yellow]'{name}' 已存在，使用 'huaqi people note' 更新备注[/yellow]")
        return
    person = Person(
        person_id=f"{name}-{uuid.uuid4().hex[:8]}",
        name=name,
        relation_type=relation,
    )
    graph.add_person(person)
    console.print(f"[green]已添加 '{name}'（{relation}）[/green]")


@people_app.command("note")
def add_note(
    name: str = typer.Argument(..., help="人物姓名"),
    text: str = typer.Argument(..., help="备注内容"),
):
    """为某人添加备注"""
    graph = PeopleGraph()
    success = graph.update_person(name, notes=text)
    if not success:
        console.print(f"[red]未找到 '{name}'[/red]")
        return
    console.print(f"[green]已更新 '{name}' 的备注[/green]")


@people_app.command("delete")
def delete_person(
    name: str = typer.Argument(..., help="人物姓名"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
):
    """删除某人数据（隐私保护）"""
    if not yes:
        confirm = typer.confirm(f"确定删除 '{name}' 的所有数据？此操作不可撤销")
        if not confirm:
            return
    graph = PeopleGraph()
    success = graph.delete_person(name)
    if not success:
        console.print(f"[red]未找到 '{name}'[/red]")
        return
    console.print(f"[green]已删除 '{name}' 的所有数据[/green]")
```

**Step 4: 在 `__init__.py` 注册子命令**

在 `huaqi_src/cli/__init__.py` 中：

找到：
```python
from huaqi_src.cli.inbox import app as inbox_app
```

在它下面追加：
```python
from huaqi_src.cli.commands.people import people_app
```

找到：
```python
app.add_typer(inbox_app, name="inbox", rich_help_panel="操作工具")
```

在它下面追加：
```python
app.add_typer(people_app, name="people", rich_help_panel="操作工具")
```

**Step 5: 运行测试，确认通过**

```
pytest tests/cli/test_people_cli.py -v
```

预期：4 个测试全部 PASS

**Step 6: 提交**

```
git add huaqi_src/cli/commands/people.py huaqi_src/cli/__init__.py tests/cli/test_people_cli.py
git commit -m "feat: add people CLI commands (list/show/add/note/delete)"
```

---

## Task 6: DailyReportAgent（日终复盘）

**文件：**
- 创建: `huaqi_src/reports/daily_report.py`
- 测试: `tests/reports/test_daily_report.py`

**背景：**
参照 `morning_brief.py` 的模式：
- `_build_context()` — 收集数据（当天日记、当天世界新闻、近期记忆）
- `_generate_report()` — 调用 LLM 生成报告
- `run()` — 保存到 `reports/daily/{date}-evening.md`，返回内容

**Step 1: 写失败测试**

```python
# tests/reports/test_daily_report.py
import datetime
import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.reports.daily_report import DailyReportAgent


def test_daily_report_creates_file(tmp_path):
    agent = DailyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="今日复盘：收获满满"):
        agent.run()
    report_dir = tmp_path / "reports" / "daily"
    files = list(report_dir.glob("*-evening.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "今日复盘" in content


def test_daily_report_context_includes_diary(tmp_path):
    diary_dir = tmp_path / "memory" / "diary"
    diary_dir.mkdir(parents=True)
    today = datetime.date.today().isoformat()
    (diary_dir / f"{today}.md").write_text("今天完成了 Phase 2 开发", encoding="utf-8")

    agent = DailyReportAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "Phase 2" in context


def test_daily_report_context_includes_people(tmp_path):
    from huaqi_src.people.graph import PeopleGraph
    from huaqi_src.people.models import Person
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="p1", name="张三", relation_type="同事",
        interaction_frequency=5
    ))

    agent = DailyReportAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "张三" in context
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_daily_report.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.reports.daily_report'`

**Step 3: 实现 `daily_report.py`**

```python
# huaqi_src/reports/daily_report.py
import datetime
from pathlib import Path
from typing import Optional


class DailyReportAgent:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from huaqi_src.core.config_paths import require_data_dir
            data_dir = require_data_dir()
        self.data_dir = Path(data_dir)

    def _build_context(self) -> str:
        sections = []
        today = datetime.date.today().isoformat()

        diary_dir = self.data_dir / "memory" / "diary"
        if diary_dir.exists():
            diary_file = diary_dir / f"{today}.md"
            if diary_file.exists():
                sections.append("## 今日日记\n" + diary_file.read_text(encoding="utf-8")[:800])

        world_dir = self.data_dir / "world"
        if world_dir.exists():
            world_file = world_dir / f"{today}.md"
            if world_file.exists():
                sections.append("## 今日世界热点\n" + world_file.read_text(encoding="utf-8")[:500])

        people_dir = self.data_dir / "people"
        if people_dir.exists():
            from huaqi_src.people.graph import PeopleGraph
            graph = PeopleGraph(data_dir=self.data_dir)
            active_people = [p for p in graph.list_people() if p.interaction_frequency > 0]
            if active_people:
                active_people.sort(key=lambda p: p.interaction_frequency, reverse=True)
                lines = ["## 关系网络动态"]
                for p in active_people[:5]:
                    lines.append(f"- {p.name}（{p.relation_type}）：近30天互动 {p.interaction_frequency} 次")
                sections.append("\n".join(lines))

        return "\n\n".join(sections) if sections else "暂无今日数据。"

    def _generate_report(self) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage
        from huaqi_src.cli.context import build_llm_manager

        context = self._build_context()
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=600)
        if llm_mgr is None:
            return "（LLM 未配置，无法生成复盘）"

        active_name = llm_mgr.get_active_provider()
        if not active_name:
            return "（未配置任何 LLM 提供商）"
        cfg = llm_mgr._configs[active_name]

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.7,
            max_tokens=600,
        )

        system_prompt = (
            "你是 huaqi，用户的 AI 同伴。请根据以下背景信息，生成一份简洁的日终复盘报告，"
            "包含：1）今日主要收获和亮点，2）情绪和状态观察，3）明日建议。"
            "报告应简短，不超过 400 字，语气温暖。"
        )

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"背景信息：\n{context}"),
        ])
        return response.content

    def run(self) -> str:
        report = self._generate_report()
        report_dir = self.data_dir / "reports" / "daily"
        report_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        report_file = report_dir / f"{today}-evening.md"
        report_file.write_text(f"# 日终复盘 {today}\n\n{report}\n", encoding="utf-8")
        return report
```

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_daily_report.py -v
```

预期：3 个测试全部 PASS

**Step 5: 提交**

```
git add huaqi_src/reports/daily_report.py tests/reports/test_daily_report.py
git commit -m "feat: implement DailyReportAgent (evening review)"
```

---

## Task 7: WeeklyReportAgent（周报）

**文件：**
- 创建: `huaqi_src/reports/weekly_report.py`
- 测试: `tests/reports/test_weekly_report.py`

**Step 1: 写失败测试**

```python
# tests/reports/test_weekly_report.py
import datetime
import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.reports.weekly_report import WeeklyReportAgent


def test_weekly_report_creates_file(tmp_path):
    agent = WeeklyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="本周成长亮点：完成了 Phase 2"):
        agent.run()
    report_dir = tmp_path / "reports" / "weekly"
    files = list(report_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Phase 2" in content


def test_weekly_report_context_includes_last_7_days_diaries(tmp_path):
    diary_dir = tmp_path / "memory" / "diary"
    diary_dir.mkdir(parents=True)
    for i in range(3):
        date = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        (diary_dir / f"{date}.md").write_text(f"第{i}天的日记内容", encoding="utf-8")

    agent = WeeklyReportAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "第0天" in context
    assert "第1天" in context


def test_weekly_report_iso_week_in_filename(tmp_path):
    agent = WeeklyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="周报"):
        agent.run()
    report_dir = tmp_path / "reports" / "weekly"
    files = list(report_dir.glob("*.md"))
    assert len(files) == 1
    today = datetime.date.today()
    expected_week = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    assert expected_week in files[0].name
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_weekly_report.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.reports.weekly_report'`

**Step 3: 实现 `weekly_report.py`**

```python
# huaqi_src/reports/weekly_report.py
import datetime
from pathlib import Path
from typing import Optional


class WeeklyReportAgent:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from huaqi_src.core.config_paths import require_data_dir
            data_dir = require_data_dir()
        self.data_dir = Path(data_dir)

    def _build_context(self) -> str:
        sections = []
        today = datetime.date.today()

        diary_dir = self.data_dir / "memory" / "diary"
        if diary_dir.exists():
            diary_snippets = []
            for i in range(7):
                date = (today - datetime.timedelta(days=i)).isoformat()
                f = diary_dir / f"{date}.md"
                if f.exists():
                    diary_snippets.append(f"### {date}\n{f.read_text(encoding='utf-8')[:300]}")
            if diary_snippets:
                sections.append("## 本周日记片段\n" + "\n\n".join(diary_snippets))

        people_dir = self.data_dir / "people"
        if people_dir.exists():
            from huaqi_src.people.graph import PeopleGraph
            graph = PeopleGraph(data_dir=self.data_dir)
            people = graph.list_people()
            if people:
                people.sort(key=lambda p: p.interaction_frequency, reverse=True)
                lines = ["## 关系人概览"]
                for p in people[:8]:
                    line = f"- {p.name}（{p.relation_type}）"
                    if p.profile:
                        line += f"：{p.profile[:50]}"
                    lines.append(line)
                sections.append("\n".join(lines))

        return "\n\n".join(sections) if sections else "暂无本周数据。"

    def _generate_report(self) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage
        from huaqi_src.cli.context import build_llm_manager

        context = self._build_context()
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=800)
        if llm_mgr is None:
            return "（LLM 未配置，无法生成周报）"

        active_name = llm_mgr.get_active_provider()
        if not active_name:
            return "（未配置任何 LLM 提供商）"
        cfg = llm_mgr._configs[active_name]

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.7,
            max_tokens=800,
        )

        system_prompt = (
            "你是 huaqi，用户的 AI 同伴。请根据以下背景信息，生成一份本周成长报告，"
            "包含：1）本周成长亮点，2）目标进展，3）值得关注的关系动态，4）下周建议。"
            "报告不超过 600 字，语气温暖有洞察力。"
        )

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"背景信息：\n{context}"),
        ])
        return response.content

    def run(self) -> str:
        report = self._generate_report()
        report_dir = self.data_dir / "reports" / "weekly"
        report_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today()
        iso = today.isocalendar()
        week_str = f"{iso[0]}-W{iso[1]:02d}"
        report_file = report_dir / f"{week_str}.md"
        report_file.write_text(f"# 周报 {week_str}\n\n{report}\n", encoding="utf-8")
        return report
```

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_weekly_report.py -v
```

预期：3 个测试全部 PASS

**Step 5: 提交**

```
git add huaqi_src/reports/weekly_report.py tests/reports/test_weekly_report.py
git commit -m "feat: implement WeeklyReportAgent"
```

---

## Task 8: QuarterlyReportAgent（季报）

**文件：**
- 创建: `huaqi_src/reports/quarterly_report.py`
- 测试: `tests/reports/test_quarterly_report.py`

**Step 1: 写失败测试**

```python
# tests/reports/test_quarterly_report.py
import datetime
import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.reports.quarterly_report import QuarterlyReportAgent


def test_quarterly_report_creates_file(tmp_path):
    agent = QuarterlyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="本季度成长总结"):
        agent.run()
    report_dir = tmp_path / "reports" / "quarterly"
    files = list(report_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "成长总结" in content


def test_quarterly_report_filename_format(tmp_path):
    agent = QuarterlyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="季报"):
        agent.run()
    report_dir = tmp_path / "reports" / "quarterly"
    files = list(report_dir.glob("*.md"))
    assert len(files) == 1
    today = datetime.date.today()
    quarter = (today.month - 1) // 3 + 1
    expected = f"{today.year}-Q{quarter}"
    assert expected in files[0].name


def test_quarterly_report_context_includes_weekly_reports(tmp_path):
    weekly_dir = tmp_path / "reports" / "weekly"
    weekly_dir.mkdir(parents=True)
    (weekly_dir / "2026-W10.md").write_text("本周完成了架构设计", encoding="utf-8")
    (weekly_dir / "2026-W11.md").write_text("本周完成了功能开发", encoding="utf-8")

    agent = QuarterlyReportAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "架构设计" in context or "W10" in context
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_quarterly_report.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.reports.quarterly_report'`

**Step 3: 实现 `quarterly_report.py`**

```python
# huaqi_src/reports/quarterly_report.py
import datetime
from pathlib import Path
from typing import Optional


class QuarterlyReportAgent:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from huaqi_src.core.config_paths import require_data_dir
            data_dir = require_data_dir()
        self.data_dir = Path(data_dir)

    def _current_quarter(self) -> tuple[int, int]:
        today = datetime.date.today()
        return today.year, (today.month - 1) // 3 + 1

    def _build_context(self) -> str:
        sections = []

        weekly_dir = self.data_dir / "reports" / "weekly"
        if weekly_dir.exists():
            weekly_files = sorted(weekly_dir.glob("*.md"), reverse=True)[:13]
            if weekly_files:
                snippets = []
                for f in weekly_files:
                    snippets.append(f"### {f.stem}\n{f.read_text(encoding='utf-8')[:200]}")
                sections.append("## 本季度周报摘要\n" + "\n\n".join(snippets))

        people_dir = self.data_dir / "people"
        if people_dir.exists():
            from huaqi_src.people.graph import PeopleGraph
            graph = PeopleGraph(data_dir=self.data_dir)
            people = graph.list_people()
            if people:
                lines = ["## 关系人全貌"]
                for p in sorted(people, key=lambda x: x.interaction_frequency, reverse=True):
                    line = f"- {p.name}（{p.relation_type}，{p.emotional_impact}影响）"
                    if p.profile:
                        line += f"：{p.profile[:80]}"
                    lines.append(line)
                sections.append("\n".join(lines))

        return "\n\n".join(sections) if sections else "暂无本季度数据。"

    def _generate_report(self) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage
        from huaqi_src.cli.context import build_llm_manager

        context = self._build_context()
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=1200)
        if llm_mgr is None:
            return "（LLM 未配置，无法生成季报）"

        active_name = llm_mgr.get_active_provider()
        if not active_name:
            return "（未配置任何 LLM 提供商）"
        cfg = llm_mgr._configs[active_name]

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.7,
            max_tokens=1200,
        )

        system_prompt = (
            "你是 huaqi，用户的 AI 同伴。请根据以下背景信息，生成一份季度成长报告，"
            "包含：1）本季度核心成长，2）长期模式识别（正向/需改善），3）目标漂移分析，"
            "4）关系网络变化，5）下季度建议。报告不超过 800 字，有深度有洞察。"
        )

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"背景信息：\n{context}"),
        ])
        return response.content

    def run(self) -> str:
        report = self._generate_report()
        report_dir = self.data_dir / "reports" / "quarterly"
        report_dir.mkdir(parents=True, exist_ok=True)
        year, quarter = self._current_quarter()
        report_file = report_dir / f"{year}-Q{quarter}.md"
        report_file.write_text(f"# 季报 {year}-Q{quarter}\n\n{report}\n", encoding="utf-8")
        return report
```

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_quarterly_report.py -v
```

预期：3 个测试全部 PASS

**Step 5: 提交**

```
git add huaqi_src/reports/quarterly_report.py tests/reports/test_quarterly_report.py
git commit -m "feat: implement QuarterlyReportAgent"
```

---

## Task 9: 把新报告 Agent 注册到定时调度器

**文件：**
- 修改: `huaqi_src/scheduler/jobs.py`
- 测试: `tests/scheduler/test_jobs.py`

**Step 1: 先阅读现有测试**

```
cat tests/scheduler/test_jobs.py
```

**Step 2: 写失败测试**

在 `tests/scheduler/test_jobs.py` 中追加：

```python
from unittest.mock import patch, MagicMock

def test_register_default_jobs_includes_new_reports():
    from huaqi_src.scheduler.jobs import register_default_jobs
    from huaqi_src.scheduler.manager import SchedulerManager

    mock_manager = MagicMock(spec=SchedulerManager)
    register_default_jobs(mock_manager)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "morning_brief" in call_ids
    assert "daily_report" in call_ids
    assert "weekly_report" in call_ids
    assert "quarterly_report" in call_ids
```

**Step 3: 运行测试，确认失败**

```
pytest tests/scheduler/test_jobs.py -v
```

预期：`AssertionError: assert 'daily_report' in [...]`

**Step 4: 修改 `jobs.py`**

```python
# huaqi_src/scheduler/jobs.py
from huaqi_src.scheduler.manager import SchedulerManager


def _run_morning_brief():
    from huaqi_src.reports.morning_brief import MorningBriefAgent
    try:
        agent = MorningBriefAgent()
        agent.run()
    except Exception as e:
        print(f"[MorningBrief] 生成失败: {e}")


def _run_daily_report():
    from huaqi_src.reports.daily_report import DailyReportAgent
    try:
        agent = DailyReportAgent()
        agent.run()
    except Exception as e:
        print(f"[DailyReport] 生成失败: {e}")


def _run_weekly_report():
    from huaqi_src.reports.weekly_report import WeeklyReportAgent
    try:
        agent = WeeklyReportAgent()
        agent.run()
    except Exception as e:
        print(f"[WeeklyReport] 生成失败: {e}")


def _run_quarterly_report():
    from huaqi_src.reports.quarterly_report import QuarterlyReportAgent
    try:
        agent = QuarterlyReportAgent()
        agent.run()
    except Exception as e:
        print(f"[QuarterlyReport] 生成失败: {e}")


def register_default_jobs(manager: SchedulerManager):
    manager.add_cron_job(
        job_id="morning_brief",
        func=_run_morning_brief,
        cron="0 8 * * *",
    )
    manager.add_cron_job(
        job_id="daily_report",
        func=_run_daily_report,
        cron="0 23 * * *",
    )
    manager.add_cron_job(
        job_id="weekly_report",
        func=_run_weekly_report,
        cron="0 21 * * 0",
    )
    manager.add_cron_job(
        job_id="quarterly_report",
        func=_run_quarterly_report,
        cron="0 22 L 3,6,9,12 *",
    )
```

**Step 5: 运行测试，确认通过**

```
pytest tests/scheduler/test_jobs.py -v
```

预期：所有测试 PASS

**Step 6: 提交**

```
git add huaqi_src/scheduler/jobs.py tests/scheduler/test_jobs.py
git commit -m "feat: register daily/weekly/quarterly report jobs in scheduler"
```

---

## Task 10: 升级 MorningBriefAgent 加入人物数据

**文件：**
- 修改: `huaqi_src/reports/morning_brief.py`
- 测试: `tests/reports/test_morning_brief.py`

**背景：**
晨间简报现在可以把今日将要接触的关系人列入上下文，让简报更有针对性。

**Step 1: 在 `test_morning_brief.py` 追加测试**

```python
def test_morning_brief_context_includes_people(tmp_path):
    from huaqi_src.people.graph import PeopleGraph
    from huaqi_src.people.models import Person

    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="p1",
        name="张三",
        relation_type="同事",
        interaction_frequency=8,
    ))

    agent = MorningBriefAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "张三" in context
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_morning_brief.py::test_morning_brief_context_includes_people -v
```

预期：FAIL，context 不含 "张三"

**Step 3: 修改 `morning_brief.py` 的 `_build_context`**

在 `morning_brief.py` 中，找到 `_build_context` 方法，在 `diary_dir` 块之后、`return` 之前追加：

```python
        people_dir = self.data_dir / "people"
        if people_dir.exists():
            from huaqi_src.people.graph import PeopleGraph
            graph = PeopleGraph(data_dir=self.data_dir)
            active_people = [p for p in graph.list_people() if p.interaction_frequency > 0]
            if active_people:
                active_people.sort(key=lambda p: p.interaction_frequency, reverse=True)
                lines = ["## 近期活跃关系人"]
                for p in active_people[:3]:
                    line = f"- {p.name}（{p.relation_type}）"
                    if p.notes:
                        line += f"：{p.notes}"
                    lines.append(line)
                sections.append("\n".join(lines))
```

**Step 4: 运行全部晨间简报测试**

```
pytest tests/reports/test_morning_brief.py -v
```

预期：所有测试 PASS

**Step 5: 提交**

```
git add huaqi_src/reports/morning_brief.py tests/reports/test_morning_brief.py
git commit -m "feat: enrich morning brief context with active people"
```

---

## Task 11: 全量回归测试

**Step 1: 运行所有测试**

```
pytest tests/ -v
```

预期：所有已有测试 + 新增测试全部 PASS，无新增 FAIL

**Step 2: 如有失败**

检查错误信息，逐一修复，再跑一遍直到全绿。

**Step 3: 提交最终状态**

```
git add -A
git commit -m "feat: Phase 2 deep understanding - PeopleGraph + multi-period reports"
```

---

## 验收检查清单

完成后手动验证：

```bash
# 1. 人物管理 CLI
huaqi people add 张三 --relation 同事
huaqi people note 张三 "喜欢直接说结论"
huaqi people show 张三
huaqi people list

# 2. 对话中调用人物工具
# 在 huaqi chat 中输入：
# "张三是什么样的人？"
# "我认识哪些人？"

# 3. 报告生成（需要 LLM 已配置）
# python -c "from huaqi_src.reports.daily_report import DailyReportAgent; a = DailyReportAgent(); print(a._build_context())"
# python -c "from huaqi_src.reports.weekly_report import WeeklyReportAgent; a = WeeklyReportAgent(); print(a._build_context())"
```

---

## 新增文件一览

| 文件 | 说明 |
|------|------|
| `huaqi_src/people/__init__.py` | 包初始化 |
| `huaqi_src/people/models.py` | Person + Relation 数据模型 |
| `huaqi_src/people/graph.py` | 人物存储层（Markdown） |
| `huaqi_src/people/extractor.py` | LLM 自动提取人物信息 |
| `huaqi_src/cli/commands/people.py` | CLI 命令：list/show/add/note/delete |
| `huaqi_src/reports/daily_report.py` | 日终复盘 Agent |
| `huaqi_src/reports/weekly_report.py` | 周报 Agent |
| `huaqi_src/reports/quarterly_report.py` | 季报 Agent |
| `tests/people/test_models.py` | Person/Relation 模型测试 |
| `tests/people/test_graph.py` | PeopleGraph 存储测试 |
| `tests/people/test_extractor.py` | PersonExtractor 测试 |
| `tests/cli/test_people_cli.py` | People CLI 测试 |
| `tests/reports/test_daily_report.py` | 日报 Agent 测试 |
| `tests/reports/test_weekly_report.py` | 周报 Agent 测试 |
| `tests/reports/test_quarterly_report.py` | 季报 Agent 测试 |

## 修改文件一览

| 文件 | 改动说明 |
|------|---------|
| `huaqi_src/agent/tools.py` | 新增 `search_person_tool`、`get_relationship_map_tool` |
| `huaqi_src/agent/graph/chat.py` | import + 注册新 Tool 到 tools list |
| `huaqi_src/cli/__init__.py` | 注册 `people_app` 子命令 |
| `huaqi_src/scheduler/jobs.py` | 新增 daily/weekly/quarterly 定时任务 |
| `huaqi_src/reports/morning_brief.py` | `_build_context` 加入人物数据 |
| `tests/agent/test_tools.py` | 新增 2 个 Tool 测试 |
| `tests/reports/test_morning_brief.py` | 新增人物上下文测试 |
| `tests/scheduler/test_jobs.py` | 新增调度任务注册验证测试 |
