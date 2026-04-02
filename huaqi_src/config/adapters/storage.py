import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from huaqi_src.config.adapters.storage_base import StorageAdapter
from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter


_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_signals (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    ingested_at  TEXT NOT NULL,
    content      TEXT NOT NULL,
    metadata     TEXT,
    raw_file_ref TEXT,
    processed    INTEGER DEFAULT 0,
    distilled    INTEGER DEFAULT 0,
    vectorized   INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_timestamp  ON raw_signals(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_user_processed  ON raw_signals(user_id, processed);
CREATE INDEX IF NOT EXISTS idx_user_source     ON raw_signals(user_id, source_type);
CREATE INDEX IF NOT EXISTS idx_user_distilled  ON raw_signals(user_id, distilled);
CREATE INDEX IF NOT EXISTS idx_user_vectorized ON raw_signals(user_id, vectorized);
"""


def _row_to_signal(row: sqlite3.Row) -> RawSignal:
    d = dict(row)
    d["processed"] = bool(d["processed"])
    d["distilled"] = bool(d["distilled"])
    d["vectorized"] = bool(d["vectorized"])
    if d.get("metadata"):
        d["metadata"] = json.loads(d["metadata"])
    return RawSignal(**{k: v for k, v in d.items() if k != "created_at"})


class SQLiteStorageAdapter(StorageAdapter):

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def save(self, signal: RawSignal) -> None:
        metadata = json.dumps(signal.metadata, ensure_ascii=False) if signal.metadata is not None else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO raw_signals
                (id, user_id, source_type, timestamp, ingested_at, content,
                 metadata, raw_file_ref, processed, distilled, vectorized, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.id,
                    signal.user_id,
                    signal.source_type.value,
                    signal.timestamp.isoformat(),
                    signal.ingested_at.isoformat(),
                    signal.content,
                    metadata,
                    signal.raw_file_ref,
                    int(signal.processed),
                    int(signal.distilled),
                    int(signal.vectorized),
                    signal.ingested_at.isoformat(),
                ),
            )

    def get(self, signal_id: str) -> Optional[RawSignal]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM raw_signals WHERE id = ?", (signal_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_signal(row)

    def query(self, filter: RawSignalFilter) -> List[RawSignal]:
        conditions = ["user_id = ?"]
        params: list = [filter.user_id]

        if filter.source_type is not None:
            conditions.append("source_type = ?")
            params.append(filter.source_type.value)
        if filter.processed is not None:
            conditions.append("processed = ?")
            params.append(filter.processed)
        if filter.distilled is not None:
            conditions.append("distilled = ?")
            params.append(filter.distilled)
        if filter.vectorized is not None:
            conditions.append("vectorized = ?")
            params.append(filter.vectorized)
        if filter.since is not None:
            conditions.append("timestamp >= ?")
            params.append(filter.since.isoformat())
        if filter.until is not None:
            conditions.append("timestamp <= ?")
            params.append(filter.until.isoformat())

        sql = (
            f"SELECT * FROM raw_signals WHERE {' AND '.join(conditions)} "
            f"ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        )
        params.extend([filter.limit, filter.offset])

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_signal(r) for r in rows]

    def mark_processed(self, signal_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (signal_id,))

    def mark_distilled(self, signal_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE raw_signals SET distilled = 1 WHERE id = ?", (signal_id,))

    def mark_vectorized(self, signal_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE raw_signals SET vectorized = 1 WHERE id = ?", (signal_id,))

    def count(self, filter: RawSignalFilter) -> int:
        conditions = ["user_id = ?"]
        params: list = [filter.user_id]

        if filter.source_type is not None:
            conditions.append("source_type = ?")
            params.append(filter.source_type.value)
        if filter.processed is not None:
            conditions.append("processed = ?")
            params.append(filter.processed)
        if filter.distilled is not None:
            conditions.append("distilled = ?")
            params.append(filter.distilled)
        if filter.vectorized is not None:
            conditions.append("vectorized = ?")
            params.append(filter.vectorized)
        if filter.since is not None:
            conditions.append("timestamp >= ?")
            params.append(filter.since.isoformat())
        if filter.until is not None:
            conditions.append("timestamp <= ?")
            params.append(filter.until.isoformat())

        sql = f"SELECT COUNT(*) FROM raw_signals WHERE {' AND '.join(conditions)}"

        with self._connect() as conn:
            return conn.execute(sql, params).fetchone()[0]
