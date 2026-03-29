import sqlite3
from typing import List, Optional
from pathlib import Path
from huaqi_src.core.event import Event
from huaqi_src.core.config_paths import get_data_dir

class LocalDBStorage:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = get_data_dir()
            if data_dir:
                db_path = str(data_dir / "events.db")
            else:
                db_path = "events.db"
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                source TEXT,
                actor TEXT,
                content TEXT,
                context_id TEXT
            )
        ''')
        self.conn.commit()

    def insert_event(self, event: Event):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO events (timestamp, source, actor, content, context_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (event.timestamp, event.source, event.actor, event.content, event.context_id))
        self.conn.commit()

    def get_recent_events(self, limit: int = 10) -> List[Event]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT timestamp, source, actor, content, context_id FROM events ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        return [Event(timestamp=r[0], source=r[1], actor=r[2], content=r[3], context_id=r[4]) for r in rows]

    def search_events(self, query: str, limit: int = 5) -> List[Event]:
        cursor = self.conn.cursor()
        search_pattern = f'%{query}%'
        cursor.execute(
            'SELECT timestamp, source, actor, content, context_id FROM events WHERE content LIKE ? OR actor LIKE ? OR source LIKE ? ORDER BY timestamp DESC LIMIT ?', 
            (search_pattern, search_pattern, search_pattern, limit)
        )
        rows = cursor.fetchall()
        return [Event(timestamp=r[0], source=r[1], actor=r[2], content=r[3], context_id=r[4]) for r in rows]
