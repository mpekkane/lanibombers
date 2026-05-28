from __future__ import annotations

from typing import Optional
import random

from game_engine.agent_state import Action
from game_engine.monster_ai.base import MonsterAI
from game_engine.render_state import RenderState
from game_engine.entities.dynamic_entity import DynamicEntity


class SlimeAI(MonsterAI):
    def __init__(self) -> None:
        super().__init__()
        self.visibility_radius = 5

    def think(
        self, state: RenderState, state_updated: bool, own_entity: DynamicEntity
    ) -> Optional[Action]:
        visible = self.get_visible_players(state, own_entity)

        # random action if no players are seen
        if len(visible) <= 0:
            return self.random_behavior(0.25)

        target, distance = visible[0]
        return self.target_seeking_behavior(state, own_entity, target)

