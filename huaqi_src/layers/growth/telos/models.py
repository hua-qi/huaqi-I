from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator


class DimensionLayer(str, Enum):
    CORE = "core"
    MIDDLE = "middle"
    SURFACE = "surface"


STANDARD_DIMENSIONS = [
    "beliefs", "models", "narratives",
    "goals", "challenges", "strategies",
    "learned", "people", "shadows",
]

STANDARD_DIMENSION_LAYERS: dict[str, DimensionLayer] = {
    "beliefs": DimensionLayer.CORE,
    "models": DimensionLayer.CORE,
    "narratives": DimensionLayer.CORE,
    "goals": DimensionLayer.MIDDLE,
    "challenges": DimensionLayer.MIDDLE,
    "strategies": DimensionLayer.MIDDLE,
    "learned": DimensionLayer.SURFACE,
    "people": DimensionLayer.SURFACE,
    "shadows": DimensionLayer.SURFACE,
}


class HistoryEntry(BaseModel):
    version: int
    change: str
    trigger: str
    confidence: float
    updated_at: datetime


class TelosDimension(BaseModel):
    name: str
    layer: DimensionLayer
    content: str
    confidence: float = 0.5
    update_count: int = 0
    is_active: bool = True
    is_custom: bool = False
    history: List[HistoryEntry] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must not be empty")
        return v

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("content must not be empty")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v

    def to_markdown(self) -> str:
        updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines = [
            "---",
            f"dimension: {self.name}",
            f"layer: {self.layer.value}",
            f"confidence: {self.confidence}",
            f"updated_at: {updated_at}",
            f"update_count: {self.update_count}",
            "---",
            "",
            "## 当前认知",
            "",
            self.content.strip(),
        ]

        if self.history:
            lines += ["", "---", "", "## 更新历史", ""]
            for entry in reversed(self.history):
                lines += [
                    f"### v{entry.version} · {entry.updated_at.strftime('%Y-%m-%d')}",
                    f"**变化**：{entry.change}",
                    f"**触发**：{entry.trigger}",
                    f"**置信度**：{entry.confidence}",
                    "",
                ]

        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> "TelosDimension":
        frontmatter_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not frontmatter_match:
            raise ValueError("Invalid TELOS markdown: missing frontmatter")

        fm_text = frontmatter_match.group(1)
        fm: dict = {}
        for line in fm_text.splitlines():
            if ": " in line:
                k, _, v = line.partition(": ")
                fm[k.strip()] = v.strip()

        content_match = re.search(r"## 当前认知\n\n(.*?)(?:\n---|\Z)", text, re.DOTALL)
        content = content_match.group(1).strip() if content_match else ""

        history: List[HistoryEntry] = []
        for m in re.finditer(
            r"### v(\d+) · (\d{4}-\d{2}-\d{2})\n\*\*变化\*\*：(.*?)\n\*\*触发\*\*：(.*?)\n\*\*置信度\*\*：([\d.]+)",
            text,
        ):
            history.append(HistoryEntry(
                version=int(m.group(1)),
                change=m.group(3).strip(),
                trigger=m.group(4).strip(),
                confidence=float(m.group(5)),
                updated_at=datetime.strptime(m.group(2), "%Y-%m-%d").replace(tzinfo=timezone.utc),
            ))

        return cls(
            name=fm.get("dimension", ""),
            layer=DimensionLayer(fm.get("layer", "surface")),
            confidence=float(fm.get("confidence", 0.5)),
            update_count=int(fm.get("update_count", 0)),
            content=content,
            history=sorted(history, key=lambda e: e.version),
        )
