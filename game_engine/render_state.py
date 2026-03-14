from dataclasses import dataclass, field
from enum import IntEnum
from typing import List

import numpy as np

from game_engine.entities import DynamicEntity, Pickup, Bomb, Player


class ExplosionVisual(IntEnum):
    NONE = 0
    EXPLOSION = 1
    SMOKE1 = 2
    SMOKE2 = 3
    EXTINGUISHER = 4
    NUKE = 5


class SoundType(IntEnum):
    EXPLOSION = 1
    SMALL_EXPLOSION = 2
    URETHANE = 3
    DIG = 4
    TREASURE = 5
    DIE = 6


@dataclass
class RenderState:
    """State data exported for the renderer"""
    width: int
    height: int
    tilemap: np.ndarray  # uint8, shape (height, width)
    explosions: np.ndarray  # uint8, shape (height, width), see ExplosionVisual enum
    players: List[Player] = field(default_factory=list)
    monsters: List[DynamicEntity] = field(default_factory=list)
    pickups: List[Pickup] = field(default_factory=list)
    bombs: List[Bomb] = field(default_factory=list)
    server_time: float = 0.0  # Server clock at interpolation time
    sounds: List[int] = field(default_factory=list)
