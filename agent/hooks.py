from typing import List, Dict, Any
from layers.domain.events.bus import EventBus

class HooksManager:
    def __init__(self, event_bus: EventBus, inbox: List[Dict[str, Any]]):
        self.event_bus = event_bus
        self.inbox = inbox

    def register_hooks(self):
        self.event_bus.subscribe("care.mood_critical", self._handle_mood_critical)

    def _handle_mood_critical(self, event_data: Dict[str, Any]):
        user_id = event_data.get("user_id")
        # In a real app, this would call LLM to generate a response
        care_message = {
            "target_user": user_id,
            "content": f"Generated care message for score {event_data.get('score')}"
        }
        self.inbox.append(care_message)
