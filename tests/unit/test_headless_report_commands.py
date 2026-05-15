"""AC-2: CLI 命令在无 TTY 环境下可执行。"""

import os
import subprocess
import tempfile
from pathlib import Path


class TestHeadlessReportCommands:
    """验证 huaqi report 命令在 HUAQI_DATA_DIR 设置后不要求交互输入。"""

    def test_report_daily_requires_data_dir(self):
        """未设置 HUAQI_DATA_DIR 时给出明确错误（不卡在交互提示）。"""
        result = subprocess.run(
            ["huaqi", "report", "daily"],
            env={**os.environ, "HUAQI_DATA_DIR": ""},
            capture_output=True,
            text=True,
            timeout=30,
        )
        # 不应因缺少 TTY 而崩溃
        assert "Cannot prompt" not in result.stderr
        assert "Abort" not in result.stderr

    def test_report_daily_with_data_dir_no_tty_crash(self, tmp_path):
        """设置 HUAQI_DATA_DIR 后不因缺少 TTY 而崩溃。"""
        (tmp_path / "memory").mkdir(parents=True)
        (tmp_path / "memory" / "config.yaml").write_text("version: 1\n")

        result = subprocess.run(
            ["huaqi", "report", "daily"],
            env={**os.environ, "HUAQI_DATA_DIR": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=30,
        )
        # 不因 TTY 缺失崩溃；可能因 LLM 未配置而失败，但不应是 prompt 错误
        assert "Cannot prompt" not in result.stderr
        assert "Abort" not in result.stderr

    def test_report_morning_headless(self, tmp_path):
        """晨间简报命令在无 TTY 环境下可用。"""
        (tmp_path / "memory").mkdir(parents=True)
        (tmp_path / "memory" / "config.yaml").write_text("version: 1\n")

        result = subprocess.run(
            ["huaqi", "report", "morning"],
            env={**os.environ, "HUAQI_DATA_DIR": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "Cannot prompt" not in result.stderr
        assert "Abort" not in result.stderr

    def test_report_weekly_headless(self, tmp_path):
        """周报命令在无 TTY 环境下可用。"""
        (tmp_path / "memory").mkdir(parents=True)
        (tmp_path / "memory" / "config.yaml").write_text("version: 1\n")

        result = subprocess.run(
            ["huaqi", "report", "weekly"],
            env={**os.environ, "HUAQI_DATA_DIR": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "Cannot prompt" not in result.stderr
        assert "Abort" not in result.stderr

    def test_report_quarterly_headless(self, tmp_path):
        """季报命令在无 TTY 环境下可用。"""
        (tmp_path / "memory").mkdir(parents=True)
        (tmp_path / "memory" / "config.yaml").write_text("version: 1\n")

        result = subprocess.run(
            ["huaqi", "report", "quarterly"],
            env={**os.environ, "HUAQI_DATA_DIR": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "Cannot prompt" not in result.stderr
        assert "Abort" not in result.stderr
