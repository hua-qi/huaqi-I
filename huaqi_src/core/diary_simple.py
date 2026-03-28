"""日记系统 - 单用户简化版

日记存储在 memory/diary/ 目录下，按日期组织
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import yaml
import re


@dataclass
class DiaryEntry:
    """日记条目"""
    date: str  # YYYY-MM-DD
    content: str
    mood: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class DiaryStore:
    """日记存储 - 单用户"""

    def __init__(self, memory_dir: Path, git_committer=None):
        self.memory_dir = memory_dir
        self.diary_dir = memory_dir / "diary"
        self.diary_dir.mkdir(parents=True, exist_ok=True)
        self._git_committer = git_committer

    def _get_diary_path(self, date: str, suffix: str = "") -> Path:
        """获取日记文件路径

        Args:
            date: 日期 (YYYY-MM-DD)
            suffix: 可选后缀，用于区分同一天的多篇日记
        """
        # 按年/月组织目录
        year_month = date[:7]  # YYYY-MM
        dir_path = self.diary_dir / year_month
        dir_path.mkdir(parents=True, exist_ok=True)

        if suffix:
            return dir_path / f"{date}-{suffix}.md"
        return dir_path / f"{date}.md"

    def _get_unique_diary_path(self, date: str, original_name: str = "") -> Path:
        """获取唯一的日记文件路径，避免覆盖

        Args:
            date: 日期 (YYYY-MM-DD)
            original_name: 原始文件名（用于生成唯一标识）

        Returns:
            Path: 唯一的文件路径
        """
        base_path = self._get_diary_path(date)
        if not base_path.exists():
            return base_path

        # 已有同名文件，需要生成唯一标识
        if original_name:
            # 使用原始文件名的哈希或简化版本作为后缀
            import hashlib
            suffix = hashlib.md5(original_name.encode()).hexdigest()[:8]
        else:
            # 使用当前时间戳
            suffix = datetime.now().strftime("%H%M%S")

        return self._get_diary_path(date, suffix)

    def save(self, date: str, content: str, mood: Optional[str] = None, tags: List[str] = None, suffix: str = "") -> DiaryEntry:
        """保存日记

        Args:
            date: 日期 (YYYY-MM-DD)
            content: 日记内容
            mood: 情绪 (可选)
            tags: 标签列表 (可选)
            suffix: 文件后缀，用于区分同一天的多篇日记

        Returns:
            DiaryEntry: 日记条目
        """
        if suffix:
            filepath = self._get_diary_path(date, suffix)
        else:
            filepath = self._get_diary_path(date)

        entry = DiaryEntry(
            date=date,
            content=content,
            mood=mood,
            tags=tags or [],
            updated_at=datetime.now().isoformat()
        )

        # 构建 Markdown 内容
        md_content = self._build_markdown(entry)

        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        return entry

    def _build_markdown(self, entry: DiaryEntry) -> str:
        """构建 Markdown 内容"""
        lines = []

        # YAML Frontmatter
        lines.append("---")
        lines.append(f"date: {entry.date}")
        lines.append(f"created_at: {entry.created_at}")
        lines.append(f"updated_at: {entry.updated_at}")
        if entry.mood:
            lines.append(f"mood: {entry.mood}")
        if entry.tags:
            lines.append(f"tags: {entry.tags}")
        lines.append("---")
        lines.append("")

        # 日记内容
        lines.append(entry.content)
        lines.append("")

        return "\n".join(lines)

    def get(self, date: str) -> Optional[DiaryEntry]:
        """获取指定日期的日记"""
        filepath = self._get_diary_path(date)

        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return self._parse_markdown(content)

    def _parse_markdown(self, content: str) -> DiaryEntry:
        """解析 Markdown 内容"""
        # 解析 frontmatter
        frontmatter = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1].strip()
                body = parts[2].strip()

                # 简单解析 YAML
                for line in frontmatter_text.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.strip()

                        if key == "tags":
                            # 解析列表格式 [tag1, tag2]
                            value = [t.strip().strip('"\'') for t in value.strip("[]").split(",") if t.strip()]

                        frontmatter[key] = value

        return DiaryEntry(
            date=frontmatter.get("date", ""),
            content=body,
            mood=frontmatter.get("mood"),
            tags=frontmatter.get("tags", []),
            created_at=frontmatter.get("created_at", ""),
            updated_at=frontmatter.get("updated_at", "")
        )

    def list_entries(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50
    ) -> List[DiaryEntry]:
        """列出日记条目

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 最大数量

        Returns:
            List[DiaryEntry]: 日记条目列表
        """
        entries = []

        # 遍历所有 Markdown 文件
        for filepath in self.diary_dir.rglob("*.md"):
            try:
                # 从文件名解析日期
                date_str = filepath.stem  # YYYY-MM-DD

                # 日期过滤
                if start_date and date_str < start_date:
                    continue
                if end_date and date_str > end_date:
                    continue

                entry = self.get(date_str)
                if entry:
                    entries.append(entry)

                if len(entries) >= limit:
                    break

            except Exception:
                continue

        # 按日期倒序
        entries.sort(key=lambda x: x.date, reverse=True)

        return entries

    def search(self, query: str) -> List[DiaryEntry]:
        """搜索日记内容

        Args:
            query: 搜索关键词

        Returns:
            List[DiaryEntry]: 匹配的日记条目
        """
        results = []
        query_lower = query.lower()

        for filepath in self.diary_dir.rglob("*.md"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                if query_lower in content.lower():
                    date_str = filepath.stem
                    entry = self.get(date_str)
                    if entry:
                        results.append(entry)

            except Exception:
                continue

        # 按日期倒序
        results.sort(key=lambda x: x.date, reverse=True)

        return results

    def delete(self, date: str) -> bool:
        """删除指定日期的日记

        Args:
            date: 日期 (YYYY-MM-DD)

        Returns:
            bool: 是否成功
        """
        filepath = self._get_diary_path(date)

        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def get_summary(self, date: Optional[str] = None) -> str:
        """获取日记摘要（用于 AI 上下文）

        Args:
            date: 指定日期，默认为最近一篇

        Returns:
            str: 日记摘要
        """
        if date:
            entry = self.get(date)
        else:
            # 获取最近一篇
            entries = self.list_entries(limit=1)
            entry = entries[0] if entries else None

        if not entry:
            return ""

        # 生成摘要
        lines = []
        lines.append(f"日期: {entry.date}")
        if entry.mood:
            lines.append(f"情绪: {entry.mood}")
        if entry.tags:
            lines.append(f"标签: {', '.join(entry.tags)}")
        lines.append("内容:")

        # 截断内容（保留前 500 字符）
        content = entry.content[:500]
        if len(entry.content) > 500:
            content += "..."
        lines.append(content)

        return "\n".join(lines)

    def import_from_markdown(self, source_path: Path, date_from_filename: bool = True) -> int:
        """从 Markdown 文件批量导入日记

        Args:
            source_path: 源文件或目录路径
            date_from_filename: 是否从文件名解析日期 (YYYY-MM-DD.md)

        Returns:
            int: 成功导入的数量
        """
        import re
        from datetime import datetime

        count = 0
        source = Path(source_path)

        # 收集所有 markdown 文件
        if source.is_file():
            files = [source]
        elif source.is_dir():
            files = list(source.rglob("*.md"))
        else:
            return 0

        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # 尝试从文件名解析日期
                date_str = None
                if date_from_filename:
                    # 匹配 YYYY-MM-DD 格式
                    match = re.search(r'(\d{4}-\d{2}-\d{2})', filepath.stem)
                    if match:
                        date_str = match.group(1)

                # 如果文件名没有日期，尝试从 frontmatter 解析
                if not date_str:
                    frontmatter, _ = self._parse_frontmatter_raw(content)
                    date_str = frontmatter.get("date")

                # 如果还是没有，使用文件修改时间
                if not date_str:
                    mtime = filepath.stat().st_mtime
                    date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")

                # 解析内容
                entry = self._parse_markdown(content)

                # 生成唯一路径避免覆盖
                filepath = self._get_unique_diary_path(date_str, filepath.name)
                suffix = filepath.stem.replace(date_str, "").lstrip("-") if date_str in filepath.stem else ""

                # 保存日记
                self.save(
                    date=date_str,
                    content=entry.content,
                    mood=entry.mood,
                    tags=entry.tags,
                    suffix=suffix
                )
                count += 1

            except Exception as e:
                print(f"导入失败 {filepath}: {e}")
                continue

        return count

    def _parse_frontmatter_raw(self, content: str) -> tuple[dict, str]:
        """原始解析 frontmatter，返回字典和正文"""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        frontmatter_text = parts[1].strip()
        body = parts[2].strip()

        frontmatter = {}
        for line in frontmatter_text.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                if key == "tags":
                    value = [t.strip().strip('"').strip("'") for t in value.strip("[]").split(",") if t.strip()]

                frontmatter[key] = value

        return frontmatter, body

    def get_recent_context(self, days: int = 7) -> str:
        """获取最近日记上下文

        Args:
            days: 最近几天

        Returns:
            str: 汇总上下文
        """
        from datetime import timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        entries = self.list_entries(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )

        if not entries:
            return ""

        lines = [f"最近 {days} 天日记概要:"]
        for entry in entries:
            lines.append(f"\n--- {entry.date} ---")
            if entry.mood:
                lines.append(f"情绪: {entry.mood}")
            # 每篇保留前 200 字符
            content = entry.content[:200]
            if len(entry.content) > 200:
                content += "..."
            lines.append(content)

        return "\n".join(lines)
