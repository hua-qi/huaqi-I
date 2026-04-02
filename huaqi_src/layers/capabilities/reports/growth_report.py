from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from huaqi_src.layers.growth.telos.growth_events import GrowthEvent, GrowthEventStore
from huaqi_src.layers.growth.telos.manager import TelosManager


class GrowthReport(BaseModel):
    user_id: str
    period: str
    period_label: str
    telos_snapshot: str
    growth_events: List[GrowthEvent]
    narrative: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_markdown(self) -> str:
        lines = [
            f"# 成长报告 {self.period_label}",
            "",
            f"> 生成时间：{self.generated_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 本期叙事",
            "",
            self.narrative,
        ]

        if self.growth_events:
            lines += ["", "## 成长事件", ""]
            for ev in self.growth_events:
                lines += [
                    f"### {ev.title}",
                    f"> {ev.occurred_at.strftime('%Y-%m-%d')} · {ev.dimension}（{ev.layer}层）",
                    "",
                    ev.narrative,
                    "",
                ]

        lines += [
            "## 当前 TELOS 快照",
            "",
            self.telos_snapshot,
        ]
        return "\n".join(lines)


_REPORT_SYSTEM = """\
你是用户的成长伙伴 Huaqi。
根据以下背景信息，生成一份{period_label}成长报告。
要求：温暖、有洞察力，不超过 400 字，用第二人称（"你"）。"""

_TEMPLATE_NO_EVENTS = "本期没有记录到明显的认知变化，但每一天的输入都在积累中。继续保持。"


class GrowthReportBuilder:

    def __init__(
        self,
        telos_manager: TelosManager,
        event_store: GrowthEventStore,
        llm: Optional[Any] = None,
    ) -> None:
        self._mgr = telos_manager
        self._events = event_store
        self._llm = llm

    def build_context(self, user_id: str, days: int) -> str:
        since = datetime.now(timezone.utc) - timedelta(days=days)

        index_path = self._mgr._dir / "INDEX.md"
        telos_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""

        events = self._events.list_by_user(user_id, limit=20)
        recent = [e for e in events if e.occurred_at >= since]

        lines = ["## TELOS 快照", "", telos_text]

        if recent:
            lines += ["", "## 本期成长事件", ""]
            for ev in recent:
                lines.append(f"- [{ev.occurred_at.strftime('%Y-%m-%d')}] **{ev.title}**：{ev.narrative[:80]}")
        else:
            lines += ["", "## 本期成长事件", "", "（本期无成长事件记录）"]

        return "\n".join(lines)

    def generate(
        self,
        user_id: str,
        period: str,
        period_label: str,
        days: int,
    ) -> GrowthReport:
        index_path = self._mgr._dir / "INDEX.md"
        telos_snapshot = index_path.read_text(encoding="utf-8") if index_path.exists() else ""

        since = datetime.now(timezone.utc) - timedelta(days=days)
        all_events = self._events.list_by_user(user_id, limit=50)
        recent_events = [e for e in all_events if e.occurred_at >= since]

        if self._llm is not None:
            ctx = self.build_context(user_id, days)
            prompt = _REPORT_SYSTEM.format(period_label=period_label) + f"\n\n背景信息：\n{ctx}"
            response = self._llm.invoke(prompt)
            narrative = response.content.strip()
        else:
            if recent_events:
                titles = "、".join(e.title for e in recent_events[:3])
                narrative = f"本期记录到 {len(recent_events)} 个成长事件：{titles}。"
            else:
                narrative = _TEMPLATE_NO_EVENTS

        return GrowthReport(
            user_id=user_id,
            period=period,
            period_label=period_label,
            telos_snapshot=telos_snapshot,
            growth_events=recent_events,
            narrative=narrative,
        )

    def save(self, report: GrowthReport, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{report.period_label}.md"
        path = output_dir / filename
        path.write_text(report.to_markdown(), encoding="utf-8")
        return path
