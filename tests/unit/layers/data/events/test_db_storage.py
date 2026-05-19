from huaqi_src.layers.data.events.store import LocalDBStorage
from huaqi_src.layers.data.events.models import Event


def test_db_insert_and_retrieve():
    with LocalDBStorage(":memory:") as db:
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
