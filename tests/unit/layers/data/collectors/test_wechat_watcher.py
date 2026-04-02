import sqlite3
from pathlib import Path
from unittest.mock import patch
from huaqi_src.layers.data.collectors.wechat_watcher import WeChatWatcher


def _make_wechat_db(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE Chat_张三 "
        "(id INTEGER PRIMARY KEY, CreateTime INTEGER, Des INTEGER, Message TEXT, Type INTEGER)"
    )
    conn.execute("INSERT INTO Chat_张三 VALUES (1, 1743300000, 1, '新消息', 1)")
    conn.commit()
    conn.close()


def test_sync_once_reads_new_messages(tmp_path):
    db_dir = tmp_path / "wechat_db"
    db_dir.mkdir()
    db_path = db_dir / "msg_0.db"
    _make_wechat_db(db_path)

    state_file = tmp_path / "wechat_state.json"
    watcher = WeChatWatcher(
        db_dir=db_dir,
        data_dir=tmp_path,
        state_file=state_file,
    )
    docs = watcher.sync_once()
    assert len(docs) == 1
    assert docs[0].doc_type == "wechat"


def test_sync_once_is_incremental(tmp_path):
    db_dir = tmp_path / "wechat_db"
    db_dir.mkdir()
    db_path = db_dir / "msg_0.db"
    _make_wechat_db(db_path)

    state_file = tmp_path / "wechat_state.json"
    watcher = WeChatWatcher(db_dir=db_dir, data_dir=tmp_path, state_file=state_file)
    watcher.sync_once()

    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO Chat_张三 VALUES (2, 1743300060, 0, '回复', 1)")
    conn.commit()
    conn.close()

    docs2 = watcher.sync_once()
    assert len(docs2) == 1
    assert "回复" in docs2[0].content


def test_sync_once_returns_empty_when_no_new_messages(tmp_path):
    db_dir = tmp_path / "wechat_db"
    db_dir.mkdir()
    db_path = db_dir / "msg_0.db"
    _make_wechat_db(db_path)

    state_file = tmp_path / "wechat_state.json"
    watcher = WeChatWatcher(db_dir=db_dir, data_dir=tmp_path, state_file=state_file)
    watcher.sync_once()
    docs2 = watcher.sync_once()
    assert docs2 == []


def test_watcher_disabled_when_module_off(tmp_path):
    db_dir = tmp_path / "wechat_db"
    db_dir.mkdir()

    with patch("huaqi_src.layers.data.collectors.wechat_watcher.get_config_manager") as mock_cm:
        mock_cm.return_value.is_enabled.return_value = False
        watcher = WeChatWatcher(db_dir=db_dir, data_dir=tmp_path)
        assert not watcher.is_enabled()
