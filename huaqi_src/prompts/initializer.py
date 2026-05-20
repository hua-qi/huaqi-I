"""PromptInitializer：负责 prompts/ 目录的首次创建和增量更新。

- 如果 prompts/ 不存在 → 全量创建（从内置默认值）
- 如果 prompts/ 存在 → 只补充内置新增但本地缺失的文件
- 已存在的文件绝不覆盖（保护用户编辑）
- 自动生成/更新 INDEX.md
"""

from pathlib import Path
from typing import List


class PromptInitializer:
    """prompts/ 目录初始化器。"""

    def __init__(self, prompts_dir: Path) -> None:
        self._prompts_dir = Path(prompts_dir)

    def ensure(self) -> bool:
        """确保 prompts 目录存在且包含所有需要的文件。

        Returns:
            bool: 是否有新文件被创建
        """
        created = False
        self._prompts_dir.mkdir(parents=True, exist_ok=True)

        from huaqi_src.prompts._defaults import _BUILTIN_DEFAULTS, _BASE_FALLBACK

        # 1. 确保 base.md 存在
        base_path = self._prompts_dir / "base.md"
        if not base_path.exists():
            base_path.write_text(_BASE_FALLBACK, encoding="utf-8")
            created = True

        # 2. 确保所有内置场景文件存在（不覆盖已有）
        for scene_id, content in _BUILTIN_DEFAULTS.items():
            file_path = self._scene_to_path(scene_id)
            if not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                created = True

        # 3. 确保 INDEX.md 是最新的
        self.rebuild_index()

        return created

    def rebuild_index(self) -> None:
        """重新生成 INDEX.md，扫描当前所有 .md 文件。"""
        if not self._prompts_dir.exists():
            return

        md_files = sorted(
            f.relative_to(self._prompts_dir)
            for f in self._prompts_dir.rglob("*.md")
            if f.name != "INDEX.md"
        )

        lines = [
            "# 提示词索引",
            "",
            f"共 {len(md_files)} 个提示词文件。",
            "",
            "| 文件 | Scene ID | 影响的功能 |",
            "|------|----------|-----------|",
        ]

        for f in md_files:
            scene_id = self._path_to_scene(f)
            desc = self._describe_scene(scene_id, f)
            lines.append(f"| `{f}` | `{scene_id}` | {desc} |")

        lines += [
            "",
            "## 使用说明",
            "",
            "- 每个 `.md` 文件对应一个场景的提示词",
            "- 文件第一行 `<!-- scene: xxx | variables: a, b -->` 声明场景标识和模板变量",
            "- `---` 水平线分隔 system prompt（上）和 user prompt（下）",
            "- 修改文件后**立即生效**，无需重启",
            "- 删除文件后系统使用内置默认值",
            "- `base.md` 是所有场景共享的角色基线，修改它会影响所有场景",
        ]

        index_path = self._prompts_dir / "INDEX.md"
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def get_all_scenes(self) -> List[str]:
        """返回所有已安装场景的 scene ID 列表。"""
        if not self._prompts_dir.exists():
            return []
        scenes = []
        for f in self._prompts_dir.rglob("*.md"):
            if f.name == "INDEX.md":
                continue
            scenes.append(self._path_to_scene(f.relative_to(self._prompts_dir)))
        return sorted(scenes)

    # ── 内部方法 ──────────────────────────────────────────────

    def _scene_to_path(self, scene: str) -> Path:
        return self._prompts_dir / f"{scene.replace('.', '/')}.md"

    @staticmethod
    def _path_to_scene(rel_path: Path) -> str:
        """将相对路径转为 scene ID。"""
        s = str(rel_path.with_suffix(""))
        return s.replace("/", ".")

    @staticmethod
    def _describe_scene(scene_id: str, rel_path: Path) -> str:
        """根据 scene ID 返回功能描述。"""
        descriptions = {
            "base": "所有场景的角色基线",
            "agent.chat": "ChatAgent 对话 (`huaqi chat`)",
            "cli.chat": "CLI 交互模式",
            "scheduler.jobs": "6 个定时任务的 prompt",
            "scheduler.job_runner": "定时任务执行时的系统提示词",
            "layers.growth.telos.engine": "TELOS 信号分析引擎",
            "layers.growth.telos.context": "TELOS 上下文构建（4 种模式）",
            "layers.growth.telos.dimensions.people.extractor": "人物信息提取",
            "layers.growth.telos.dimensions.people.pipeline": "人物互动管道",
            "layers.capabilities.reports.morning": "晨间简报",
            "layers.capabilities.reports.daily": "日终复盘",
            "layers.capabilities.reports.weekly": "周报",
            "layers.capabilities.reports.quarterly": "季报",
            "layers.capabilities.reports.growth": "成长报告",
            "layers.capabilities.world_news_enricher_source": "世界新闻按源增强（per-source）",
            "layers.capabilities.world_news_enricher": "世界新闻富化与翻译（旧版，已废弃）",
            "layers.capabilities.learning.course": "学习课程生成",
            "layers.capabilities.onboarding.telos_generator": "引导式 TELOS 初始化",
            "layers.capabilities.personality.engine": "个性引擎系统提示词",
            "layers.capabilities.personality.updater": "人格画像自动更新",
            "layers.data.profile.narrative": "用户画像叙事生成",
            "layers.data.profile.extract": "用户信息提取",
            "layers.data.memory.relevance": "记忆相关性评估",
        }
        return descriptions.get(scene_id, f"{scene_id} 场景")


_prompts_initializer: "PromptInitializer | None" = None


def get_prompts_initializer(prompts_dir: Path = None) -> PromptInitializer:
    """获取全局 PromptInitializer 单例。"""
    global _prompts_initializer
    if _prompts_initializer is not None:
        return _prompts_initializer
    if prompts_dir is None:
        from huaqi_src.config.paths import get_data_dir
        data_dir = get_data_dir()
        if data_dir is None:
            raise RuntimeError("数据目录未初始化")
        prompts_dir = data_dir / "prompts"
    _prompts_initializer = PromptInitializer(prompts_dir)
    return _prompts_initializer
