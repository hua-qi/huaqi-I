import json
import datetime
from pathlib import Path
from typing import Optional

from .models import Person, Relation


class PeopleGraph:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._people_dir = Path(data_dir) / "people"
        else:
            from huaqi_src.core.config_paths import get_people_dir
            self._people_dir = get_people_dir()
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
