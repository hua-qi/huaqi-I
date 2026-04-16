import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from huaqi_src.layers.data.collectors.work_signal_ingester import WorkSignalIngester
from huaqi_src.layers.data.collectors.work_data_source import (
    _work_source_registry,
    register_work_source,
)


@pytest.fixture(autouse=True)
def clear_registry():
    _work_source_registry.clear()
    yield
    _work_source_registry.clear()


@pytest.fixture
def mock_pipeline():
    p = MagicMock()
    p.process = AsyncMock(return_value={})
    return p


@pytest.fixture
def mock_telos_manager():
    from huaqi_src.config.errors import DimensionNotFoundError
    mgr = MagicMock()
    mgr.get.side_effect = DimensionNotFoundError("not found")
    return mgr


@pytest.fixture
def mock_signal_store():
    return MagicMock()


async def test_ingest_calls_pipeline_for_each_doc(
    mock_pipeline, mock_telos_manager, mock_signal_store
):
    source = MagicMock()
    source.name = "test_source"
    source.fetch_documents.return_value = ["文档1", "文档2"]
    register_work_source(source)

    mock_telos_manager.get.side_effect = None
    mock_telos_manager.get.return_value = MagicMock()

    ingester = WorkSignalIngester(
        signal_store=mock_signal_store,
        pipeline=mock_pipeline,
        telos_manager=mock_telos_manager,
        user_id="user1",
    )
    count = await ingester.ingest()
    assert count == 2
    assert mock_pipeline.process.call_count == 2


async def test_ingest_creates_work_style_dimension_if_missing(
    mock_pipeline, mock_telos_manager, mock_signal_store
):
    source = MagicMock()
    source.name = "s"
    source.fetch_documents.return_value = []
    register_work_source(source)

    ingester = WorkSignalIngester(
        signal_store=mock_signal_store,
        pipeline=mock_pipeline,
        telos_manager=mock_telos_manager,
        user_id="user1",
    )
    await ingester.ingest()
    mock_telos_manager.create_custom.assert_called_once()


async def test_ingest_does_not_recreate_existing_work_style(
    mock_pipeline, mock_telos_manager, mock_signal_store
):
    source = MagicMock()
    source.name = "s"
    source.fetch_documents.return_value = []
    register_work_source(source)

    mock_telos_manager.get.side_effect = None
    mock_telos_manager.get.return_value = MagicMock()

    ingester = WorkSignalIngester(
        signal_store=mock_signal_store,
        pipeline=mock_pipeline,
        telos_manager=mock_telos_manager,
        user_id="user1",
    )
    await ingester.ingest()
    mock_telos_manager.create_custom.assert_not_called()


async def test_cli_chat_watcher_calls_ingester_after_work_log(tmp_path):
    from huaqi_src.layers.data.collectors.cli_chat_watcher import CLIChatWatcher
    from huaqi_src.layers.data.collectors.cli_chat_parser import CLIChatMessage, CLIChatSession

    mock_ingester = MagicMock()
    mock_ingester.ingest = AsyncMock(return_value=0)

    watcher = CLIChatWatcher(data_dir=tmp_path, work_signal_ingester=mock_ingester)

    session = CLIChatSession(
        session_id="sess1",
        messages=[CLIChatMessage(role="user", content="测试消息", timestamp=None)],
        time_start="2026-11-04T10:00:00Z",
        time_end="2026-11-04T10:30:00Z",
        project_dir="/some/project",
        git_branch="main",
    )
    fake_file = tmp_path / "session.jsonl"
    fake_file.touch()

    watcher._process_codeflicker_session(session, fake_file)
    mock_ingester.ingest.assert_called_once()


def test_work_signal_ingester_hooks_claude_md_writer_to_telos_manager(
    mock_pipeline, mock_telos_manager, mock_signal_store
):
    mock_writer = MagicMock()
    mock_telos_manager.get.side_effect = None
    mock_telos_manager.get.return_value = MagicMock()

    ingester = WorkSignalIngester(
        signal_store=mock_signal_store,
        pipeline=mock_pipeline,
        telos_manager=mock_telos_manager,
        user_id="user1",
        claude_md_writer=mock_writer,
    )
    assert mock_telos_manager.on_work_style_updated is mock_writer.sync


async def test_cli_chat_watcher_passes_since_to_ingester(tmp_path):
    from huaqi_src.layers.data.collectors.cli_chat_watcher import CLIChatWatcher
    from huaqi_src.layers.data.collectors.cli_chat_parser import CLIChatMessage, CLIChatSession
    from datetime import datetime, timezone

    mock_ingester = MagicMock()
    mock_ingester.ingest = AsyncMock(return_value=0)

    watcher = CLIChatWatcher(data_dir=tmp_path, work_signal_ingester=mock_ingester)

    session = CLIChatSession(
        session_id="sess2",
        messages=[CLIChatMessage(role="user", content="测试消息", timestamp=None)],
        time_start="2026-11-04T10:00:00Z",
        time_end="2026-11-04T10:30:00Z",
        project_dir="/some/project",
        git_branch="main",
    )
    fake_file = tmp_path / "session2.jsonl"
    fake_file.touch()

    watcher._process_codeflicker_session(session, fake_file)

    call_kwargs = mock_ingester.ingest.call_args
    assert call_kwargs is not None
    since_arg = call_kwargs.kwargs.get("since") or (call_kwargs.args[0] if call_kwargs.args else None)
    assert since_arg is not None
    assert isinstance(since_arg, datetime)
