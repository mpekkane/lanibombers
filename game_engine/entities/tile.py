from dataclasses import dataclass
from enum import Enum

from game_engine.entities.game_object import GameObject


class TileType(Enum):
    EMPTY = 'empty'
    BEDROCK = 'bedrock'
    DIRT = 'dirt'
    CONCRETE = 'concrete'
    URETHANE = 'urethane'
    BIOSLIME = 'bioslime'
    C4 = 'c4'
    BOULDER = 'boulder'
    BRICKS = 'bricks'
    SWITCH = 'switch'
    SECURITY_DOOR = 'security_door'
    TUNNEL = 'tunnel'


@dataclass
class Tile(GameObject):
    """Static tile in the game world. Position is implicit from array index."""
    tile_id: int = 0
    tile_type: TileType = TileType.EMPTY
    solid: bool = False
    interactable: bool = False
