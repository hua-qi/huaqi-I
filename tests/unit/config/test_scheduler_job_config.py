from huaqi_src.config.manager import AppConfig, SchedulerJobConfig


def test_scheduler_job_config_defaults():
    cfg = SchedulerJobConfig()
    assert cfg.enabled is True
    assert cfg.cron is None


def test_scheduler_job_config_custom():
    cfg = SchedulerJobConfig(enabled=False, cron="0 9 * * *")
    assert cfg.enabled is False
    assert cfg.cron == "0 9 * * *"


def test_app_config_has_scheduler_jobs_field():
    config = AppConfig()
    assert hasattr(config, "scheduler_jobs")
    assert isinstance(config.scheduler_jobs, dict)
    assert config.scheduler_jobs == {}


def test_app_config_scheduler_jobs_can_be_set():
    config = AppConfig(
        scheduler_jobs={
            "morning_brief": SchedulerJobConfig(enabled=True, cron="0 7 * * *"),
            "weekly_report": SchedulerJobConfig(enabled=False),
        }
    )
    assert config.scheduler_jobs["morning_brief"].cron == "0 7 * * *"
    assert config.scheduler_jobs["weekly_report"].enabled is False


def test_app_config_serializes_scheduler_jobs():
    config = AppConfig(
        scheduler_jobs={
            "morning_brief": SchedulerJobConfig(enabled=True, cron="0 8 * * *"),
        }
    )
    data = config.model_dump()
    assert "scheduler_jobs" in data
    assert data["scheduler_jobs"]["morning_brief"]["enabled"] is True
