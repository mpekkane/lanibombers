import threading
import time
from typing import Any, Callable, Optional

from game_engine.events.event import Event
from game_engine.events.event_queue import EventQueue


class EventResolver:
    """Timer-based event resolver that fires events at their scheduled times."""

    def __init__(self, resolve: Optional[Callable[[Any, Event], None]] = None):
        """
        Args:
            resolve: Callback invoked when an event fires.
                     Receives (target, event) where target is event.target.
        """
        self.queue = EventQueue()
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._running = False
        self._resolve = resolve

    def start(self) -> None:
        """Start the event resolver."""
        with self._lock:
            self._running = True
            self._schedule_next_wakeup()

    def stop(self) -> None:
        """Stop the event resolver."""
        with self._lock:
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None

    def schedule_event(self, event: Event) -> None:
        """Add an event and reschedule the timer if needed."""
        with self._lock:
            self.queue.add_event(event)
            if self._running:
                self._schedule_next_wakeup()

    def cancel_event(self, event_id) -> bool:
        """Cancel a scheduled event."""
        with self._lock:
            return self.queue.cancel_event(event_id)

    def _schedule_next_wakeup(self) -> None:
        """Internal: schedule timer for next event."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

        next_time = self.queue.get_next_trigger_time()
        if next_time is not None:
            delay = max(0, next_time - time.time())
            self._timer = threading.Timer(delay, self._process_due_events)
            self._timer.daemon = True
            self._timer.start()

    def _process_due_events(self) -> None:
        """Internal: fire all events whose time has come."""
        with self._lock:
            if not self._running:
                return

            current_time = time.time()
            while True:
                next_time = self.queue.get_next_trigger_time()
                if next_time is None or next_time > current_time:
                    break

                event = self.queue.pop_next()
                if event and self._resolve:
                    try:
                        self._resolve(event.target, event)
                    except Exception as e:
                        # Log but don't crash the resolver
                        print(f"Event resolve error: {e}")

            self._schedule_next_wakeup()
