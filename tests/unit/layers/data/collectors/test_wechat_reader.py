import sqlite3
from pathlib import Path
from huaqi_src.layers.data.collectors.wechat_reader import WeChatDBReader


def _make_fake_wechat_db(db_path: Path, contact: str = "张三"):
    conn = sqlite3.connect(str(db_path))
    table = f"Chat_{contact}"
    conn.execute(
        f"CREATE TABLE {table} "
        "(id INTEGER PRIMARY KEY, CreateTime INTEGER, Des INTEGER, Message TEXT, Type INTEGER)"
    )
    conn.execute(
        f"INSERT INTO {table} (CreateTime, Des, Message, Type) VALUES (1743300000, 0, '你好', 1)"
    )
    conn.execute(
        f"INSERT INTO {table} (CreateTime, Des, Message, Type) VALUES (1743300060, 1, '你也好', 1)"
    )
    conn.commit()
    conn.close()


def test_read_messages_from_db(tmp_path):
    db_path = tmp_path / "msg_0.db"
    _make_fake_wechat_db(db_path, contact="张三")
    reader = WeChatDBReader(db_path)
    messages = reader.read_since(last_rowid=0)
    assert len(messages) == 2
    assert messages[0].content == "你好"
    assert messages[0].is_self is True
    assert messages[1].content == "你也好"
    assert messages[1].is_self is False


def test_read_since_rowid_only_returns_new(tmp_path):
    db_path = tmp_path / "msg_0.db"
    _make_fake_wechat_db(db_path, contact="张三")
    reader = WeChatDBReader(db_path)
    messages = reader.read_since(last_rowid=1)
    assert len(messages) == 1
    assert messages[0].content == "你也好"


def test_read_returns_empty_when_db_unreadable(tmp_path):
    db_path = tmp_path / "nonexistent.db"
    reader = WeChatDBReader(db_path)
    messages = reader.read_since(last_rowid=0)
    assert messages == []


def test_read_skips_non_text_messages(tmp_path):
    db_path = tmp_path / "msg_0.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE Chat_Alice "
        "(id INTEGER PRIMARY KEY, CreateTime INTEGER, Des INTEGER, Message TEXT, Type INTEGER)"
    )
    conn.execute("INSERT INTO Chat_Alice VALUES (1, 1743300000, 0, '[图片]', 43)")
    conn.execute("INSERT INTO Chat_Alice VALUES (2, 1743300060, 0, '文字消息', 1)")
    conn.commit()
    conn.close()

    reader = WeChatDBReader(db_path)
    messages = reader.read_since(last_rowid=0)
    assert len(messages) == 1
    assert messages[0].content == "文字消息"
