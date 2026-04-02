import pytest
from pathlib import Path
from datetime import datetime, timezone
from huaqi_src.layers.data.raw_signal.converters.diary import DiaryConverter
from huaqi_src.layers.data.raw_signal.models import SourceType


@pytest.fixture
def diary_file(tmp_path):
    content = """\
---
date: 2026-01-04
mood: 平静
tags:
  - 工作
  - 反思
---

今天思考了很多关于方向感的问题。
感觉需要重新审视自己的目标。
"""
    p = tmp_path / "2026-01-04.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_diary_converter_creates_raw_signal(diary_file):
    converter = DiaryConverter(user_id="u1")
    signals = converter.convert(diary_file)
    assert len(signals) == 1
    assert signals[0].source_type == SourceType.JOURNAL
    assert "方向感" in signals[0].content


def test_diary_converter_extracts_timestamp_from_frontmatter(diary_file):
    converter = DiaryConverter(user_id="u1")
    signals = converter.convert(diary_file)
    assert signals[0].timestamp.year == 2026
    assert signals[0].timestamp.month == 1
    assert signals[0].timestamp.day == 4


def test_diary_converter_extracts_metadata(diary_file):
    converter = DiaryConverter(user_id="u1")
    signals = converter.convert(diary_file)
    meta = signals[0].metadata
    assert meta["mood"] == "平静"
    assert "工作" in meta["tags"]


def test_diary_converter_empty_file_returns_empty(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    converter = DiaryConverter(user_id="u1")
    assert converter.convert(empty) == []


def test_diary_converter_no_frontmatter_uses_ingested_time(tmp_path):
    no_fm = tmp_path / "no_frontmatter.md"
    no_fm.write_text("今天是个好日子。", encoding="utf-8")
    converter = DiaryConverter(user_id="u1")
    signals = converter.convert(no_fm)
    assert len(signals) == 1
    diff = abs((signals[0].timestamp - datetime.now(timezone.utc)).total_seconds())
    assert diff < 5
