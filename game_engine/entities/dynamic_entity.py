from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from game_engine.entities.game_object import GameObject


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class EntityType(Enum):
    PLAYER = "player"
    FURRYMAN = "furryman"
    SLIME = "slime"
    ALIEN = "alien"
    GRENADEMONSTER = "grenademonster"


MONSTER_DAMAGE = {
    EntityType.FURRYMAN: 10,
    EntityType.SLIME: 2,
    EntityType.ALIEN: 20,
    EntityType.GRENADEMONSTER: 10,
}


@dataclass
class DynamicEntity(GameObject):
    """Agentic entity that can move and act."""

    x: float = 0.0
    y: float = 0.0
    direction: Direction = Direction.DOWN
    entity_type: EntityType = EntityType.PLAYER
    name: str = ""
    speed: float = 0.0
    state: str = "idle"
    sprite_id: int = 1  # Used for player entities (1-4)
    money: int = 0
    fight_power: int = 0

    def take_damage(self, amount: int):
        """Reduce health by amount. Sets state to 'dead' if health reaches 0."""
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.state = "dead"

    def add_money(self, amount: int):
        """Add money to the entity."""
        self.money += amount

    @staticmethod
    def create_monster(
        monster_type: EntityType, x: float, y: float, direction: Direction
    ) -> DynamicEntity:
        """Create monster object"""
        # TODO: inject AI here
        return DynamicEntity(
            x=x,
            y=y,
            direction=direction,
            entity_type=monster_type,
            state="walk",
            fight_power=MONSTER_DAMAGE[monster_type],
        )
