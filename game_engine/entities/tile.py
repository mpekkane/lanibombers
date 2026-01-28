from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING, Optional

from cfg.tile_dictionary import (
    EMPTY_TILE_ID,
    ROCK1_TILE_ID,
    ROCK2_TILE_ID,
    BRICS2_TILE_ID,
    BRICS3_TILE_ID,
)
from game_engine.entities.game_object import GameObject

if TYPE_CHECKING:
    from game_engine.entities.explosion import ExplosionType
else:
    from game_engine.entities.explosion import ExplosionType

from cfg.tile_dictionary import (
    EMPTY_TILE_ID,
    ROCK1_TILE_ID,
    ROCK2_TILE_ID,
    CONCRETE_TILE_ID,
    URETHANE_TILE_ID,
    C4_TILE_ID,
    DIRT_TILE_ID,
    BIOSLIME_TILE_ID,
    BRICKS_TILE_ID,
    SWITCH_TILE_ID,
    SECURITY_DOOR_ID,
    TUNNEL_TILE_ID,
    BOULDER_TILE_ID,
    BEDROCK_TILES,
    BEDROCK_CORNER_TILES,
    DIRT_TILES,
    CONCRETE_TILES,
    URETHANE_TILES,
    BIOSLIME_TILES,
    BOULDER_TILES,
    BRICKS_TILES,
    SWITCH_TILES,
    SECURITY_DOOR_TILES,
    TUNNEL_TILES,
    C4_TILES,
    INDESTRUCTIBLE_TILE_TYPES,
)


class TileType(Enum):
    EMPTY = "empty"
    BEDROCK = "bedrock"
    DIRT = "dirt"
    CONCRETE = "concrete"
    URETHANE = "urethane"
    BIOSLIME = "bioslime"
    C4 = "c4"
    BOULDER = "boulder"
    BRICKS = "bricks"
    SWITCH = "switch"
    SECURITY_DOOR = "security_door"
    TUNNEL = "tunnel"


