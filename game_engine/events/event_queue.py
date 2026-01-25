import heapq
from typing import Optional, List
from uuid import UUID

from game_engine.clock import Clock
from game_engine.events.event import Event


class EventQueue:
    """Priority queue for scheduled events, ordered by trigger time."""

    def __init__(self):
        self._events: list[Event] = []
        self._event_map: dict[UUID, Event] = {}  # For O(1) lookup by ID

    def add_event(self, event: Event) -> None:
        """Add an event to the queue."""
        heapq.heappush(self._events, event)
        self._event_map[event.id] = event

    def peek_next(self) -> Optional[Event]:
        """Return the next event without removing it."""
        self._cleanup_cancelled()
        if self._events:
            return self._events[0]
        return None

    def pop_next(self) -> Optional[Event]:
        """Remove and return the next event."""
        self._cleanup_cancelled()
        if self._events:
            event = heapq.heappop(self._events)
            del self._event_map[event.id]
            return event
        return None

    def cancel_event(self, event_id: UUID) -> bool:
        """Cancel an event by ID. Returns True if found and cancelled."""
        if event_id in self._event_map:
            del self._event_map[event_id]
            return True
        return False

    def get_object_events(self, creator: UUID, event_type: str = "") -> List[Event]:
        found: List[Event] = []
        for event in self._events:
            if event.created_by == creator:
                if not event_type or event_type == event.event_type:
                    found.append(event)
        return found

    def get_events_by_target(self, target, event_type: str = "") -> List[Event]:
        """Find events by their target object."""
        found: List[Event] = []
        for event in self._events:
            if event.id not in self._event_map:
                continue  # Skip cancelled events
            if event.target is target:
                if not event_type or event_type == event.event_type:
                    found.append(event)
        return found

    def reschedule_events_by_target(self, target, event_type: str, relative_time: float) -> int:
        """
        Reschedule all events for a target to trigger at current_time + relative_time.
        If no existing event is found, schedules a new one.

        Args:
            target: The target object to find events for
            event_type: The event type to match (e.g., "explode")
            relative_time: Time from now when the event should trigger

        Returns:
            Number of events rescheduled or created
        """
        events = self.get_events_by_target(target, event_type)
        new_trigger_time = Clock.now() + relative_time

        if events:
            # Reschedule existing events
            for event in events:
                # Cancel old event
                self.cancel_event(event.id)
                # Create new event with updated trigger time
                new_event = Event(
                    trigger_at=new_trigger_time,
                    target=event.target,
                    event_type=event.event_type,
                    created_at=event.created_at,
                    created_by=event.created_by,
                )
                self.add_event(new_event)
            return len(events)
        else:
            # No existing event, schedule a new one
            new_event = Event(
                trigger_at=new_trigger_time,
                target=target,
                event_type=event_type,
            )
            self.add_event(new_event)
            return 1

    def cancel_object_events(self, creator: UUID, event_type: str = "") -> None:
        for event in self._events:
            if event.created_by == creator:
                if not event_type or event_type == event.event_type:
                    self.cancel_event(event.id)
        self._cleanup_cancelled()

    def get_next_trigger_time(self) -> Optional[float]:
        """Return the trigger time of the next event, or None if queue is empty."""
        self._cleanup_cancelled()
        if self._events:
            return self._events[0].trigger_at
        return None

    def _cleanup_cancelled(self) -> None:
        """Remove cancelled events from the front of the heap."""
        while self._events and self._events[0].id not in self._event_map:
            heapq.heappop(self._events)

    def __len__(self) -> int:
        return len(self._event_map)

    def __bool__(self) -> bool:
        return bool(self._event_map)
