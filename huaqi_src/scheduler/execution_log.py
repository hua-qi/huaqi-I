import sqlite3
import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class LogEntry:
    id: int
    job_id: str
    scheduled_at: datetime.datetime
    status: str
    started_at: datetime.datetime
    finished_at: Optional[datetime.datetime]
    error: Optional[str]


class JobExecutionLog:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_execution_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id       TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'running',
                    started_at   TEXT NOT NULL,
                    finished_at  TEXT,
                    error        TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_scheduled
                ON job_execution_log (job_id, scheduled_at)
            """)

    def write_start(self, job_id: str, scheduled_at: datetime.datetime) -> int:
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO job_execution_log (job_id, scheduled_at, status, started_at) VALUES (?, ?, 'running', ?)",
                (job_id, scheduled_at.isoformat(), now),
            )
            return cursor.lastrowid

    def write_result(self, entry_id: int, status: str, error: Optional[str] = None):
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE job_execution_log SET status=?, finished_at=?, error=? WHERE id=?",
                (status, now, error, entry_id),
            )

    def has_success(self, job_id: str, scheduled_at: datetime.datetime) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM job_execution_log WHERE job_id=? AND scheduled_at=? AND status='success' LIMIT 1",
                (job_id, scheduled_at.isoformat()),
            ).fetchone()
            return row is not None

    def get_latest(
        self, job_id: str, since: datetime.datetime, until: datetime.datetime
    ) -> List[LogEntry]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, job_id, scheduled_at, status, started_at, finished_at, error
                   FROM job_execution_log
                   WHERE job_id=? AND scheduled_at>=? AND scheduled_at<=?
                   ORDER BY scheduled_at DESC""",
                (job_id, since.isoformat(), until.isoformat()),
            ).fetchall()
        return [
            LogEntry(
                id=r[0],
                job_id=r[1],
                scheduled_at=datetime.datetime.fromisoformat(r[2]),
                status=r[3],
                started_at=datetime.datetime.fromisoformat(r[4]),
                finished_at=datetime.datetime.fromisoformat(r[5]) if r[5] else None,
                error=r[6],
            )
            for r in rows
        ]
