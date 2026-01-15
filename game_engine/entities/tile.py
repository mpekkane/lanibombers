from dataclasses import dataclass
from enum import Enum

from cfg.tile_dictionary import EMPTY_TILE_ID, ROCK1_TILE_ID, ROCK2_TILE_ID, BRICS2_TILE_ID, BRICS3_TILE_ID
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
    tile_type: TileType = TileType.EMPTY
    solid: bool = False
    interactable: bool = False

    def take_damage(self, amount: int) -> None:
        """Take damage and update visual for bedrock tiles based on health."""
        self.health = max(0, self.health - amount)

        # Tile destroyed - become empty
        if self.health == 0:
            self.tile_type = TileType.EMPTY
            self.visual_id = EMPTY_TILE_ID
            self.solid = False
            self.interactable = False
            return

        # Update bedrock visual based on damage state
        if self.tile_type == TileType.BEDROCK:
            if self.health <= 25:
                self.visual_id = ROCK1_TILE_ID
            elif self.health <= 50:
                self.visual_id = ROCK2_TILE_ID

        # Update bricks visual based on damage state
        elif self.tile_type == TileType.BRICKS:
            if self.health <= 25:
                self.visual_id = BRICS3_TILE_ID
            elif self.health <= 50:
                self.visual_id = BRICS2_TILE_ID
