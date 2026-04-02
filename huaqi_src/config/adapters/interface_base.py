from abc import ABC, abstractmethod
from typing import List, Optional


class InterfaceAdapter(ABC):

    @abstractmethod
    def send_message(self, text: str, user_id: str) -> None:
        pass

    @abstractmethod
    def send_question(self, text: str, user_id: str, options: Optional[List[str]] = None) -> None:
        pass

    @abstractmethod
    def display_progress(self, message: str) -> None:
        pass
