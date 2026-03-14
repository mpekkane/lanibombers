from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Dict, Type

from game_engine.agent_state import Action
from game_engine.entities.dynamic_entity import EntityType
from game_engine.render_state import RenderState


class MonsterAI(ABC):
    """Abstract base class for monster AI behavior."""

    @abstractmethod
    def think(self, state: RenderState) -> Optional[Action]:
        """Decide the next action based on current game state.

        Returns an Action to execute, or None to do nothing this tick.
        """
        ...


class FurrymanAI(MonsterAI):
    def think(self, state: RenderState) -> Optional[Action]:
        return None


class SlimeAI(MonsterAI):
    def think(self, state: RenderState) -> Optional[Action]:
        return None


class AlienAI(MonsterAI):
    def think(self, state: RenderState) -> Optional[Action]:
        return None


class GrenadeMonsterAI(MonsterAI):
    def think(self, state: RenderState) -> Optional[Action]:
        return None


MONSTER_AI_MAP: Dict[EntityType, Type[MonsterAI]] = {
    EntityType.FURRYMAN: FurrymanAI,
    EntityType.SLIME: SlimeAI,
    EntityType.ALIEN: AlienAI,
    EntityType.GRENADEMONSTER: GrenadeMonsterAI,
}
