import sqlite3
from typing import List
from huaqi_src.core.event import Event

class LocalDBStorage:
    def __init__(self, db_path: str = "memory.db"):
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
