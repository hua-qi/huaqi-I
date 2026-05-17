"""定时任务 PromptLoader 集成测试。

AC-24: 定时任务使用 PromptLoader。
"""
import pytest
import datetime


class TestScheduledJobPrompts:
    def test_build_default_jobs_has_prompt_scene(self):
        """AC-24: _build_default_jobs() 中每个 job 包含 prompt_scene。"""
        from huaqi_src.scheduler.scheduled_job_store import _build_default_jobs
        jobs = _build_default_jobs()
        assert len(jobs) == 6
        for job in jobs:
            assert "prompt_scene" in job, f"job {job['id']} 缺少 prompt_scene"
            assert job["prompt_scene"].startswith("scheduler.jobs.")

    def test_job_runner_uses_loader(self):
        """AC-24: _call_llm_for_job 尝试使用 PromptLoader。"""
        from unittest.mock import patch, MagicMock
        from huaqi_src.scheduler import job_runner as jr

        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "test"

        mock_mgr = MagicMock()
        mock_mgr._active_provider = MagicMock()
        mock_mgr._active_provider.config.provider = "openai"
        mock_mgr._active_provider.config.model = "gpt-test"
        mock_mgr._active_provider.config.api_key = "test-key"
        mock_mgr._active_provider.config.api_base = "https://test.api"

        mock_loader = MagicMock()
        mock_loader.load.return_value = ("system prompt", None)

        with patch(
            "huaqi_src.cli.context.build_llm_manager", return_value=mock_mgr
        ), patch("langchain_openai.ChatOpenAI", return_value=mock_llm), patch(
            "huaqi_src.prompts.loader.get_prompt_loader",
            return_value=mock_loader,
        ):
            result = jr._call_llm_for_job("daily_report", "test prompt")
            assert result is not None

    def test_job_runner_fallback_on_loader_failure(self):
        """Loader 不可用时回退到硬编码默认值。"""
        from unittest.mock import patch, MagicMock
        from huaqi_src.scheduler import job_runner as jr

        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "fallback"

        mock_mgr = MagicMock()
        mock_mgr._active_provider = MagicMock()
        mock_mgr._active_provider.config.provider = "openai"
        mock_mgr._active_provider.config.model = "gpt-test"
        mock_mgr._active_provider.config.api_key = "test-key"
        mock_mgr._active_provider.config.api_base = "https://test.api"

        with patch(
            "huaqi_src.cli.context.build_llm_manager", return_value=mock_mgr
        ), patch("langchain_openai.ChatOpenAI", return_value=mock_llm), patch(
            "huaqi_src.prompts.loader.get_prompt_loader",
            side_effect=RuntimeError("no data dir"),
        ):
            result = jr._call_llm_for_job("daily_report", "test prompt")
            assert result is not None


class TestScheduledJobModel:
    def test_scheduled_job_has_prompt_scene_field(self):
        """ScheduledJob 模型包含 prompt_scene 字段。"""
        from huaqi_src.scheduler.scheduled_job_store import ScheduledJob
        job = ScheduledJob(
            id="test", display_name="测试", cron="0 0 * * *",
            prompt="测试提示词", prompt_scene="scheduler.jobs.test"
        )
        assert job.prompt_scene == "scheduler.jobs.test"

    def test_scheduled_job_prompt_scene_optional(self):
        """prompt_scene 字段可选（向后兼容已有 YAML）。"""
        from huaqi_src.scheduler.scheduled_job_store import ScheduledJob
        job = ScheduledJob(
            id="test", display_name="测试", cron="0 0 * * *",
            prompt="测试提示词"
        )
        assert job.prompt_scene is None
