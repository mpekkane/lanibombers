from dataclasses import dataclass, field
from uuid import UUID
from typing import Optional
from game_engine.clock import Clock
from game_engine.entities.game_object import GameObject
from game_engine.entities.explosion import ExplosionType
from cfg.bomb_dictionary import BombType, BOMB_PROPERTIES


@dataclass(kw_only=True)
class Bomb(GameObject):
    """Timed/event-driven explosive."""
    # Mandatory fields
    x: int
    y: int
    bomb_type: BombType
    placed_at: float
    owner_id: UUID

    # Optional override fields (used by grasshopper hops)
    fuse_override: Optional[float] = None
    explosion_override: Optional[ExplosionType] = None
    hop_count: int = 0  # For grasshopper bombs: tracks explosion count

    # Auto-set fields based on bomb_type
    fuse_duration: float = field(default=0.0, init=False)
    explosion_type: ExplosionType = field(default=ExplosionType.SMALL, init=False)
    state: str = field(default='active', init=False)

    def __post_init__(self):
        fuse, explosion_type = BOMB_PROPERTIES[self.bomb_type]
        # Allow overrides for special cases like grasshopper hops
        self.fuse_duration = self.fuse_override if self.fuse_override is not None else fuse
        self.explosion_type = self.explosion_override if self.explosion_override is not None else explosion_type

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
