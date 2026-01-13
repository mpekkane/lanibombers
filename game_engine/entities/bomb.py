from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from game_engine.entities.game_object import GameObject


class BombType(Enum):
    NORMAL = 'normal'
    C4 = 'c4'
    LANDMINE = 'landmine'


@dataclass
class Bomb(GameObject):
    """Timed/event-driven explosive."""
    x: int = 0
    y: int = 0
    bomb_type: BombType = BombType.NORMAL
    fuse_duration: float = 3.0  # Seconds until explosion
    blast_radius: int = 1       # Tiles affected
    placed_at: float = 0.0      # Timestamp when placed
    owner_id: UUID = None       # Who placed it
