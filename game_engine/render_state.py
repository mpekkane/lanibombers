import array
from dataclasses import dataclass, field
from typing import List

from game_engine.entities import DynamicEntity, Pickup, Bomb


@dataclass
class RenderState:
    """State data exported for the renderer"""
    width: int
    height: int
    tilemap: array.array
    players: List[DynamicEntity] = field(default_factory=list)
    monsters: List[DynamicEntity] = field(default_factory=list)
    pickups: List[Pickup] = field(default_factory=list)
    bombs: List[Bomb] = field(default_factory=list)
    explosions: array.array = field(default_factory=lambda: array.array('B'))  # 0=none, 1=explosion, 2=smoke1, 3=smoke2
