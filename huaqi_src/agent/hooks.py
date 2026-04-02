from datetime import datetime, timezone
from typing import Optional

from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore


def save_conversation_to_signal(
    user_id: str,
    user_message: str,
    assistant_message: str,
    signal_store: RawSignalStore,
    occurred_at: Optional[datetime] = None,
) -> None:
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc)

    content = f"[用户] {user_message}\n[Huaqi] {assistant_message}"
    signal = RawSignal(
        user_id=user_id,
        source_type=SourceType.AI_CHAT,
        timestamp=occurred_at,
        content=content,
        metadata={"user_message": user_message, "assistant_message": assistant_message},
    )
    signal_store.save(signal)