@dataclass
class Tile(GameObject):
    """Static tile in the game world. Position is implicit from array index."""

    tile_type: TileType = TileType.EMPTY
    solid: bool = False
    interactable: bool = False
    diggable: bool = False

    @staticmethod
    def create(tile_type: TileType, tile_id: Optional[int] = None) -> Tile:
        if tile_type == TileType.EMPTY:
            return Tile.create_empty()
        elif tile_type == TileType.BEDROCK:
            if tile_id is not None:
                return Tile.create_bedrock(tile_id)
            else:
                return Tile.create_bedrock()
        elif tile_type == TileType.DIRT:
            if tile_id is not None:
                return Tile.create_dirt(tile_id)
            else:
                return Tile.create_dirt()
        elif tile_type == TileType.CONCRETE:
            return Tile.create_concrete()
        elif tile_type == TileType.URETHANE:
            return Tile.create_urethane()
        elif tile_type == TileType.BIOSLIME:
            return Tile.create_bioslime()
        elif tile_type == TileType.C4:
            return Tile.create_c4()
        elif tile_type == TileType.BOULDER:
            if tile_id is not None:
                return Tile.create_boulder(tile_id)
            else:
                return Tile.create_boulder()
        elif tile_type == TileType.BRICKS:
            return Tile.create_bricks()
        elif tile_type == TileType.SWITCH:
            return Tile.create_switch()
        elif tile_type == TileType.SECURITY_DOOR:
            return Tile.create_sercurity_door()
        elif tile_type == TileType.TUNNEL:
            return Tile.create_tunnel()
        else:
            raise ValueError("Invalid tile type")

    @staticmethod
    def create_by_id(tile_id: int) -> Tile:
        if tile_id == ROCK1_TILE_ID:
            return Tile.create_bedrock(tile_id, health=25)
        elif tile_id == ROCK2_TILE_ID:
            return Tile.create_bedrock(tile_id, health=50)
        elif tile_id in BEDROCK_TILES:
            return Tile.create_bedrock(tile_id)
        elif tile_id in BEDROCK_CORNER_TILES:
            return Tile.create_bedrock(tile_id, health=60)
        elif tile_id in DIRT_TILES:
            return Tile.create_dirt(tile_id)
        elif tile_id in CONCRETE_TILES:
            return Tile.create_concrete()
        elif tile_id in URETHANE_TILES:
            return Tile.create_urethane()
        elif tile_id in BIOSLIME_TILES:
            return Tile.create_bioslime()
        elif tile_id in BOULDER_TILES:
            return Tile.create_boulder(tile_id)
        elif tile_id in BRICKS_TILES:
            return Tile.create_bricks()
        elif tile_id in SWITCH_TILES:
            return Tile.create_switch()
        elif tile_id in SECURITY_DOOR_TILES:
            return Tile.create_sercurity_door()
        elif tile_id in TUNNEL_TILES:
            return Tile.create_tunnel()
        elif tile_id in C4_TILES:
            return Tile.create_c4()
        else:
            return Tile.create_empty()

    # constructors
    @staticmethod
    def create_empty() -> Tile:
        return Tile(
            tile_type=TileType.EMPTY,
            solid=False,
            interactable=False,
            diggable=False,
            visual_id=EMPTY_TILE_ID,
        )

    @staticmethod
    def create_bedrock(tile_id: int = ROCK1_TILE_ID, health: int = 100) -> Tile:
        return Tile(
            tile_type=TileType.BEDROCK,
            solid=True,
            interactable=False,
            diggable=True,
            visual_id=tile_id,
            health=health,
        )

    @staticmethod
    def create_dirt(tile_id: int = DIRT_TILE_ID) -> Tile:
        return Tile(
            tile_type=TileType.DIRT,
            solid=True,
            interactable=False,
            diggable=True,
            visual_id=tile_id,
        )

    @staticmethod
    def create_concrete() -> Tile:
        return Tile(
            tile_type=TileType.CONCRETE,
            solid=True,
            interactable=False,
            diggable=False,
            visual_id=CONCRETE_TILE_ID,
        )

    @staticmethod
    def create_urethane() -> Tile:
        return Tile(
            tile_type=TileType.URETHANE,
            solid=True,
            interactable=False,
            diggable=True,
            visual_id=URETHANE_TILE_ID,
            health=200
        )

    @staticmethod
    def create_bioslime() -> Tile:
        return Tile(
            tile_type=TileType.BIOSLIME,
            solid=True,
            interactable=False,
            diggable=True,
            visual_id=BIOSLIME_TILE_ID,
        )

    @staticmethod
    def create_c4() -> Tile:
        return Tile(
            tile_type=TileType.C4,
            solid=True,
            interactable=False,
            diggable=True,
            visual_id=C4_TILE_ID,
        )

    @staticmethod
    def create_boulder(tile_id: int = BOULDER_TILE_ID) -> Tile:
        return Tile(
            tile_type=TileType.BOULDER,
            solid=True,
            interactable=True,
            diggable=False,
            visual_id=tile_id,
        )

    @staticmethod
    def create_bricks() -> Tile:
        return Tile(
            tile_type=TileType.BRICKS,
            solid=True,
            interactable=False,
            diggable=True,
            visual_id=BRICKS_TILE_ID,
        )

    @staticmethod
    def create_switch() -> Tile:
        return Tile(
            tile_type=TileType.SWITCH,
            solid=True,
            interactable=True,
            diggable=False,
            visual_id=SWITCH_TILE_ID,
        )

    @staticmethod
    def create_sercurity_door() -> Tile:
        return Tile(
            tile_type=TileType.SECURITY_DOOR,
            solid=True,
            interactable=False,
            diggable=False,
            visual_id=SECURITY_DOOR_ID,
        )

    @staticmethod
    def create_tunnel() -> Tile:
        return Tile(
            tile_type=TileType.TUNNEL,
            solid=False,
            interactable=True,
            diggable=False,
            visual_id=TUNNEL_TILE_ID,
        )

    def to_byte(self) -> int:
        return self.visual_id

    # damage
    def take_damage(
        self, amount: int, damage_type: Optional["ExplosionType"] = None
    ) -> None:
        """Take damage and update visual for bedrock tiles based on health."""
        # Some tiles are indestructible
        if self.tile_type.value in INDESTRUCTIBLE_TILE_TYPES:
            return

        damage = int(amount)

        # Dirt takes double damage from small, medium, and large explosions
        if self.tile_type == TileType.DIRT and damage_type in (
            ExplosionType.SMALL,
            ExplosionType.MEDIUM,
            ExplosionType.LARGE,
        ):
            damage *= 2

        self.health = max(0, self.health - damage)

        # Tile destroyed - become empty
        if self.health <= 0:
            self.tile_type = TileType.EMPTY
            self.visual_id = EMPTY_TILE_ID
            self.solid = False
            self.interactable = False
            self.diggable = False
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

    # helpers for types
    def is_switch(self) -> bool:
        return self.tile_type == TileType.SWITCH

    def is_security_door(self) -> bool:
        return self.tile_type == TileType.SECURITY_DOOR

    def is_teleport(self) -> bool:
        return self.tile_type == TileType.TUNNEL

    def is_boulder(self) -> bool:
        return self.tile_type == TileType.BOULDER
