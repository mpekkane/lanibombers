from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    UP = 'up'
    DOWN = 'down'
    LEFT = 'left'
    RIGHT = 'right'


class EntityType(Enum):
    PLAYER = 'player'
    FURRYMAN = 'furryman'
    SLIME = 'slime'
    ALIEN = 'alien'
    GRENADEMONSTER = 'grenademonster'


@dataclass
class DynamicEntity:
    x: float
    y: float
    direction: Direction
    entity_type: EntityType
    name: str = ''
    colour: tuple = (255, 255, 255)
    speed: float = 0.0
    state: str = 'idle'
    sprite_id: int = 1  # Used for player entities (1-4)
