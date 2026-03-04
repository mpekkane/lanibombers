from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4


@dataclass
class ResolveFlags:
    """This enables message passing from forced resolvation"""
    spawn: bool = True
    resolve_time: float = 0.0  # Wall-clock time for premature resolution (0 = use event.trigger_at)


@dataclass
class Event:
    """Scheduled event in the game."""
    trigger_at: float                       # When to fire (time.time())
    target: Any                             # Object with trigger() method
    id: UUID = field(default_factory=uuid4)
    created_at: float = 0.0                 # Timestamp when created
    created_by: UUID = None                 # GameObject that created it
    event_type: str = ''                    # Optional type identifier
    source: str = ''                        # Method that created this event

    def __lt__(self, other: 'Event') -> bool:
        """Comparison for heapq ordering."""
        return self.trigger_at < other.trigger_at


@dataclass
class MoveEvent(Event):
    """Movement event"""
    direction: str = ""
