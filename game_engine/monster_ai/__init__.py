from __future__ import annotations

from typing import Dict, Type

from game_engine.entities.dynamic_entity import EntityType
from game_engine.monster_ai.base import MonsterAI
from game_engine.monster_ai.furryman_ai import FurrymanAI
from game_engine.monster_ai.slime_ai import SlimeAI
from game_engine.monster_ai.alien_ai import AlienAI
from game_engine.monster_ai.grenade_monster_ai import GrenadeMonsterAI

MONSTER_AI_MAP: Dict[EntityType, Type[MonsterAI]] = {
    EntityType.FURRYMAN: FurrymanAI,
    EntityType.SLIME: SlimeAI,
    EntityType.ALIEN: AlienAI,
    EntityType.GRENADEMONSTER: GrenadeMonsterAI,
}
