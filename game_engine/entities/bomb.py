from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID
from typing import Optional
from game_engine.clock import Clock
from game_engine.entities.game_object import GameObject
from common.bomb_dictionary import BombType, BombState, BOMB_PROPERTIES, ExplosionType
from game_engine.entities.dynamic_entity import Direction
import struct


@dataclass(kw_only=True)
class Bomb(GameObject):
    """Timed/event-driven explosive."""
    # Mandatory fields
    x: int
    y: int
    bomb_type: BombType
    placed_at: float
    owner_id: UUID

    # Optional override fields (used by grasshopper hops, flamethrower direction)
    fuse_override: Optional[float] = None
    explosion_override: Optional[ExplosionType] = None
    hop_count: int = 0  # For grasshopper bombs: tracks explosion count
    direction: Optional[Direction] = None  # For directed explosions like flamethrower

    # Auto-set fields based on bomb_type
    fuse_duration: float = field(default=0.0, init=False)
    explosion_type: ExplosionType = field(default=ExplosionType.SMALL, init=False)
    state: BombState = field(default=BombState.ACTIVE, init=False)
    # Populated by GameEngine.get_render_state when the render state is sent
    # to clients, so the renderer can pick a fuse animation frame without
    # doing cross-clock arithmetic.
    fuse_pct: float = field(default=1.0, init=False)

    _byte_format = struct.Struct("!16s16sBBHf")
    byte_size = _byte_format.size

    def to_bytes(self) -> bytes:
        """Encode a client snapshot; fuse animation uses fuse_pct, not placed_at."""
        direction = 0 if self.direction is None else int(Direction(self.direction)) + 1
        flags = (int(BombType(self.bomb_type))
                 | int(BombState(self.state)) << 5
                 | direction << 6)
        return self._byte_format.pack(
            self.id.bytes, self.owner_id.bytes, self.x, self.y, flags, self.fuse_pct
        )

    @staticmethod
    def from_bytes(buffer: bytes) -> Bomb:
        identity, owner, x, y, flags, fuse_pct = Bomb._byte_format.unpack(buffer)
        if flags >> 9:
            raise ValueError("Reserved bomb bits must be zero")
        direction = (flags >> 6) & 7
        bomb = Bomb(
            id=UUID(bytes=identity), owner_id=UUID(bytes=owner), x=x, y=y,
            bomb_type=BombType(flags & 31), placed_at=0.0,
            direction=None if direction == 0 else Direction(direction - 1),
        )
        bomb.state = BombState((flags >> 5) & 1)
        bomb.fuse_pct = fuse_pct
        return bomb

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
