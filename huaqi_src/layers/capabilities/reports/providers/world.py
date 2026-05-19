import re
from pathlib import Path
from typing import Optional

from huaqi_src.layers.capabilities.reports.providers import DataProvider, DateRange, register


class WorldProvider(DataProvider):
    name = "world"
    priority = 10
    supported_reports = ["morning", "daily"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        today = date_range.end.isoformat()
        world_file = self._data_dir / "world" / f"{today}.md"
        if not world_file.exists():
            world_file = self._lazy_fetch(today)
        if world_file is None or not world_file.exists():
            return None
        content = world_file.read_text(encoding="utf-8")
        extracted = self._extract_for_report(content)
        return f"## 今日世界热点\n{extracted}"

    def _extract_for_report(self, content: str, max_chars: int = 1500) -> str:
        """从世界新闻文件中智能提取报告用内容。

        优先提取「今日精选」板块的标题和选择理由；
        兼容旧格式的「重点关注建议」板块。
        """
        # 新格式：提取「今日精选」中的标题 + 选择理由
        pattern = r'## 今日精选.*?\n(.*?)(?=\n---\n|\Z)'
        select_match = re.search(pattern, content, re.DOTALL)
        if select_match:
            selected = select_match.group(1).strip()
            lines = []
            for para in selected.split("\n### "):
                para = para.strip()
                if not para or not (para.startswith("精选") or para.startswith("### 精选")):
                    continue
                head = para.split("\n")[0].strip()
                if head:
                    lines.append(f"- {head}")
                why_match = re.search(r'\*\*为什么选这篇\*\*[：:]\s*(.+?)(?=\n|$)', para)
                if why_match:
                    lines.append(f"  {why_match.group(1)}")
            if lines:
                result = "\n".join(lines)
                if len(result) <= max_chars:
                    return result
                return result[:max_chars].rsplit("\n", 1)[0]

        # 旧格式兼容：「重点关注建议」
        suggest_match = re.search(
            r'## 重点关注建议\n(.*?)(?=\n## 新闻详情|\n---\n## )',
            content, re.DOTALL
        )
        if suggest_match:
            suggestions = suggest_match.group(0).strip()
            if len(suggestions) <= max_chars:
                return suggestions
            return suggestions[:max_chars].rsplit("\n", 1)[0]

        return content[:max_chars]

    def _lazy_fetch(self, date_str: str) -> "Optional[Path]":
        try:
            from huaqi_src.layers.data.world.pipeline import WorldPipeline
            import datetime
            pipeline = WorldPipeline(data_dir=self._data_dir)
            target_date = datetime.date.fromisoformat(date_str)
            success = pipeline.run(date=target_date)
            if not success:
                return None
            return self._data_dir / "world" / f"{date_str}.md"
        except Exception as e:
            print(f"[WorldProvider] lazy 补采失败: {e}")
            return None


try:
    from huaqi_src.config.paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(WorldProvider(_data_dir))
except Exception:
    pass
