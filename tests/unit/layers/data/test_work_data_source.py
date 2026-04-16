from unittest.mock import MagicMock
from huaqi_src.layers.data.collectors.work_data_source import (
    WorkDataSource,
    register_work_source,
    get_work_sources,
    _work_source_registry,
)


def test_register_and_get():
    _work_source_registry.clear()
    source = MagicMock(spec=WorkDataSource)
    register_work_source(source)
    assert source in get_work_sources()


def test_get_returns_copy():
    _work_source_registry.clear()
    source = MagicMock(spec=WorkDataSource)
    register_work_source(source)
    result = get_work_sources()
    result.clear()
    assert len(get_work_sources()) == 1


def test_register_defaults_adds_three_sources():
    _work_source_registry.clear()
    from huaqi_src.layers.data.collectors.work_sources.registry import register_defaults
    register_defaults()
    names = [s.name for s in get_work_sources()]
    assert "codeflicker" in names
    assert "huaqi_docs" in names
    assert "kuaishou_docs" in names
