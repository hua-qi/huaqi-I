import datetime
from huaqi_src.layers.data.collectors.wechat_reader import WeChatMessage
from huaqi_src.layers.data.collectors.wechat_writer import WeChatWriter


def _make_messages(contact: str) -> list[WeChatMessage]:
    return [
        WeChatMessage(
            rowid=1,
            contact=contact,
            timestamp=datetime.datetime(2026, 3, 30, 10, 0, 0),
            content="你好，在吗？",
            is_self=True,
        ),
        WeChatMessage(
            rowid=2,
            contact=contact,
            timestamp=datetime.datetime(2026, 3, 30, 10, 1, 0),
            content="在的，有什么事？",
            is_self=False,
        ),
    ]


def test_write_creates_markdown_file(tmp_path):
    writer = WeChatWriter(data_dir=tmp_path)
    msgs = _make_messages("张三")
    docs = writer.write(msgs)
    assert len(docs) == 1
    md_file = tmp_path / "memory" / "wechat" / "2026-03" / "张三.md"
    assert md_file.exists()


def test_write_appends_to_existing_file(tmp_path):
    writer = WeChatWriter(data_dir=tmp_path)
    msgs1 = _make_messages("张三")
    writer.write(msgs1)

    msgs2 = [
        WeChatMessage(
            rowid=3,
            contact="张三",
            timestamp=datetime.datetime(2026, 3, 30, 11, 0, 0),
            content="再聊",
            is_self=True,
        )
    ]
    writer.write(msgs2)

    md_file = tmp_path / "memory" / "wechat" / "2026-03" / "张三.md"
    content = md_file.read_text(encoding="utf-8")
    assert "你好，在吗？" in content
    assert "再聊" in content


def test_write_returns_huaqi_documents(tmp_path):
    writer = WeChatWriter(data_dir=tmp_path)
    msgs = _make_messages("李四")
    docs = writer.write(msgs)
    assert docs[0].doc_type == "wechat"
    assert docs[0].source == "wechat:李四"
    assert "你好，在吗？" in docs[0].content


def test_write_groups_by_contact_and_month(tmp_path):
    writer = WeChatWriter(data_dir=tmp_path)
    msgs = [
        WeChatMessage(1, "张三", datetime.datetime(2026, 3, 1), "三月消息", True),
        WeChatMessage(2, "李四", datetime.datetime(2026, 3, 1), "李四消息", False),
    ]
    docs = writer.write(msgs)
    assert len(docs) == 2
    assert (tmp_path / "memory" / "wechat" / "2026-03" / "张三.md").exists()
    assert (tmp_path / "memory" / "wechat" / "2026-03" / "李四.md").exists()
