"""从 LangGraph checkpoints 回填 RawSignal。

扫描 checkpoints.db 中每个会话的最新 checkpoint，
提取对话中的 HumanMessage/AIMessage 对，生成 AI_CHAT 类型的信号。
使用确定性 UUID（thread_id + pair_index）确保多次运行幂等。
"""

import hashlib
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import ormsgpack

from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore

logger = logging.getLogger(__name__)


def _deterministic_id(seed: str) -> str:
    """基于种子字符串生成确定性 UUID5。"""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


def backfill_from_checkpoints(
    checkpoints_db_path: Path,
    signal_store: RawSignalStore,
    user_id: str = "default",
) -> Dict:
    """从 LangGraph checkpoints.db 回填信号。

    Args:
        checkpoints_db_path: checkpoints.db 的路径。
        signal_store: RawSignalStore 实例。
        user_id: 信号的 user_id。

    Returns:
        {"backfilled": N, "skipped": M, "errors": E}
    """
    if not checkpoints_db_path.exists():
        return {"backfilled": 0, "skipped": 0, "errors": 0}

    ckpt_db = sqlite3.connect(str(checkpoints_db_path))

    threads = ckpt_db.execute(
        """SELECT thread_id, checkpoint_id, checkpoint
           FROM checkpoints c1
           WHERE rowid = (
               SELECT MAX(rowid) FROM checkpoints c2
               WHERE c2.thread_id = c1.thread_id
           )"""
    ).fetchall()

    from langgraph.checkpoint.serde.jsonplus import _msgpack_ext_hook

    backfilled = 0
    skipped = 0
    errors = 0

    for tid, cid, blob in threads:
        try:
            data = ormsgpack.unpackb(blob, ext_hook=_msgpack_ext_hook)
            msgs = data.get("channel_values", {}).get(
                "__start__", {}
            ).get("messages", data.get("channel_values", {}).get("messages", []))

            ts_str = data.get("ts", "")
            try:
                ts = (
                    datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts_str
                    else datetime.now(timezone.utc)
                )
            except ValueError:
                ts = datetime.now(timezone.utc)

            pair_index = 0
            user_msg = None
            for m in msgs:
                content = ""
                msg_type = ""
                if isinstance(m, dict):
                    msg_type = m.get("type", "")
                    content = m.get("content", "")
                elif hasattr(m, "type") and hasattr(m, "content"):
                    msg_type = m.type
                    content = m.content

                if msg_type in ("human", "HumanMessage"):
                    user_msg = content
                elif msg_type in ("ai", "AIMessage") and user_msg is not None:
                    sig_id = _deterministic_id(f"{tid}:{pair_index}")

                    existing = signal_store.get(sig_id)
                    if existing is not None:
                        skipped += 1
                    else:
                        signal = RawSignal(
                            id=sig_id,
                            user_id=user_id,
                            source_type=SourceType.AI_CHAT,
                            timestamp=ts,
                            content=f"[用户] {user_msg}\n[Huaqi] {content}",
                            metadata={
                                "user_message": user_msg,
                                "assistant_message": content,
                                "thread_id": tid,
                                "checkpoint_id": cid,
                                "backfilled": True,
                            },
                        )
                        signal_store.save(signal)
                        backfilled += 1

                    pair_index += 1
                    user_msg = None

        except Exception as e:
            errors += 1
            logger.debug(f"Backfill error thread={tid[:20]}: {e}")

    ckpt_db.close()
    return {"backfilled": backfilled, "skipped": skipped, "errors": errors}
