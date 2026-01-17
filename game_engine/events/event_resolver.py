import threading
import time
from typing import Any, Callable, Optional, List

from game_engine.events.event import Event, ResolveFlags
from game_engine.events.event_queue import EventQueue
from uuid import UUID


class EventResolver:
    """Timer-based event resolver that fires events at their scheduled times."""

    def __init__(
        self, resolve: Optional[Callable[[Any, Event, ResolveFlags], None]] = None
    ):
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

    def cancel_event(self, event_id: UUID) -> bool:
        """Cancel a scheduled event."""
        with self._lock:
            return self.queue.cancel_event(event_id)

    def get_object_events(self, creator: UUID, event_type: str = "") -> List[Event]:
        with self._lock:
            return self.queue.get_object_events(creator, event_type)

    def cancel_object_events(self, creator: UUID, type: str = "") -> None:
        with self._lock:
            self.queue.cancel_object_events(creator, type)

    def resolve_object_events(
        self,
        creator: UUID,
        type: str = "",
        flags: ResolveFlags = ResolveFlags(),
    ) -> None:
        events = self.get_object_events(creator, type)
        for event in events:
            self._resolve_event(event, flags)

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

    def _resolve_event(self, event: Event, flags: ResolveFlags) -> None:
        assert self._resolve is not None, "resolve handle missing"
        try:
            self._resolve(event.target, event, flags)
        except Exception as e:
            # Log but don't crash the resolver
            print(f"Event resolve error: {e}")

    def _process_due_events(self) -> None:
        """Internal: fire all events whose time has come."""
        while True:
            event = None

            if not self._running:
                return
            current_time = time.time()

            with self._lock:
                next_time = self.queue.get_next_trigger_time()
                if next_time is None or next_time > current_time:
                    break
                event = self.queue.pop_next()

            if event and self._resolve:
                self._resolve_event(event, ResolveFlags())
        self._schedule_next_wakeup()
