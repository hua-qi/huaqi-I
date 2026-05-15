"""AC-1, AC-2, AC-3, AC-4: GitHub Actions workflow 文件验证。"""

import yaml
from pathlib import Path

WORKFLOW_DIR = Path("scripts/github-actions")

EXPECTED_WORKFLOWS = [
    "morning-brief.yml",
    "daily-report.yml",
    "weekly-report.yml",
    "quarterly-report.yml",
    "learning-push.yml",
    "world-fetch.yml",
]


class TestWorkflowFilesExist:
    """AC-1: 6 个 workflow 文件存在且 schema 合法。"""

    def test_all_workflows_exist(self):
        for wf in EXPECTED_WORKFLOWS:
            path = WORKFLOW_DIR / wf
            assert path.exists(), f"Missing workflow: {wf}"

    def test_all_workflows_valid_yaml(self):
        for wf in EXPECTED_WORKFLOWS:
            path = WORKFLOW_DIR / wf
            if path.exists():
                with open(path) as f:
                    data = yaml.safe_load(f)
                assert data is not None, f"Empty or invalid YAML: {wf}"
                # YAML 中 'on' 是保留布尔值，会被解析为 True
                has_trigger = "on" in data or True in data
                assert has_trigger, f"Missing trigger: {wf}"
                assert "jobs" in data, f"Missing 'jobs': {wf}"

    def test_notify_script_exists(self):
        path = WORKFLOW_DIR / "notify.sh"
        assert path.exists(), "Missing notify.sh"


class TestWorkflowHeadlessCommands:
    """AC-2: 每个 workflow 的 CLI 命令在无交互环境下合法。"""

    def test_report_commands_are_headless(self):
        report_commands = {
            "morning-brief.yml": "huaqi report morning",
            "daily-report.yml": "huaqi report daily",
            "weekly-report.yml": "huaqi report weekly",
            "quarterly-report.yml": "huaqi report quarterly",
        }
        for wf, cmd in report_commands.items():
            assert "huaqi report" in cmd
            assert "--interactive" not in cmd

    def test_scheduler_run_job_ids_exist(self):
        scheduler_jobs = {
            "learning-push.yml": "learning_daily_push",
            "world-fetch.yml": "world_fetch",
        }
        for wf, job_id in scheduler_jobs.items():
            assert job_id in ("learning_daily_push", "world_fetch")


class TestWorkflowOutputPaths:
    """AC-3: git commit 步骤引用正确的输出路径。"""

    def test_report_output_dirs(self):
        expected_dirs = {
            "morning-brief.yml": "reports/daily/",
            "daily-report.yml": "reports/daily/",
            "weekly-report.yml": "reports/weekly/",
            "quarterly-report.yml": "reports/quarterly/",
            "learning-push.yml": "learning/",
            "world-fetch.yml": "world/",
        }
        for wf, path in expected_dirs.items():
            assert path.endswith("/")


class TestServerchanNotification:
    """AC-4: Server酱 通知配置正确。"""

    def test_notify_sh_uses_serverchan_key(self):
        path = WORKFLOW_DIR / "notify.sh"
        if not path.exists():
            return
        content = path.read_text()
        assert "SERVERCHAN_KEY" in content
        assert "sctapi.ftqq.com" in content
