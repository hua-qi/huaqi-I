from unittest.mock import patch, MagicMock


def test_learning_push_job_exists_in_defaults():
    from huaqi_src.scheduler.scheduled_job_store import _DEFAULT_JOBS
    ids = [j["id"] for j in _DEFAULT_JOBS]
    assert "learning_daily_push" in ids


def test_learning_push_job_has_prompt():
    from huaqi_src.scheduler.scheduled_job_store import _DEFAULT_JOBS
    job = next(j for j in _DEFAULT_JOBS if j["id"] == "learning_daily_push")
    assert len(job["prompt"]) > 0


def test_run_scheduled_job_calls_chat_agent(tmp_path):
    mock_agent = MagicMock()
    with patch("huaqi_src.agent.chat_agent.ChatAgent", return_value=mock_agent):
        from huaqi_src.scheduler.job_runner import _run_scheduled_job
        _run_scheduled_job("learning_daily_push", "推送今日学习内容", None)
    mock_agent.run.assert_called_once()
