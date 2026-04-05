from layers.domain.events.bus import EventBus

def test_event_bus_pub_sub():
    bus = EventBus()
    received = []
    
    def handler(event_data):
        received.append(event_data)
        
    bus.subscribe("test.event", handler)
    bus.emit("test.event", {"key": "value"})
    
    assert len(received) == 1
    assert received[0] == {"key": "value"}
