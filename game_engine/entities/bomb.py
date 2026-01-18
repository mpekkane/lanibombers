from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID
from typing import Optional
from game_engine.clock import Clock
from game_engine.entities.game_object import GameObject
from game_engine.entities.explosion import ExplosionType


class BombType(Enum):
    BIG_BOMB = 'big_bomb'
    C4 = 'c4'
    LANDMINE = 'landmine'
    REMOTE = 'remote'

    def is_timed(self) -> bool:
        return self != BombType.LANDMINE and self != BombType.REMOTE


# Bomb properties by type: (fuse_duration, explosion_type)
BOMB_PROPERTIES = {
    BombType.BIG_BOMB: (3.0, ExplosionType.MEDIUM),
    BombType.C4: (5.0, ExplosionType.LARGE),
    BombType.LANDMINE: (0.5, ExplosionType.SMALL),
    BombType.REMOTE: (-1.0, ExplosionType.MEDIUM),
}


@dataclass(kw_only=True)
class Bomb(GameObject):
    """Timed/event-driven explosive."""
    # Mandatory fields
    x: int
    y: int
    bomb_type: BombType
    placed_at: float
    owner_id: UUID

    # Auto-set fields based on bomb_type
    fuse_duration: float = field(default=0.0, init=False)
    explosion_type: ExplosionType = field(default=ExplosionType.SMALL, init=False)
    state: str = field(default='active', init=False)

    def __post_init__(self):
        fuse, explosion_type = BOMB_PROPERTIES[self.bomb_type]
        self.fuse_duration = fuse
        self.explosion_type = explosion_type

    def get_fuse_percentage(self, current_time: Optional[float] = None) -> float:
        """
        Get the percentage of fuse remaining (1.0 = full, 0.0 = exploded).

        Args:
            current_time: Current timestamp. If None, uses Clock.now()

        Returns:
            Float between 0.0 and 1.0 representing fuse remaining
        """
        if current_time is None:
            current_time = Clock.now()

        elapsed = current_time - self.placed_at
        remaining = max(0.0, 1.0 - (elapsed / self.fuse_duration))
        return remaining
