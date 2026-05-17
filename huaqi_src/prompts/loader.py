"""PromptLoader：从数据目录加载场景提示词，支持热更新和模板变量注入。

文件格式：
    <!-- scene: a.b.c | variables: x, y -->
    system prompt 内容...
    ---
    user prompt 内容...

- scene ID 使用点号分隔，映射为文件路径，如 "agent.chat" → "agent/chat.md"
- --- 水平线以上为 system prompt，以下为 user prompt
- 无 --- 则整个文件为 system prompt
- 以 --- 开头则整体为 user prompt（system 为 None）
- {variable_name} 模板变量由调用方注入
"""

from pathlib import Path
from typing import Optional


class PromptLoader:
    """从数据目录按需加载场景提示词。

    每次调用 load() 都重新读取文件，实现热更新。
    文件不存在时回退到内置默认值。
    """

    def __init__(self, prompts_dir: Path) -> None:
        self._prompts_dir = Path(prompts_dir)

    @property
    def prompts_dir(self) -> Path:
        return self._prompts_dir

    def load(self, scene: str, **kwargs) -> tuple[Optional[str], Optional[str]]:
        """加载场景 prompt，返回 (system, user)。

        - system 可能为 None（user-only 场景）
        - user 可能为 None（system-only 场景）
        - 自动在 system 前拼接 base.md 角色基线（scene="base" 除外）

        Args:
            scene: 场景标识，点号分隔，如 "agent.chat"
            **kwargs: 模板变量，注入 prompt 中的 {var_name}
        """
        file_path = self._scene_to_path(scene)

        if file_path.exists():
            raw = file_path.read_text(encoding="utf-8")
        else:
            raw = self._get_fallback(scene)

        system, user = self._parse(raw)

        # 为 system 自动拼接 base.md（仅当文件本身有 system 内容时）
        if scene != "base" and system:
            base_system, _ = self._load_base()
            if base_system:
                system = f"{base_system}\n\n{system}"

        # 模板变量注入
        if kwargs:
            if system is not None:
                system = system.format(**kwargs)
            if user is not None:
                user = user.format(**kwargs)

        return system, user

    # ── 内部方法 ──────────────────────────────────────────────

    def _scene_to_path(self, scene: str) -> Path:
        return self._prompts_dir / f"{scene.replace('.', '/')}.md"

    def _load_base(self) -> tuple[Optional[str], Optional[str]]:
        """加载 base.md（不拼接自身）。"""
        base_path = self._prompts_dir / "base.md"
        if base_path.exists():
            raw = base_path.read_text(encoding="utf-8")
            return self._parse(raw)
        return self._get_fallback_base()

    @staticmethod
    def _parse(raw: str) -> tuple[Optional[str], Optional[str]]:
        """解析原始 markdown 内容，分离 system/user 并去除元数据行。

        Returns:
            (system, user) — 两端都可能为 None 或空字符串
        """
        # 剥离元数据行（<!-- ... -->）
        lines = raw.splitlines()
        content_lines = [
            line for line in lines
            if not (line.strip().startswith("<!--") and line.strip().endswith("-->"))
        ]
        stripped = "\n".join(content_lines).strip()

        if not stripped:
            return (stripped, None)

        # 以 ---\n 开头 → 整体为 user prompt（无 system 部分）
        if stripped.startswith("---\n"):
            return (None, stripped[4:].strip())

        # 查找第一个 \n---\n（独立成行的 ---，前面有内容）
        separator = "\n---\n"
        idx = stripped.find(separator)

        if idx == -1:
            # 无分隔符 → 整体为 system
            return (stripped, None)

        # 正常分隔
        system = stripped[:idx].strip()
        user = stripped[idx + len(separator):].strip()
        return (system, user if user else None)

    @staticmethod
    def _get_fallback(scene: str) -> str:
        """获取内置默认 prompt 内容（文件不存在时的回退）。"""
        from huaqi_src.prompts._defaults import _BUILTIN_DEFAULTS, _UNKNOWN_SCENE_FALLBACK
        return _BUILTIN_DEFAULTS.get(scene, _UNKNOWN_SCENE_FALLBACK)

    @staticmethod
    def _get_fallback_base() -> tuple[Optional[str], Optional[str]]:
        """base.md 不存在时的内置回退。"""
        from huaqi_src.prompts._defaults import _BASE_FALLBACK
        return PromptLoader._parse(_BASE_FALLBACK)


_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader(data_dir: Optional[Path] = None) -> PromptLoader:
    """获取全局 PromptLoader 单例。

    Args:
        data_dir: 数据目录。如果为 None，从配置中获取。
    """
    global _prompt_loader
    if _prompt_loader is not None:
        return _prompt_loader

    if data_dir is None:
        from huaqi_src.config.paths import get_data_dir
        data_dir = get_data_dir()
        if data_dir is None:
            raise RuntimeError("数据目录未初始化，请先运行 huaqi 配置向导")

    prompts_dir = Path(data_dir) / "prompts"
    _prompt_loader = PromptLoader(prompts_dir)
    return _prompt_loader
