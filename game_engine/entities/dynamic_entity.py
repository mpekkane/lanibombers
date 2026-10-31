from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
import struct
from uuid import UUID
from game_engine.entities.game_object import GameObject


class EntityState(IntEnum):
    IDLE = 0
    WALK = 1
    DIG = 2
    DEAD = 3


class Direction(IntEnum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3


class EntityType(IntEnum):
    PLAYER = 0
    FURRYMAN = 1
    SLIME = 2
    ALIEN = 3
    GRENADEMONSTER = 4
    GRENADE = 5

    def is_monster(self) -> bool:
        return (
            self == EntityType.FURRYMAN
            or self == EntityType.SLIME
            or self == EntityType.GRENADEMONSTER
            or self == EntityType.ALIEN
        )

    def is_player(self) -> bool:
        return self == EntityType.PLAYER


MONSTER_DAMAGE = {
    EntityType.FURRYMAN: 10,
    EntityType.SLIME: 2,
    EntityType.ALIEN: 20,
    EntityType.GRENADEMONSTER: 10,
}

MONSTER_SPEEDS = {
    EntityType.FURRYMAN: 2.0,
    EntityType.SLIME: 1.0,
    EntityType.ALIEN: 3.0,
    EntityType.GRENADEMONSTER: 2.5,
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
    state: EntityState = EntityState.IDLE
    sprite_id: int = 1  # Used for player entities (1-4)
    money: int = 0
    fight_power: int = 0

    _byte_format = struct.Struct("!16sfff3s")
    byte_size = _byte_format.size

    def to_bytes(self) -> bytes:
        """Encode the entity fields used by client rendering and extrapolation."""
        if not 0 <= self.health < 1 << 10:
            raise ValueError("Entity health must fit in 10 bits")
        flags = (self.health
                 | int(EntityType(self.entity_type)) << 10
                 | int(Direction(self.direction)) << 13
                 | int(EntityState(self.state)) << 15)
        return DynamicEntity._byte_format.pack(
            self.id.bytes, self.x, self.y, self.speed, flags.to_bytes(3, "big")
        )

    @staticmethod
    def from_bytes(buffer: bytes) -> DynamicEntity:
        identity, x, y, speed, packed = DynamicEntity._byte_format.unpack(buffer)
        flags = int.from_bytes(packed, "big")
        if flags >> 17:
            raise ValueError("Reserved entity bits must be zero")
        return DynamicEntity(
            id=UUID(bytes=identity), x=x, y=y, speed=speed,
            health=flags & 1023,
            entity_type=EntityType((flags >> 10) & 7),
            direction=Direction((flags >> 13) & 3),
            state=EntityState((flags >> 15) & 3),
        )

    def take_damage(self, amount: int) -> bool:
        """Reduce health by amount. Sets state to 'dead' if health reaches 0."""
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.state = EntityState.DEAD
            return True
        return False

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
            state=EntityState.WALK,
            speed=MONSTER_SPEEDS[monster_type],
            fight_power=MONSTER_DAMAGE[monster_type],
        )

    def push_power(self) -> float:
        return 0.25

    @staticmethod
    def create_grenade(
        x: float, y: float, direction: Direction, owner_id, speed: float
    ) -> DynamicEntity:
        """Create a grenade projectile entity."""
        entity = DynamicEntity(
            x=x,
            y=y,
            direction=direction,
            entity_type=EntityType.GRENADE,
            state=EntityState.WALK,
            speed=speed,
        )
        entity.owner_id = owner_id
        return entity
