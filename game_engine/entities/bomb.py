import time
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
    state: str = 'active'       # 'active' or 'defused'

    def get_fuse_percentage(self, current_time: float = None) -> float:
        """
        Get the percentage of fuse remaining (1.0 = full, 0.0 = exploded).

        Args:
            current_time: Current timestamp. If None, uses time.time()

        Returns:
            Float between 0.0 and 1.0 representing fuse remaining
        """
        if current_time is None:
            current_time = time.time()

        elapsed = current_time - self.placed_at
        remaining = max(0.0, 1.0 - (elapsed / self.fuse_duration))
        return remaining
