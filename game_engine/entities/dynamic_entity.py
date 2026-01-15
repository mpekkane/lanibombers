from dataclasses import dataclass
from enum import Enum
from typing import Tuple


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
    colour: Tuple[int, int, int] = (255, 255, 255)
    speed: float = 0.0
    state: str = 'idle'
    sprite_id: int = 1  # Used for player entities (1-4)
    health: int = 100

    def take_damage(self, amount: int):
        """Reduce health by amount. Sets state to 'dead' if health reaches 0."""
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.state = 'dead'
