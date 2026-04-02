import pytest
from pathlib import Path
from huaqi_src.layers.data.raw_signal.converters.wechat import WechatConverter
from huaqi_src.layers.data.raw_signal.models import SourceType

SAMPLE_WECHAT = """\
2026-01-04 10:30:23 张三
你好啊！

2026-01-04 10:30:45 李四
你好！我最近在思考人生方向。

2026-01-04 10:31:00 张三
哦，说来听听？
"""


@pytest.fixture
def wechat_file(tmp_path):
    p = tmp_path / "chat.txt"
    p.write_text(SAMPLE_WECHAT, encoding="utf-8")
    return p


def test_wechat_converter_each_message_is_one_signal(wechat_file):
    converter = WechatConverter(user_id="u1", participants=["张三", "李四"])
    signals = converter.convert(wechat_file)
    assert len(signals) == 3


def test_wechat_converter_source_type_is_wechat(wechat_file):
    converter = WechatConverter(user_id="u1", participants=["张三", "李四"])
    signals = converter.convert(wechat_file)
    assert all(s.source_type == SourceType.WECHAT for s in signals)


def test_wechat_converter_timestamp_from_message(wechat_file):
    converter = WechatConverter(user_id="u1", participants=["张三", "李四"])
    signals = converter.convert(wechat_file)
    assert signals[0].timestamp.hour == 10
    assert signals[0].timestamp.minute == 30


def test_wechat_converter_participants_in_metadata(wechat_file):
    converter = WechatConverter(user_id="u1", participants=["张三", "李四"], chat_name="朋友群")
    signals = converter.convert(wechat_file)
    meta = signals[0].metadata
    assert "张三" in meta["participants"] or "李四" in meta["participants"]
    assert meta["chat_name"] == "朋友群"
