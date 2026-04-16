import re
from datetime import date
from pathlib import Path
from typing import Optional

from huaqi_src.layers.growth.telos.manager import TelosManager

_DEFAULT_AGENTS_MD = Path.home() / ".codeflicker" / "AGENTS.md"
_SECTION_HEADER = "## My Work Style"
_SECTION_PATTERN = re.compile(
    r"(## My Work Style\n)(.*?)(?=\n## |\Z)", re.DOTALL
)


class CLAUDEmdWriter:

    def __init__(
        self,
        telos_manager: TelosManager,
        agents_md_path: Optional[Path] = None,
    ) -> None:
        self._mgr = telos_manager
        self._path = agents_md_path or _DEFAULT_AGENTS_MD

    def sync(self) -> None:
        section = self._build_section()
        self._upsert_section(section)

    def _build_section(self) -> str:
        parts = [f"{_SECTION_HEADER}\n"]
        parts.append(f"\n> 由 huaqi-growing 自动维护，最后更新：{date.today()}\n")
        for dim in ("work_style", "strategies", "shadows"):
            snippet = self._mgr.get_dimension_snippet(dim)
            if snippet:
                parts.append(f"\n### {dim}\n\n{snippet}\n")
        return "".join(parts)

    def _upsert_section(self, new_section: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text(new_section + "\n", encoding="utf-8")
            return
        existing = self._path.read_text(encoding="utf-8")
        match = _SECTION_PATTERN.search(existing)
        if match:
            updated = existing[: match.start()] + new_section + existing[match.end() :]
        else:
            updated = existing.rstrip("\n") + "\n\n" + new_section + "\n"
        self._path.write_text(updated, encoding="utf-8")
