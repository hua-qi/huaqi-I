"""用户画像叙事生成器

基于日记、对话历史和结构化字段，每天生成一次 LLM 叙事性画像并缓存。
"""

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from huaqi_src.config.paths import get_memory_dir


NARRATIVE_PROMPT = """你是一个洞察力极强的心理分析师和人物传记作者。
请基于以下数据，为该用户生成一份客观、深刻、多维度的画像描述。

要求：
1. **完全客观**，同时包含优势和缺点/局限性，不要美化
2. **维度尽可能多**，覆盖但不限于：性格特质、思维方式、工作风格、情绪模式、人际关系倾向、价值观、成长轨迹、潜在矛盾或挣扎
3. 用**第三人称**叙事，语言凝练但有温度
4. 基于数据说话，有推断时要标注"推测"
5. 长度 300-600 字，分段落
6. 不要列清单，要叙事性段落

---

## 已知结构化信息
```
{structured_info}
```

## 最近日记（最多 10 篇）
{diary_content}

## 最近对话摘要
{conversation_content}

---

请直接输出画像正文，不需要标题。"""


@dataclass
class ProfileNarrative:
    """LLM 动态生成的叙事性用户画像"""
    content: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    data_sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "generated_at": self.generated_at,
            "data_sources": self.data_sources,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfileNarrative":
        return cls(
            content=data.get("content", ""),
            generated_at=data.get("generated_at", datetime.now().isoformat()),
            data_sources=data.get("data_sources", []),
        )

    def is_today(self) -> bool:
        try:
            generated_date = datetime.fromisoformat(self.generated_at).date()
            return generated_date == datetime.now().date()
        except Exception:
            return False


class ProfileNarrativeManager:
    """用户画像叙事生成器

    每天生成一次 LLM 叙事性画像并缓存，
    基于日记、对话历史、结构化字段综合生成。
    """

    NARRATIVE_FILENAME = "profile_narrative.yaml"

    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or get_memory_dir()
        self.narrative_path = self.memory_dir / self.NARRATIVE_FILENAME
        self._narrative: Optional[ProfileNarrative] = None

    def _load(self) -> Optional[ProfileNarrative]:
        if not self.narrative_path.exists():
            return None
        try:
            with open(self.narrative_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return ProfileNarrative.from_dict(data)
        except Exception:
            return None

    def _save(self, narrative: ProfileNarrative):
        self.narrative_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.narrative_path, "w", encoding="utf-8") as f:
            yaml.dump(narrative.to_dict(), f, allow_unicode=True, sort_keys=False)

    def get_cached(self) -> Optional[ProfileNarrative]:
        if self._narrative is None:
            self._narrative = self._load()
        return self._narrative

    def needs_refresh(self) -> bool:
        cached = self.get_cached()
        if cached is None:
            return True
        return not cached.is_today()

    def _collect_data(self) -> Dict[str, Any]:
        from huaqi_src.layers.data.profile.manager import get_profile_manager

        data: Dict[str, Any] = {
            "structured": {},
            "diaries": [],
            "conversations": [],
        }

        try:
            pm = get_profile_manager()
            p = pm.profile
            structured: Dict[str, Any] = {}
            identity = p.identity.to_dict()
            if identity:
                structured["身份"] = identity
            background = p.background.to_dict()
            if background:
                structured["背景"] = background
            preferences = p.preferences.to_dict()
            if preferences:
                structured["偏好"] = preferences
            data["structured"] = structured
        except Exception:
            pass

        try:
            from huaqi_src.layers.data.diary import DiaryStore
            diary_store = DiaryStore(self.memory_dir)
            entries = diary_store.list_entries(limit=10)
            data["diaries"] = [
                {
                    "date": e.date,
                    "mood": e.mood,
                    "tags": e.tags,
                    "content": e.content[:500] + ("..." if len(e.content) > 500 else ""),
                }
                for e in entries
            ]
        except Exception:
            pass

        try:
            from huaqi_src.layers.data.memory.storage.markdown_store import MarkdownMemoryStore
            conv_store = MarkdownMemoryStore(self.memory_dir / "conversations")
            conversations = conv_store.list_conversations(limit=5)
            data["conversations"] = conversations
        except Exception:
            pass

        return data

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        structured_str = json.dumps(data["structured"], ensure_ascii=False, indent=2) if data["structured"] else "暂无结构化信息"

        diary_parts = []
        for d in data["diaries"]:
            parts = [f"【{d['date']}】"]
            if d.get("mood"):
                parts.append(f"情绪: {d['mood']}")
            if d.get("tags"):
                parts.append(f"标签: {', '.join(d['tags'])}")
            parts.append(d["content"])
            diary_parts.append("\n".join(parts))
        diary_str = "\n\n".join(diary_parts) if diary_parts else "暂无日记数据"

        conv_parts = []
        for c in data["conversations"]:
            session_id = c.get("session_id", "")[:8]
            turns = c.get("turns", 0)
            created = c.get("created_at", "")[:10]
            conv_parts.append(f"- 会话 {session_id}（{created}，共 {turns} 轮）")
        conv_str = "\n".join(conv_parts) if conv_parts else "暂无对话记录"

        return NARRATIVE_PROMPT.format(
            structured_info=structured_str,
            diary_content=diary_str,
            conversation_content=conv_str,
        )

    def generate(self, llm_manager) -> ProfileNarrative:
        from huaqi_src.layers.capabilities.llm.manager import Message

        data = self._collect_data()
        prompt = self._build_prompt(data)

        sources = []
        if data["structured"]:
            sources.append("结构化画像")
        if data["diaries"]:
            sources.append(f"日记({len(data['diaries'])}篇)")
        if data["conversations"]:
            sources.append(f"对话({len(data['conversations'])}次)")

        messages = [
            Message.system("你是一个洞察力极强的心理分析师，请客观、深刻地分析并描述用户。"),
            Message.user(prompt),
        ]

        response = llm_manager.chat(messages)
        content = response.content.strip()

        narrative = ProfileNarrative(
            content=content,
            data_sources=sources,
        )
        self._narrative = narrative
        self._save(narrative)
        return narrative

    def get_or_generate(self, llm_manager) -> ProfileNarrative:
        if not self.needs_refresh():
            return self.get_cached()
        return self.generate(llm_manager)

    def generate_async(
        self,
        llm_manager,
        on_complete: Optional[Callable[["ProfileNarrative"], None]] = None,
    ):
        def _worker():
            try:
                result = self.generate(llm_manager)
                if on_complete:
                    on_complete(result)
            except Exception:
                pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return t


_narrative_manager: Optional[ProfileNarrativeManager] = None


def get_narrative_manager() -> ProfileNarrativeManager:
    global _narrative_manager
    if _narrative_manager is None:
        _narrative_manager = ProfileNarrativeManager()
    return _narrative_manager
