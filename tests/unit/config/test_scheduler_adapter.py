import pytest
from huaqi_src.config.adapters.scheduler_base import SchedulerAdapter


def test_scheduler_adapter_is_abstract():
    with pytest.raises(TypeError):
        SchedulerAdapter()


def test_scheduler_adapter_interface():
    methods = ["start", "stop", "add_interval_job", "add_cron_job", "remove_job"]
    for m in methods:
        assert hasattr(SchedulerAdapter, m)
