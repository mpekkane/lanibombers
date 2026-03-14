from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, List, Optional, TYPE_CHECKING

from game_engine.agent_state import Action

if TYPE_CHECKING:
    from game_engine.entities.bomb import Bomb
    from game_engine.entities.dynamic_entity import DynamicEntity


@dataclass
class InputCommand:
    """A single input action queued for the engine thread."""
    entity: DynamicEntity
    action: Action
    timestamp: float
    bomb: Optional[Bomb] = None


class InputQueue:
    """Thread-safe queue for external input to the game engine.

    Uses collections.deque which has thread-safe append/popleft in CPython.
    """

    def __init__(self) -> None:
        self._queue: deque[InputCommand] = deque()
        self._notify: Optional[Callable[[], None]] = None

    def set_notify(self, callback: Callable[[], None]) -> None:
        """Set callback to wake the resolver thread on submit."""
        self._notify = callback

    def submit(self, command: InputCommand) -> None:
        """Enqueue a command and notify the resolver thread."""
        self._queue.append(command)
        if self._notify:
            self._notify()

    def drain(self) -> List[InputCommand]:
        """Drain all pending commands. Called from the resolver thread."""
        result: List[InputCommand] = []
        while self._queue:
            result.append(self._queue.popleft())
        return result
