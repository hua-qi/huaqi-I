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
