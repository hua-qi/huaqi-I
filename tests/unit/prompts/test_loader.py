"""PromptLoader 单元测试。

覆盖 AC-1 ~ AC-10。
"""
import pytest
import tempfile
from pathlib import Path


class TestPromptLoader:
    """PromptLoader 核心功能测试。"""

    @pytest.fixture
    def prompts_dir(self, tmp_path):
        """创建一个临时 prompts 目录，包含测试用 prompt 文件。"""
        d = tmp_path / "prompts"
        d.mkdir()
        return d

    @pytest.fixture
    def loader(self, prompts_dir):
        from huaqi_src.prompts.loader import PromptLoader

        return PromptLoader(prompts_dir)

    def _write_prompt(self, prompts_dir: Path, scene: str, content: str):
        """将 scene ID 转为文件路径并写入内容。"""
        file_path = prompts_dir / f"{scene.replace('.', '/')}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    # AC-1: PromptLoader 根据 scene ID 找到对应 .md 文件
    def test_loader_finds_file_by_scene(self, loader, prompts_dir):
        self._write_prompt(prompts_dir, "agent.chat", "你是 Huaqi。")
        system, user = loader.load("agent.chat")
        assert "你是 Huaqi。" in system
        assert user is None

    def test_loader_finds_nested_scene(self, loader, prompts_dir):
        """深层嵌套 scene 路径映射为多层目录。"""
        self._write_prompt(
            prompts_dir, "layers.growth.telos.engine", "TELOS Engine Prompt"
        )
        system, user = loader.load("layers.growth.telos.engine")
        assert "TELOS Engine Prompt" in system

    # AC-2: 正确解析 <!-- --> 元数据行
    def test_loader_parses_metadata(self, loader, prompts_dir):
        content = (
            "<!-- scene: agent.chat | variables: ctx, snapshot -->\n"
            "你是 Huaqi。\n"
        )
        self._write_prompt(prompts_dir, "agent.chat", content)
        system, user = loader.load("agent.chat")
        assert "Huaqi" in system
        # 元数据行本身不在返回内容中
        assert "<!--" not in system

    # AC-3: --- 分隔符正确分离 system/user
    def test_loader_splits_system_user(self, loader, prompts_dir):
        content = "你是 Huaqi。\n---\n用户上下文：{context}"
        self._write_prompt(prompts_dir, "test.split", content)
        system, user = loader.load("test.split", context="测试数据")
        assert "你是 Huaqi。" in system
        assert user.strip() == "用户上下文：测试数据"

    # AC-4: 无 --- 时整体作为 system prompt
    def test_loader_no_separator_is_system_only(self, loader, prompts_dir):
        content = "system only prompt"
        self._write_prompt(prompts_dir, "test.system_only", content)
        system, user = loader.load("test.system_only")
        assert "system only prompt" in system
        assert user is None

    # AC-5: --- 开头时整体作为 user prompt
    def test_loader_separator_at_start_is_user_only(self, loader, prompts_dir):
        content = "---\nuser only prompt: {name}"
        self._write_prompt(prompts_dir, "test.user_only", content)
        system, user = loader.load("test.user_only", name="小明")
        assert system is None
        assert user.strip() == "user only prompt: 小明"

    # AC-6: {var_name} 模板变量正确替换
    def test_template_variable_injection(self, loader, prompts_dir):
        content = "你好 {name}，你的{telos_snapshot}"
        self._write_prompt(prompts_dir, "test.template", content)
        system, user = loader.load(
            "test.template", name="子蒙", telos_snapshot="核心认知快照"
        )
        assert "子蒙" in system
        assert "核心认知快照" in system
        assert "{" not in system  # 所有变量都已替换

    def test_template_multiple_same_variable(self, loader, prompts_dir):
        """同一变量多次出现，全部替换。"""
        content = "{name} 你好，{name}，你的 {attr}"
        self._write_prompt(prompts_dir, "test.multi", content)
        system, user = loader.load("test.multi", name="子蒙", attr="状态")
        assert "子蒙 你好，子蒙，你的 状态" in system

    # AC-7: 缺失变量抛出异常
    def test_missing_variable_raises(self, loader, prompts_dir):
        content = "你好 {name}，你的 {missing_var}"
        self._write_prompt(prompts_dir, "test.missing_var", content)
        with pytest.raises(KeyError):
            loader.load("test.missing_var", name="子蒙")

    # AC-8: 文件不存在时回退到内置默认值
    def test_fallback_on_missing_file(self, loader, prompts_dir):
        """场景文件不存在时，从内置默认值加载。"""
        system, user = loader.load("nonexistent.scene")
        # 应该返回内置默认值，不抛异常
        assert system is not None or user is not None

    def test_fallback_on_missing_file_returns_string(self, loader, prompts_dir):
        """回退值至少是有效字符串。"""
        system, user = loader.load("completely.made.up.scene")
        # 至少有一端非空
        has_content = (system and len(system) > 0) or (user and len(user) > 0)
        assert has_content, "回退值不应为空"

    # AC-9: 热更新——修改文件后下一次 load() 使用新内容
    def test_hot_reload(self, loader, prompts_dir):
        content_v1 = "版本1"
        self._write_prompt(prompts_dir, "test.hot", content_v1)
        system1, _ = loader.load("test.hot")
        assert "版本1" in system1

        # 修改文件
        content_v2 = "版本2——已更新"
        self._write_prompt(prompts_dir, "test.hot", content_v2)
        system2, _ = loader.load("test.hot")
        assert "版本2——已更新" in system2
        assert system1 != system2

    # AC-10: 中文/emoji/特殊 Unicode 字符热加载
    def test_unicode_hot_reload(self, loader, prompts_dir):
        content = "你好！🎉 Huaqi 花旗 — 你的成长伙伴。emoji: 😊🌟🔥"
        self._write_prompt(prompts_dir, "test.unicode", content)
        system, _ = loader.load("test.unicode")
        assert "🎉" in system
        assert "花旗" in system
        assert "😊" in system
        assert "🌟" in system
        assert "🔥" in system
        # 再次读取，确认热加载不破坏编码
        system2, _ = loader.load("test.unicode")
        assert system == system2


