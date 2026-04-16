from enum import Enum
from typing import List, Optional, Any
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    JOURNAL = "journal"
    AI_CHAT = "ai_chat"
    WECHAT = "wechat"
    READING = "reading"
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"
    CALENDAR = "calendar"
    ABSENCE = "absence"
    WORK_DOC = "work_doc"


class JournalMetadata(BaseModel):
    mood: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class WechatMetadata(BaseModel):
    participants: List[str] = Field(default_factory=list)
    chat_name: Optional[str] = None


class ReadingMetadata(BaseModel):
    book_title: Optional[str] = None
    author: Optional[str] = None
    highlight: bool = False


class AudioMetadata(BaseModel):
    duration_seconds: int
    speaker_count: int = 1

    @field_validator("duration_seconds")
    @classmethod
    def duration_must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("duration_seconds must be non-negative")
        return v


class AbsenceMetadata(BaseModel):
    days: int
    last_signal_id: str

    @field_validator("days")
    @classmethod
    def days_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("days must be positive")
        return v


class RawSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    source_type: SourceType
    timestamp: datetime
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: str
    metadata: Optional[Any] = None
    raw_file_ref: Optional[str] = None
    processed: bool = False
    distilled: bool = False
    vectorized: bool = False
    embedding: Optional[List[float]] = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("content must not be empty or whitespace")
        return v

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("user_id must not be empty")
        return v


class RawSignalFilter(BaseModel):
    user_id: str
    source_type: Optional[SourceType] = None
    processed: Optional[int] = None
    distilled: Optional[int] = None
    vectorized: Optional[int] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    limit: int = 100
    offset: int = 0

    @field_validator("limit")
    @classmethod
    def limit_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("limit must be positive")
        return v

    @field_validator("offset")
    @classmethod
    def offset_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("offset must be non-negative")
        return v
