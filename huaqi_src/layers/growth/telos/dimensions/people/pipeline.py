import json
import datetime
from typing import Any, List, Optional

from huaqi_src.layers.data.raw_signal.models import RawSignal
from .graph import PeopleGraph
from .models import Person, InteractionLog, EmotionalTimeline


def _load_pipeline_prompt(**kwargs) -> str:
    try:
        from huaqi_src.prompts.loader import get_prompt_loader
        loader = get_prompt_loader()
        system, user = loader.load(
            "layers.growth.telos.dimensions.people.pipeline", **kwargs
        )
        return user or system or ""
    except Exception:
        content = kwargs.get("content", "")
        known_people = kwargs.get("known_people", "")
        mentioned_names = kwargs.get("mentioned_names", "")
        return (
            "分析以下信号文本，提取其中出现的人物互动信息。\n"
            "\n"
            f"信号文本：\n{content}\n"
            "\n"
            f"已知人物列表（摘要）：\n{known_people}\n"
            "\n"
            f"本次信号中提到的人名：{mentioned_names}\n"
            "\n"
            "对每个提到的人物，提取：\n"
            "- interaction_type: 从 [合作, 冲突, 日常, 初识, 久未联系] 中选择\n"
            "- emotional_score: 此次互动对用户情感的影响，-1.0（极负面）到 1.0（极正面）\n"
            "- summary: 一句话描述此次互动\n"
            "- new_profile: 若发现新的画像信息（职位/性格/兴趣），填写；否则 null\n"
            "- new_relation_type: 若关系类型发生变化，填写；否则 null\n"
            "\n"
            "只返回 JSON 数组，不要其他内容：\n"
            '[\n  {{\n    "name": "姓名",\n'
            '    "interaction_type": "...",\n'
            '    "emotional_score": 0.0,\n'
            '    "summary": "...",\n'
            '    "new_profile": null,\n'
            '    "new_relation_type": null\n'
            "  }}\n]"
        )


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

    async def process(self, signal: RawSignal, mentioned_names: List[str]) -> List[Person]:
        if not mentioned_names:
            return []

        prompt = _load_pipeline_prompt(
            content=signal.content,
            known_people=self._known_people_summary(mentioned_names),
            mentioned_names="、".join(mentioned_names),
        )

        try:
            response = await self._llm.ainvoke(prompt)
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