class TestPromptLoaderEdgeCases:
    """PromptLoader 边界情况测试。"""

    @pytest.fixture
    def prompts_dir(self, tmp_path):
        d = tmp_path / "prompts"
        d.mkdir()
        return d

    @pytest.fixture
    def loader(self, prompts_dir):
        from huaqi_src.prompts.loader import PromptLoader

        return PromptLoader(prompts_dir)

    def _write(self, prompts_dir, scene, content):
        path = prompts_dir / f"{scene.replace('.', '/')}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_empty_file_returns_empty_strings(self, loader, prompts_dir):
        """空文件：返回空字符串，不崩溃。"""
        self._write(prompts_dir, "test.empty", "")
        system, user = loader.load("test.empty")
        assert system is not None
        assert user is None

    def test_whitespace_only_file(self, loader, prompts_dir):
        self._write(prompts_dir, "test.whitespace", "   \n  \n  ")
        system, user = loader.load("test.whitespace")
        assert system is not None

    def test_only_metadata_line(self, loader, prompts_dir):
        """只有元数据行，没有实际内容。"""
        self._write(
            prompts_dir, "test.meta_only",
            "<!-- scene: test.meta_only | variables: none -->\n"
        )
        system, user = loader.load("test.meta_only")
        # 元数据行被移除后，system 应该为空字符串
        assert system is not None

    def test_multiple_separators_use_first(self, loader, prompts_dir):
        """多个 --- 时，第一个作为分界。"""
        content = "system part\n---\nuser part\n---\n ignored"
        self._write(prompts_dir, "test.multi_sep", content)
        system, user = loader.load("test.multi_sep")
        assert "system part" in system
        assert "user part" in user

    def test_metadata_without_variables_field(self, loader, prompts_dir):
        """metadata 无 variables 字段也能正常工作。"""
        content = "<!-- scene: test.no_vars -->\n你好"
        self._write(prompts_dir, "test.no_vars", content)
        system, user = loader.load("test.no_vars")
        assert "你好" in system
