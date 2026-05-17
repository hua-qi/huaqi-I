# Dependency Architecture Migration Implementation Plan

**Goal:** Implement the event-driven dependency architecture between Layers, Agent, and Scheduler to enable proactive agent behaviors like mood-based responses while maintaining strict unidirectional dependencies.

**Architecture:** A unidirectional dependency flow where Agent and Scheduler depend on Layers. Layers do not depend on Agent or Scheduler, but instead emit events to an EventBus when critical state changes occur (e.g., mood threshold met). Agent/Scheduler subscribe to these events to trigger workflows. Core events are persisted for reliability.

**Tech Stack:** Python, EventBus pattern, SQLite (for event persistence), Pytest (for TDD).

---

### Task 1: Create the EventBus interface and basic implementation

**Files:**
- Create: `layers/domain/events/bus.py`
- Test: `tests/layers/domain/events/test_bus.py`

**Step 1: Write the failing test**

```python
# tests/layers/domain/events/test_bus.py
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/layers/domain/events/test_bus.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'layers.domain.events.bus'"

**Step 3: Write minimal implementation**

```python
# layers/domain/events/bus.py
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/layers/domain/events/test_bus.py -v`
Expected: PASS

### Task 2: Implement Event Persistence Store

**Files:**
- Create: `layers/data/events/store.py`
- Test: `tests/layers/data/events/test_store.py`

**Step 1: Write the failing test**

```python
# tests/layers/data/events/test_store.py
import os
import sqlite3
from layers.data.events.store import EventStore

def test_event_store_save_and_retrieve(tmp_path):
    db_path = tmp_path / "test_events.db"
    store = EventStore(str(db_path))
    
    event_id = store.save("user.created", {"user_id": 123})
    
    assert event_id is not None
    events = store.get_unprocessed()
    assert len(events) == 1
    assert events[0]['event_type'] == "user.created"
    assert events[0]['payload'] == '{"user_id": 123}'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/layers/data/events/test_store.py -v`
Expected: FAIL with "ModuleNotFoundError" or "EventStore not defined"

**Step 3: Write minimal implementation**

```python
# layers/data/events/store.py
import sqlite3
import json
from typing import Dict, Any, List

class EventStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    processed BOOLEAN DEFAULT 0
                )
            ''')

    def save(self, event_type: str, payload: Dict[str, Any]) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO events (event_type, payload) VALUES (?, ?)",
                (event_type, json.dumps(payload))
            )
            return cursor.lastrowid

    def get_unprocessed(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE processed = 0")
            return [dict(row) for row in cursor.fetchall()]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/layers/data/events/test_store.py -v`
Expected: PASS

### Task 3: Integrate EventBus with Domain Engine

**Files:**
- Create: `layers/domain/engine.py`
- Test: `tests/layers/domain/test_engine.py`

**Step 1: Write the failing test**

```python
# tests/layers/domain/test_engine.py
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/layers/domain/test_engine.py -v`
Expected: FAIL with "ModuleNotFoundError" or missing `AnalysisEngine`

**Step 3: Write minimal implementation**

```python
# layers/domain/engine.py
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/layers/domain/test_engine.py -v`
Expected: PASS

### Task 4: Implement Agent Hooks to Consume Events

**Files:**
- Create: `agent/hooks.py`
- Test: `tests/agent/test_hooks.py`

**Step 1: Write the failing test**

```python
# tests/agent/test_hooks.py
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_hooks.py -v`
Expected: FAIL with "ModuleNotFoundError" or missing `HooksManager`

**Step 3: Write minimal implementation**

```python
# agent/hooks.py
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_hooks.py -v`
Expected: PASS
