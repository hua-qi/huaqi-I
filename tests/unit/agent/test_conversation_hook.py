from datetime import datetime, timezone
from pathlib import Path

from huaqi_src.agent.hooks import save_conversation_to_signal
from huaqi_src.layers.data.raw_signal.models import SourceType, RawSignalFilter
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter


def test_save_conversation_creates_raw_signal(tmp_path):
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    store = RawSignalStore(adapter=adapter)

    save_conversation_to_signal(
        user_id="u1",
        user_message="我最近很迷茫，不知道该做什么",
        assistant_message="听起来你在寻找方向感，能说说具体是什么让你感到迷茫吗？",
        signal_store=store,
        occurred_at=datetime.now(timezone.utc),
    )

    signals = store.query(RawSignalFilter(user_id="u1"))
    assert len(signals) == 1
    assert signals[0].source_type == SourceType.AI_CHAT
    assert "迷茫" in signals[0].content
