from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from game_engine.agent_state import Action
from game_engine.render_state import RenderState


class MonsterAI(ABC):
    """Abstract base class for monster AI behavior."""

    @abstractmethod
    def think(self, state: RenderState, state_updated: bool) -> Optional[Action]:
        """Decide the next action based on current game state.

        Args:
            state: The latest game render state.
            state_updated: True if the state changed since the last think() call.

        Returns an Action to execute, or None to do nothing this tick.
        """
        ...
