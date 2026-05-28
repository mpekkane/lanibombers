from __future__ import annotations

from typing import Optional

from game_engine.agent_state import Action
from game_engine.monster_ai.base import MonsterAI
from game_engine.render_state import RenderState
from game_engine.entities.dynamic_entity import DynamicEntity


class GrenadeMonsterAI(MonsterAI):
    def __init__(self) -> None:
        super().__init__()
        self.visibility_radius = 5

    def think(
        self, state: RenderState, state_updated: bool, own_entity: DynamicEntity
    ) -> Optional[Action]:
        return None
