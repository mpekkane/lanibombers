import threading

from typing import Any, Callable, Optional, List
from game_engine.clock import Clock
from game_engine.events.event import Event, ResolveFlags
from game_engine.events.event_queue import EventQueue
from uuid import UUID


class EventResolver:
    """Condition-based event resolver that processes events on a persistent thread."""

    def __init__(
        self, resolve: Optional[Callable[[Any, Event, ResolveFlags], None]] = None
    ):
        """
        Args:
            resolve: Callback invoked when an event fires.
                     Receives (target, event, flags) where target is event.target.
        """
        self.queue = EventQueue()
        self._cond = threading.Condition()
        self._running = False
        self._resolve = resolve
        self._thread: Optional[threading.Thread] = None
        self.pre_process: Optional[Callable[[], None]] = None

    def start(self) -> None:
        """Start the event resolver thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the event resolver thread."""
        with self._cond:
            self._running = False
            self._cond.notify()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def notify(self) -> None:
        """Wake the resolver thread (new input available)."""
        with self._cond:
            self._cond.notify()

    def schedule_event(self, event: Event) -> None:
        """Add an event and wake the resolver thread if needed."""
        with self._cond:
            self.queue.add_event(event)
            if self._running:
                self._cond.notify()

    def cancel_event(self, event_id: UUID) -> bool:
        """Cancel a scheduled event."""
        with self._cond:
            return self.queue.cancel_event(event_id)

    def get_object_events(self, creator: UUID, event_type: str = "") -> List[Event]:
        with self._cond:
            return self.queue.get_object_events(creator, event_type)

    def get_events_by_target(self, target, event_type: str = "") -> List[Event]:
        """Find events by their target object."""
        with self._cond:
            return self.queue.get_events_by_target(target, event_type)

    def reschedule_events_by_target(self, target, event_type: str, relative_time: float, base_time: float = 0.0) -> int:
        """
        Reschedule all events for a target to trigger at base_time + relative_time.

        Returns:
            Number of events rescheduled
        """
        with self._cond:
            count = self.queue.reschedule_events_by_target(target, event_type, relative_time, base_time)
            if self._running:
                self._cond.notify()
            return count

    def cancel_object_events(self, creator: UUID, type: str = "") -> None:
        with self._cond:
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
            # Remove from queue so the timer can't resolve it again
            self.cancel_event(event.id)

    def _resolve_event(self, event: Event, flags: ResolveFlags) -> None:
        assert self._resolve is not None, "resolve handle missing"
        try:
            self._resolve(event.target, event, flags)
        except Exception as e:
            # Log but don't crash the resolver
            print(f"Event resolve error: {e}")

    def _run(self) -> None:
        """Persistent thread: drain inputs, process due events, sleep until next."""
        while self._running:
            # 1. Drain input queue via pre_process callback
            if self.pre_process:
                self.pre_process()

            # 2. Process all due game events
            self._process_due_events()

            # 3. Wait until next event or external notification
            with self._cond:
                if not self._running:
                    break
                next_time = self.queue.get_next_trigger_time()
                if next_time is not None:
                    delay = max(0, next_time - Clock.now())
                    self._cond.wait(timeout=delay)
                else:
                    self._cond.wait()  # sleep until notified

    def _process_due_events(self) -> None:
        """Fire all events whose time has come."""
        while True:
            if not self._running:
                return

            current_time = Clock.now()

            with self._cond:
                next_time = self.queue.get_next_trigger_time()
                if next_time is None or next_time > current_time:
                    break
                event = self.queue.pop_next()

            if event and self._resolve:
                self._resolve_event(event, ResolveFlags())
