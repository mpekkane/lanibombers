from __future__ import annotations

from typing import Optional

from game_engine.agent_state import Action
from game_engine.monster_ai.monster_ai_base import MonsterAI, MonsterSense
from game_engine.render_state import RenderState
from game_engine.entities.dynamic_entity import DynamicEntity


class AlienAI(MonsterAI):

    def __init__(self) -> None:
        super().__init__()
        self.smell_radius = 10
        self.view_radius = 100
        self.hunt_time = 30
        self.bravery = 50

    def think(
        self, state: RenderState, state_updated: bool, own_entity: DynamicEntity
    ) -> Optional[Action]:
        smell_targets = self.smell(state, own_entity)
        see_targets = self.see(state, own_entity)
        in_danger = self.sense_bombs(state, own_entity, MonsterSense.VISION)
        if in_danger:
            print("I'm in danger")
            return self.bomb_avoidance_behavior(state, own_entity)

        targets = self.fuse_senses([smell_targets, see_targets])

        # if no players are seen - hunt player
        if len(targets) <= 0:
            return self.hunting_behavior(state, own_entity)

        target, distance = targets[0]
        self.hunt(target)
        return self.target_seeking_behavior(state, own_entity, target)
