from __future__ import annotations

from typing import Optional

from game_engine.agent_state import Action
from game_engine.monster_ai.monster_ai_base import MonsterAI, MonsterSense
from game_engine.render_state import RenderState
from game_engine.entities.dynamic_entity import DynamicEntity


class SlimeAI(MonsterAI):
    def __init__(self) -> None:
        super().__init__()
        self.smell_radius = 5
        self.view_radius = 10

    def think(
        self, state: RenderState, state_updated: bool, own_entity: DynamicEntity
    ) -> Optional[Action]:
        smell_targets = self.smell(state, own_entity)
        see_targets = self.see(state, own_entity)
        # print("-" * 40)
        # print("I'm a slime")
        # print(f"Smell: {smell_targets}")
        # print(f"See  : {see_targets}")
        targets = self.fuse_senses([smell_targets, see_targets])
        # random action if no players are seen
        if len(targets) <= 0:
            return self.random_behavior(0.25)

        target, distance = targets[0]
        return self.target_seeking_behavior(
            state, own_entity, target, MonsterSense.SMELL
        )
