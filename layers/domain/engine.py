from layers.domain.events.bus import EventBus

class AnalysisEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    def analyze(self, text: str, uid: str):
        # Mock sentiment analysis logic
        score = -0.8 if "depressed" in text else 0.5
        
        # If score is critically low, emit event
        if score < -0.5:
            self.event_bus.emit("care.mood_critical", {
                "user_id": uid,
                "score": score
            })
