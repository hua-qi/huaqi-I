from huaqi_src.core.db_storage import LocalDBStorage
from huaqi_src.core.event import Event
import sqlite3
import time

def test_db_insert_and_retrieve():
    # 使用内存数据库进行测试
    db = LocalDBStorage(":memory:")
    event = Event(
        timestamp=1700000000,
        source="wechat",
        actor="System",
        content="Hello world"
    )
    db.insert_event(event)
    
    results = db.get_recent_events(limit=1)
    assert len(results) == 1
    assert results[0].source == "wechat"
    assert results[0].content == "Hello world"
