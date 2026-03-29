from huaqi_src.core.event import Event, redact_sensitive_info
import time

def test_redact_sensitive_info():
    raw_text = "Here is my key sk-proj-12345ABCDE and some text."
    redacted = redact_sensitive_info(raw_text)
    assert "sk-proj-12345ABCDE" not in redacted
    assert "sk-***" in redacted

def test_event_creation():
    event = Event(
        timestamp=int(time.time()),
        source="terminal/bash",
        actor="User",
        content="Testing key sk-abcde"
    )
    assert event.source == "terminal/bash"
    assert "sk-***" in event.content
