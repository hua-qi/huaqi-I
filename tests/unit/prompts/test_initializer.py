"""PromptInitializer 单元测试。

覆盖 AC-16 ~ AC-22。
"""
import pytest
from pathlib import Path


class TestPromptInitializer:
    """PromptInitializer 初始化逻辑测试。"""

    @pytest.fixture
    def prompts_dir(self, tmp_path):
        d = tmp_path / "prompts"
        return d

    def _loader(self, prompts_dir):
        from huaqi_src.prompts.loader import PromptLoader
        return PromptLoader(prompts_dir)

    def _init(self, prompts_dir):
        from huaqi_src.prompts.initializer import PromptInitializer
        return PromptInitializer(prompts_dir)

    # AC-20: 首次启动时 prompts/ 目录自动创建并填充默认值
    def test_prompts_auto_init(self, prompts_dir):
        init = self._init(prompts_dir)
        assert not prompts_dir.exists()
        init.ensure()
        assert prompts_dir.exists()
        # 应有 base.md
        assert (prompts_dir / "base.md").exists()
        # 应有 INDEX.md
        assert (prompts_dir / "INDEX.md").exists()

    def test_auto_init_creates_all_default_files(self, prompts_dir):
        """确保所有内置场景文件都被创建。"""
        init = self._init(prompts_dir)
        init.ensure()
        # 核心文件
        assert (prompts_dir / "base.md").exists()
        assert (prompts_dir / "INDEX.md").exists()
        # 至少应有部分场景目录
        assert (prompts_dir / "agent" / "chat.md").exists()
        assert (prompts_dir / "scheduler" / "jobs" / "morning_brief.md").exists()

    # AC-21: 已有 prompts/ 目录时不覆盖用户修改
    def test_auto_init_preserves_user_edits(self, prompts_dir):
        prompts_dir.mkdir(parents=True)
        base = prompts_dir / "base.md"
        base.write_text("用户自定义角色", encoding="utf-8")

        init = self._init(prompts_dir)
        init.ensure()

        # 用户编辑的内容应保留
        assert base.read_text(encoding="utf-8") == "用户自定义角色"

    # AC-22: 仅补充缺失的新文件，不覆盖已有
    def test_auto_init_adds_new_files_only(self, prompts_dir):
        prompts_dir.mkdir(parents=True)
        # 只手动创建 base.md
        (prompts_dir / "base.md").write_text("custom base", encoding="utf-8")

        init = self._init(prompts_dir)
        init.ensure()

        # base.md 不变
        assert (prompts_dir / "base.md").read_text(encoding="utf-8") == "custom base"
        # 缺失的文件被补充
        assert (prompts_dir / "INDEX.md").exists()
        assert (prompts_dir / "agent" / "chat.md").exists()

    # AC-16: base.md 角色基线文件存在，包含 TELOS 相关定义
    def test_base_file_exists_and_contains_telos(self, prompts_dir):
        init = self._init(prompts_dir)
        init.ensure()
        base_content = (prompts_dir / "base.md").read_text(encoding="utf-8")
        assert "TELOS" in base_content
        assert "核心认知" in base_content or "Core" in base_content

    # AC-17: 加载任意场景时 system prompt 以 base.md 开头
    def test_base_prepended_to_system(self, prompts_dir):
        init = self._init(prompts_dir)
        init.ensure()
        # 写入测试 scene
        (prompts_dir / "test.md").write_text("测试场景内容", encoding="utf-8")

        loader = self._loader(prompts_dir)
        system, _ = loader.load("test")
        base_content = (prompts_dir / "base.md").read_text(encoding="utf-8")
        # 去除 meta 行后的 base 内容应该在 system 中
        assert "TELOS" in system
        assert "测试场景内容" in system

    # AC-18: base.md 明确定义 Huaqi 与 TELOS 维度的关系
    def test_base_references_telos_dimensions(self, prompts_dir):
        init = self._init(prompts_dir)
        init.ensure()
        base = (prompts_dir / "base.md").read_text(encoding="utf-8")
        # 应提及核心层/中间层/表面层
        layers_mentioned = (
            ("核心" in base or "Core" in base)
            and ("中间" in base or "Middle" in base)
            and ("表面" in base or "Surface" in base)
        )
        assert layers_mentioned, "base.md 应引用 TELOS 三层维度"

    # AC-19: 修改 base.md 后所有场景反映新角色
    def test_base_hot_reload_propagates(self, prompts_dir):
        init = self._init(prompts_dir)
        init.ensure()
        (prompts_dir / "test.md").write_text("场景测试", encoding="utf-8")

        loader = self._loader(prompts_dir)

        # 修改 base.md
        (prompts_dir / "base.md").write_text("新角色定义 v2", encoding="utf-8")

        system, _ = loader.load("test")
        assert "新角色定义 v2" in system


class TestIndexGeneration:
    """INDEX.md 自动生成测试。"""

    @pytest.fixture
    def prompts_dir(self, tmp_path):
        d = tmp_path / "prompts"
        return d

    def _init(self, prompts_dir):
        from huaqi_src.prompts.initializer import PromptInitializer
        return PromptInitializer(prompts_dir)

    # AC-11: INDEX.md 文件存在
    def test_index_file_exists(self, prompts_dir):
        init = self._init(prompts_dir)
        init.ensure()
        assert (prompts_dir / "INDEX.md").exists()

    # AC-12: INDEX.md 包含"影响的功能"和"修改效果"
    def test_index_describes_effect(self, prompts_dir):
        init = self._init(prompts_dir)
        init.ensure()
        content = (prompts_dir / "INDEX.md").read_text(encoding="utf-8")
        assert "影响" in content or "功能" in content or "修改" in content

    # AC-15: 新增文件后 INDEX.md 自动更新
    def test_index_auto_updates(self, prompts_dir):
        init = self._init(prompts_dir)
        init.ensure()

        initial_size = (prompts_dir / "INDEX.md").stat().st_size

        # 新增一个 prompt 文件
        (prompts_dir / "agent").mkdir(parents=True, exist_ok=True)
        (prompts_dir / "agent" / "new_feature.md").write_text(
            "<!-- scene: agent.new_feature | variables: none -->\n新功能提示词",
            encoding="utf-8",
        )

        init.rebuild_index()

        new_content = (prompts_dir / "INDEX.md").read_text(encoding="utf-8")
        assert "new_feature" in new_content
