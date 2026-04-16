import asyncio
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List, Optional

from huaqi_src.config.errors import DimensionNotFoundError
from huaqi_src.layers.growth.telos.models import (
    DimensionLayer,
    HistoryEntry,
    STANDARD_DIMENSION_LAYERS,
    STANDARD_DIMENSIONS,
    TelosDimension,
)

if TYPE_CHECKING:
    from huaqi_src.layers.growth.telos.meta import MetaManager

_INITIAL_CONTENT: dict[str, str] = {
    "beliefs": "（待补充）",
    "models": "（待补充）",
    "narratives": "（待补充）",
    "goals": "（待补充）",
    "challenges": "（待补充）",
    "strategies": "（待补充）",
    "learned": "（待补充）",
    "shadows": "（待补充）",
}

_META_TEMPLATE = """---
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


class TelosManager:

    def __init__(self, telos_dir: Path, git_commit: bool = True) -> None:
        self._dir = telos_dir
        self._git_commit = git_commit
        self._meta_lock: asyncio.Lock = asyncio.Lock()
        self.on_work_style_updated: Optional[Callable[[], None]] = None

    def _path(self, name: str) -> Path:
        return self._dir / f"{name}.md"

    def _archive_path(self, name: str) -> Path:
        return self._dir / "_archive" / f"{name}.md"

    def init(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / "_archive").mkdir(exist_ok=True)

        for name in STANDARD_DIMENSIONS:
            p = self._path(name)
            if not p.exists():
                dim = TelosDimension(
                    name=name,
                    layer=STANDARD_DIMENSION_LAYERS[name],
                    content=_INITIAL_CONTENT[name],
                    confidence=0.5,
                )
                p.write_text(dim.to_markdown(), encoding="utf-8")

        meta_p = self._path("meta")
        if not meta_p.exists():
            meta_p.write_text(
                _META_TEMPLATE.format(
                    date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    active_dims=" / ".join(STANDARD_DIMENSIONS),
                ),
                encoding="utf-8",
            )

        self._rebuild_index()

    def get(self, name: str) -> TelosDimension:
        p = self._path(name)
        if not p.exists():
            raise DimensionNotFoundError(
                f"Dimension '{name}' not found",
                context={"name": name, "path": str(p)},
            )
        text = p.read_text(encoding="utf-8")
        return TelosDimension.from_markdown(text)

    def list_active(self) -> List[TelosDimension]:
        result = []
        for p in self._dir.glob("*.md"):
            if p.stem in ("meta", "INDEX"):
                continue
            try:
                dim = TelosDimension.from_markdown(p.read_text(encoding="utf-8"))
                if dim.is_active:
                    result.append(dim)
            except Exception:
                pass
        return result

    def _git_auto_commit(self, message: str) -> None:
        if not self._git_commit:
            return
        try:
            repo_root = self._dir.parent
            subprocess.run(["git", "-C", str(repo_root), "add", str(self._dir)],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo_root), "commit", "-m", message],
                           check=True, capture_output=True)
        except Exception:
            pass

    def update(
        self,
        name: str,
        new_content: str,
        history_entry: HistoryEntry,
        confidence: float,
    ) -> None:
        dim = self.get(name)
        dim.content = new_content
        dim.confidence = confidence
        dim.update_count += 1
        dim.history.append(history_entry)
        self._path(name).write_text(dim.to_markdown(), encoding="utf-8")
        self._rebuild_index()
        self._git_auto_commit(f"telos: update {name} (v{dim.update_count})")
        if name == "work_style" and self.on_work_style_updated is not None:
            self.on_work_style_updated()

    def create_custom(
        self,
        name: str,
        layer: DimensionLayer,
        initial_content: str,
        meta_manager: Optional["MetaManager"] = None,
    ) -> None:
        p = self._path(name)
        if p.exists():
            raise ValueError(f"Dimension '{name}' already exists")
        dim = TelosDimension(
            name=name,
            layer=layer,
            content=initial_content,
            confidence=0.5,
            is_custom=True,
        )
        p.write_text(dim.to_markdown(), encoding="utf-8")
        self._rebuild_index()
        if meta_manager is not None:
            from huaqi_src.layers.growth.telos.meta import DimensionOperation
            meta_manager.add_active_dimension(name)
            meta_manager.log_dimension_operation(DimensionOperation(
                dimension=name,
                operation="add",
                date=datetime.now(timezone.utc),
                reason="用户创建自定义维度",
            ))

    def archive(self, name: str, meta_manager: Optional["MetaManager"] = None) -> None:
        if name in STANDARD_DIMENSIONS:
            raise ValueError(f"Cannot archive standard dimension '{name}'")
        p = self._path(name)
        if not p.exists():
            raise DimensionNotFoundError(f"Dimension '{name}' not found")
        dest = self._archive_path(name)
        shutil.move(str(p), str(dest))
        self._rebuild_index()
        if meta_manager is not None:
            from huaqi_src.layers.growth.telos.meta import DimensionOperation
            meta_manager.remove_active_dimension(name)
            meta_manager.log_dimension_operation(DimensionOperation(
                dimension=name,
                operation="archive",
                date=datetime.now(timezone.utc),
                reason="用户归档维度",
            ))

    def get_dimension_snippet(self, name: str) -> str:
        p = self._path(name)
        if not p.exists():
            return ""
        text = p.read_text(encoding="utf-8")
        separator_index = text.find("\n---\n\n## 更新历史")
        if separator_index != -1:
            return text[:separator_index].strip()
        return text.strip()

    def get_all_dimension_snippets(self) -> dict[str, str]:
        result = {}
        for dim in self.list_active():
            result[dim.name] = self.get_dimension_snippet(dim.name)
        return result

    def _rebuild_index(self) -> None:
        active = self.list_active()

        core = [d for d in active if d.layer == DimensionLayer.CORE]
        middle = [d for d in active if d.layer == DimensionLayer.MIDDLE]
        surface = [d for d in active if d.layer == DimensionLayer.SURFACE]

        lines = [
            "# TELOS 索引",
            "",
            f"> 最后更新：{datetime.now(timezone.utc).strftime('%Y-%m-%d')} · 共 {len(active)} 个活跃维度",
            "",
            "## 核心层（变化最慢）",
        ]

        def dim_line(d: TelosDimension) -> str:
            summary = d.content[:30].replace("\n", " ") + ("…" if len(d.content) > 30 else "")
            return f"- [{d.name}.md]({d.name}.md) — {summary}（v{d.update_count}，置信度 {d.confidence}）"

        for d in core:
            lines.append(dim_line(d))

        lines += ["", "## 中间层（定期变化）"]
        for d in middle:
            lines.append(dim_line(d))

        lines += ["", "## 表面层（频繁变化）"]
        for d in surface:
            lines.append(dim_line(d))

        lines += ["", "## 特殊", "- [meta.md](meta.md)", ""]

        (self._dir / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
