from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
import struct

from game_engine.entities.game_object import GameObject


class PickupType(IntEnum):
    NONE = 0
    TREASURE = 1
    TOOL = 2


@dataclass(kw_only=True)
class Pickup(GameObject):
    """Static, pickable item (treasure, tool)."""
    x: int
    y: int
    pickup_type: PickupType = None
    value: int = 0  # Points or effect magnitude
    _byte_format = struct.Struct("!BBBH")
    byte_size = _byte_format.size

    def to_bytes(self) -> bytes:
        pickup_type = PickupType.NONE if self.pickup_type is None else self.pickup_type
        pickup_type = PickupType(pickup_type)
        if not 0 <= self.value <= 127:
            raise ValueError("Pickup value must be (0..127)")
        return self._byte_format.pack(
            self.x, self.y, self.visual_id, (int(pickup_type) << 7) | self.value
        )

    @staticmethod
    def from_bytes(buffer: bytes) -> Pickup:
        x, y, visual_id, type_and_value = Pickup._byte_format.unpack(buffer)
        if type_and_value >> 9:
            raise ValueError("Reserved pickup bits must be zero")
        pickup_type = PickupType(type_and_value >> 7)
        value = type_and_value & 0x7f
        return Pickup(
            x=x, y=y, pickup_type=PickupType(pickup_type),
            value=value, visual_id=visual_id,
        )
