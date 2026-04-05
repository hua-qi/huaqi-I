import os
import sqlite3
from layers.data.events.store import EventStore

def test_event_store_save_and_retrieve(tmp_path):
    db_path = tmp_path / "test_events.db"
    store = EventStore(str(db_path))
    
    event_id = store.save("user.created", {"user_id": 123})
    
    assert event_id is not None
    events = store.get_unprocessed()
    assert len(events) == 1
    assert events[0]['event_type'] == "user.created"
    assert events[0]['payload'] == '{"user_id": 123}'
