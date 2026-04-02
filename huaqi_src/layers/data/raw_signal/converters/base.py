from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from huaqi_src.layers.data.raw_signal.models import RawSignal


class BaseConverter(ABC):

    def __init__(self, user_id: str) -> None:
        self._user_id = user_id

    @abstractmethod
    def convert(self, source: Path) -> List[RawSignal]:
        pass
