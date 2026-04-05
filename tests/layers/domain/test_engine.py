from layers.domain.engine import AnalysisEngine
from layers.domain.events.bus import EventBus

def test_analysis_emits_mood_critical_event():
    bus = EventBus()
    engine = AnalysisEngine(event_bus=bus)
    
    received_events = []
    bus.subscribe("care.mood_critical", lambda data: received_events.append(data))
    
    # Analyze text that should trigger critical mood
    engine.analyze("I am feeling very depressed and sad today.", uid="user_1")
    
    assert len(received_events) == 1
    assert received_events[0]["user_id"] == "user_1"
    assert "score" in received_events[0]
