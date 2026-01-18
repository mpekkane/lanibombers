from dataclasses import dataclass, field
from typing import List

import numpy as np

from game_engine.entities import DynamicEntity, Pickup, Bomb


@dataclass
class RenderState:
    """State data exported for the renderer"""
    width: int
    height: int
    tilemap: np.ndarray  # uint8, shape (height, width)
    explosions: np.ndarray  # uint8, shape (height, width), 0=none, 1=explosion, 2=smoke1, 3=smoke2
    players: List[DynamicEntity] = field(default_factory=list)
    monsters: List[DynamicEntity] = field(default_factory=list)
    pickups: List[Pickup] = field(default_factory=list)
    bombs: List[Bomb] = field(default_factory=list)
