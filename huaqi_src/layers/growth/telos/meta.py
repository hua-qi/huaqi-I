import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from huaqi_src.layers.growth.telos.manager import TelosManager


class CorrectionRecord(BaseModel):
    date: datetime
    agent_conclusion: str
    user_feedback: str
    correction_direction: str


class DimensionOperation(BaseModel):
    dimension: str
    operation: str
    date: datetime
    reason: str


_TEMPLATE = """\
---
dimension: meta
updated_at: {date}
---

## 提炼偏好

### 用户反馈记录

| 日期 | Agent 提炼结论 | 用户反馈 | 校正方向 |
|---|---|---|---|

## 活跃维度列表

当前活跃维度：{active_dims}

## 维度演化历史

| 维度 | 操作 | 日期 | 原因 |
|---|---|---|---|
"""


class MetaManager:

    def __init__(self, meta_path: Path) -> None:
        self._path = meta_path

    def init(self, active_dimensions: List[str]) -> None:
        if self._path.exists():
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            _TEMPLATE.format(
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                active_dims=" / ".join(active_dimensions),
            ),
            encoding="utf-8",
        )

    def _read(self) -> str:
        return self._path.read_text(encoding="utf-8")

    def _write(self, text: str) -> None:
        self._path.write_text(text, encoding="utf-8")

    def add_correction(
        self,
        record: CorrectionRecord,
        dimension: Optional[str] = None,
        telos_manager: Optional["TelosManager"] = None,
        confidence_penalty: float = 0.15,
    ) -> None:
        text = self._read()
        row = f"| {record.date.strftime('%Y-%m-%d')} | {record.agent_conclusion} | {record.user_feedback} | {record.correction_direction} |"
        text = text.replace(
            "| 日期 | Agent 提炼结论 | 用户反馈 | 校正方向 |\n|---|---|---|---|",
            f"| 日期 | Agent 提炼结论 | 用户反馈 | 校正方向 |\n|---|---|---|---|\n{row}",
        )
        self._write(text)

        if dimension and telos_manager:
            try:
                dim = telos_manager.get(dimension)
                new_confidence = max(0.0, dim.confidence - confidence_penalty)
                from huaqi_src.layers.growth.telos.models import HistoryEntry
                entry = HistoryEntry(
                    version=dim.update_count + 1,
                    change=f"用户纠错：{record.correction_direction}",
                    trigger=f"用户反馈：{record.user_feedback}",
                    confidence=new_confidence,
                    updated_at=datetime.now(timezone.utc),
                )
                telos_manager.update(
                    name=dimension,
                    new_content=dim.content,
                    history_entry=entry,
                    confidence=new_confidence,
                )
            except Exception:
                pass
        self._write(text)

    def list_corrections(self) -> List[CorrectionRecord]:
        text = self._read()
        records = []
        in_table = False
        for line in text.splitlines():
            if "Agent 提炼结论" in line:
                in_table = True
                continue
            if in_table and line.startswith("|---"):
                continue
            if in_table and line.startswith("|") and line.strip() != "|":
                parts = [p.strip() for p in line.strip("|").split("|")]
                if len(parts) >= 4 and parts[0]:
                    try:
                        records.append(CorrectionRecord(
                            date=datetime.strptime(parts[0], "%Y-%m-%d").replace(tzinfo=timezone.utc),
                            agent_conclusion=parts[1],
                            user_feedback=parts[2],
                            correction_direction=parts[3],
                        ))
                    except Exception:
                        pass
            elif in_table and not line.startswith("|"):
                in_table = False
        return records

    def get_active_dimensions(self) -> List[str]:
        text = self._read()
        m = re.search(r"当前活跃维度：(.+)", text)
        if not m:
            return []
        return [d.strip() for d in m.group(1).split("/") if d.strip()]

    def add_active_dimension(self, name: str) -> None:
        dims = self.get_active_dimensions()
        if name not in dims:
            dims.append(name)
        self._update_active_dims(dims)

    def remove_active_dimension(self, name: str) -> None:
        dims = [d for d in self.get_active_dimensions() if d != name]
        self._update_active_dims(dims)

    def _update_active_dims(self, dims: List[str]) -> None:
        text = self._read()
        new_line = f"当前活跃维度：{' / '.join(dims)}"
        text = re.sub(r"当前活跃维度：.+", new_line, text)
        self._write(text)

    def log_dimension_operation(self, op: DimensionOperation) -> None:
        text = self._read()
        row = f"| {op.dimension} | {op.operation} | {op.date.strftime('%Y-%m-%d')} | {op.reason} |"
        text = text.replace(
            "| 维度 | 操作 | 日期 | 原因 |\n|---|---|---|---|",
            f"| 维度 | 操作 | 日期 | 原因 |\n|---|---|---|---|\n{row}",
        )
        self._write(text)

    def list_dimension_operations(self) -> List[DimensionOperation]:
        text = self._read()
        ops = []
        in_table = False
        for line in text.splitlines():
            if "| 维度 | 操作 |" in line:
                in_table = True
                continue
            if in_table and line.startswith("|---"):
                continue
            if in_table and line.startswith("|") and line.strip() != "|":
                parts = [p.strip() for p in line.strip("|").split("|")]
                if len(parts) >= 4 and parts[0]:
                    try:
                        ops.append(DimensionOperation(
                            dimension=parts[0],
                            operation=parts[1],
                            date=datetime.strptime(parts[2], "%Y-%m-%d").replace(tzinfo=timezone.utc),
                            reason=parts[3],
                        ))
                    except Exception:
                        pass
            elif in_table and not line.startswith("|"):
                in_table = False
        return ops
