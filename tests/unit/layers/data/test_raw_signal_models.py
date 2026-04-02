import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from huaqi_src.layers.data.raw_signal.models import (
    RawSignal,
    RawSignalFilter,
    SourceType,
    JournalMetadata,
    WechatMetadata,
    ReadingMetadata,
    AudioMetadata,
    AbsenceMetadata,
)


class TestRawSignalCreation:
    def test_minimal_valid_signal(self):
        signal = RawSignal(
            user_id="user1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, 4, 10, 0, 0, tzinfo=timezone.utc),
            content="今天状态不错，思路清晰。",
        )
        assert signal.user_id == "user1"
        assert signal.source_type == SourceType.JOURNAL
        assert signal.content == "今天状态不错，思路清晰。"

    def test_id_auto_generated_when_not_provided(self):
        signal = RawSignal(
            user_id="user1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
            content="测试内容",
        )
        assert signal.id is not None
        assert len(signal.id) == 36

    def test_id_preserved_when_provided(self):
        signal = RawSignal(
            id="my-custom-id-123",
            user_id="user1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
            content="测试内容",
        )
        assert signal.id == "my-custom-id-123"

    def test_processed_defaults_to_false(self):
        signal = RawSignal(
            user_id="user1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
            content="测试",
        )
        assert signal.processed is False

    def test_distilled_defaults_to_false(self):
        signal = RawSignal(
            user_id="user1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
            content="测试",
        )
        assert signal.distilled is False

    def test_vectorized_defaults_to_false(self):
        signal = RawSignal(
            user_id="user1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
            content="测试",
        )
        assert signal.vectorized is False

    def test_ingested_at_auto_set(self):
        before = datetime.now(timezone.utc)
        signal = RawSignal(
            user_id="user1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
            content="测试",
        )
        after = datetime.now(timezone.utc)
        assert before <= signal.ingested_at <= after


class TestRawSignalValidation:
    def test_empty_content_raises(self):
        with pytest.raises(ValidationError):
            RawSignal(
                user_id="user1",
                source_type=SourceType.JOURNAL,
                timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
                content="",
            )

    def test_whitespace_only_content_raises(self):
        with pytest.raises(ValidationError):
            RawSignal(
                user_id="user1",
                source_type=SourceType.JOURNAL,
                timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
                content="   ",
            )

    def test_empty_user_id_raises(self):
        with pytest.raises(ValidationError):
            RawSignal(
                user_id="",
                source_type=SourceType.JOURNAL,
                timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
                content="测试",
            )

    def test_invalid_source_type_raises(self):
        with pytest.raises(ValidationError):
            RawSignal(
                user_id="user1",
                source_type="invalid_type",
                timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
                content="测试",
            )


class TestSourceType:
    def test_all_standard_source_types_exist(self):
        assert SourceType.JOURNAL
        assert SourceType.AI_CHAT
        assert SourceType.WECHAT
        assert SourceType.READING
        assert SourceType.AUDIO
        assert SourceType.VIDEO
        assert SourceType.IMAGE
        assert SourceType.CALENDAR
        assert SourceType.ABSENCE


class TestMetadataModels:
    def test_journal_metadata_valid(self):
        meta = JournalMetadata(mood="平静", tags=["工作", "反思"])
        assert meta.mood == "平静"
        assert meta.tags == ["工作", "反思"]

    def test_journal_metadata_optional_fields(self):
        meta = JournalMetadata()
        assert meta.mood is None
        assert meta.tags == []

    def test_wechat_metadata_valid(self):
        meta = WechatMetadata(participants=["张三", "李四"], chat_name="家庭群")
        assert meta.participants == ["张三", "李四"]
        assert meta.chat_name == "家庭群"

    def test_reading_metadata_valid(self):
        meta = ReadingMetadata(book_title="穷查理宝典", author="查理·芒格", highlight=True)
        assert meta.book_title == "穷查理宝典"
        assert meta.highlight is True

    def test_audio_metadata_valid(self):
        meta = AudioMetadata(duration_seconds=183, speaker_count=1)
        assert meta.duration_seconds == 183

    def test_absence_metadata_valid(self):
        meta = AbsenceMetadata(days=30, last_signal_id="uuid-xxx")
        assert meta.days == 30
        assert meta.last_signal_id == "uuid-xxx"

    def test_audio_duration_must_be_positive(self):
        with pytest.raises(ValidationError):
            AudioMetadata(duration_seconds=-1)

    def test_absence_days_must_be_positive(self):
        with pytest.raises(ValidationError):
            AbsenceMetadata(days=0, last_signal_id="uuid-xxx")


class TestRawSignalFilter:
    def test_minimal_filter(self):
        f = RawSignalFilter(user_id="user1")
        assert f.user_id == "user1"
        assert f.source_type is None
        assert f.processed is None
        assert f.distilled is None
        assert f.limit == 100
        assert f.offset == 0

    def test_filter_with_all_fields(self):
        f = RawSignalFilter(
            user_id="user1",
            source_type=SourceType.JOURNAL,
            processed=0,
            distilled=0,
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            until=datetime(2026, 1, 4, tzinfo=timezone.utc),
            limit=50,
            offset=10,
        )
        assert f.source_type == SourceType.JOURNAL
        assert f.processed == 0
        assert f.limit == 50

    def test_limit_must_be_positive(self):
        with pytest.raises(ValidationError):
            RawSignalFilter(user_id="user1", limit=0)

    def test_offset_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            RawSignalFilter(user_id="user1", offset=-1)


@pytest.fixture
def journal_signal() -> RawSignal:
    return RawSignal(
        user_id="test_user",
        source_type=SourceType.JOURNAL,
        timestamp=datetime(2026, 1, 4, 10, 0, 0, tzinfo=timezone.utc),
        content="今天思考了很多关于方向感的问题，感觉有些迷茫。",
        metadata={"mood": "迷茫", "tags": ["反思", "方向"]},
    )


@pytest.fixture
def wechat_signal() -> RawSignal:
    return RawSignal(
        user_id="test_user",
        source_type=SourceType.WECHAT,
        timestamp=datetime(2026, 1, 4, 11, 0, 0, tzinfo=timezone.utc),
        content="和朋友聊了关于职业规划的事情。",
        metadata={"participants": ["李四"], "chat_name": "私聊"},
    )


@pytest.fixture
def absence_signal() -> RawSignal:
    return RawSignal(
        user_id="test_user",
        source_type=SourceType.ABSENCE,
        timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
        content="用户沉默期 30 天，无任何输入信号。",
        metadata={"days": 30, "last_signal_id": "prev-uuid"},
    )


class TestStandardFixtures:
    def test_journal_signal_fixture(self, journal_signal):
        assert journal_signal.source_type == SourceType.JOURNAL
        assert "迷茫" in journal_signal.content

    def test_wechat_signal_fixture(self, wechat_signal):
        assert wechat_signal.source_type == SourceType.WECHAT

    def test_absence_signal_fixture(self, absence_signal):
        assert absence_signal.source_type == SourceType.ABSENCE
