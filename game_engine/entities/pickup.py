from dataclasses import dataclass, field
from enum import Enum

from game_engine.entities.game_object import GameObject


class PickupType(Enum):
    TREASURE = 'treasure'
    TOOL = 'tool'


@dataclass(kw_only=True)
class Pickup(GameObject):
    """Static, pickable item (treasure, tool)."""
    x: int
    y: int
    pickup_type: PickupType = None
    value: int = 0  # Points or effect magnitude
