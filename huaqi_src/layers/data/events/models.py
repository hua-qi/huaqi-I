from dataclasses import dataclass
import re


def redact_sensitive_info(text: str) -> str:
    return re.sub(r'sk-[a-zA-Z0-9\-]+', 'sk-***', text)


@dataclass
class Event:
    timestamp: int
    source: str
    actor: str
    content: str
    context_id: str = ""

    def __post_init__(self):
        self.content = redact_sensitive_info(self.content)
