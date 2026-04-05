from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def emit(self, event_type: str, event_data: Dict[str, Any] = None):
        if event_data is None:
            event_data = {}
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                handler(event_data)
