from __future__ import annotations

import json
import threading
import time
from collections import deque
from queue import Queue
from typing import Deque, Dict, List


class EventBus:
    def __init__(self, history_size: int = 200):
        self._subscribers: List[Queue] = []
        self._lock = threading.Lock()
        self._history: Deque[Dict] = deque(maxlen=history_size)

    def emit(self, level: str, message: str, extra: Dict | None = None) -> None:
        event = {
            "ts": time.time(),
            "level": level,
            "message": message,
            "extra": extra or {},
        }
        with self._lock:
            self._history.append(event)
            for q in list(self._subscribers):
                try:
                    q.put_nowait(event)
                except Exception:
                    pass

    def subscribe(self) -> Queue:
        q: Queue = Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def get_history(self) -> List[Dict]:
        with self._lock:
            return list(self._history)


bus = EventBus()


