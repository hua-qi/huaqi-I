from agent.hooks import HooksManager
from layers.domain.events.bus import EventBus

def test_hooks_manager_subscribes_and_handles_mood_critical():
    bus = EventBus()
    inbox = []
    manager = HooksManager(event_bus=bus, inbox=inbox)
    
    manager.register_hooks()
    
    # Simulate the event being emitted from the domain layer
    bus.emit("care.mood_critical", {"user_id": "user_1", "score": -0.9})
    
    assert len(inbox) == 1
    assert "user_1" in inbox[0]["target_user"]
    assert "care message" in inbox[0]["content"]
