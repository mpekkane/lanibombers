"""
Map loader for loading game maps from .MNE files.
"""

import array
from dataclasses import dataclass, field
from typing import List

from cfg.tile_dictionary import (
    EMPTY_TILE_ID,
    ROCK1_TILE_ID,
    ROCK2_TILE_ID,
    MONSTER_SPAWN_TILES,
    TREASURE_TILES,
    TOOL_TILES,
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
)
from game_engine.entities import (
    DynamicEntity,
    Direction,
    EntityType,
    Tile,
    TileType,
    Treasure,
    TreasureType,
    Tool,
    ToolType,
)


@dataclass
class MapData:
    """Loaded map data containing tiles and entities."""

    width: int
    height: int
    tiles: List[List[Tile]]
    tilemap: array.array  # Raw byte array for renderer
    monsters: List[DynamicEntity] = field(default_factory=list)
    treasures: List[Treasure] = field(default_factory=list)
    tools: List[Tool] = field(default_factory=list)


def load_map(path: str, width: int = 64, height: int = 45) -> MapData:
    """
    Load a map file and return MapData with tiles and monsters.

    Args:
        path: Path to the .MNE map file
        width: Map width in tiles (default 64)
        height: Map height in tiles (default 45)

    Returns:
        MapData containing tile grid and monster list
    """
    # Read raw bytes from file
    tilemap = array.array("B")
    with open(path, "rb") as f:
        for line in f:
            line = line.rstrip(b"\r\n")
            for char in line:
                tilemap.append(char)

    # Create tile grid and entity lists
    tiles = []
    monsters = []
    treasures = []
    tools = []

    for y in range(height):
        row = []
        for x in range(width):
            i = y * width + x
            tile_id = tilemap[i] if i < len(tilemap) else EMPTY_TILE_ID

            # Check for monster spawn tile
            if tile_id in MONSTER_SPAWN_TILES:
                entity_type_str, direction_str = MONSTER_SPAWN_TILES[tile_id]
                # offset to the center of the tile. (0,0) is the last pixel in the grid, (.5,.5) is the center of the first tile
                monster = DynamicEntity.create_monster(
                    EntityType(entity_type_str),
                    float(x + 0.5),
                    float(y + 0.5),
                    Direction(direction_str),
                )
                monsters.append(monster)
                # Replace spawn tile with empty in tilemap
                tilemap[i] = EMPTY_TILE_ID
                tile_id = EMPTY_TILE_ID

            # Check for treasure tile
            elif tile_id in TREASURE_TILES:
                treasure_type_str = TREASURE_TILES[tile_id]
                treasure = Treasure(
                    x=x,
                    y=y,
                    treasure_type=TreasureType(treasure_type_str),
                    visual_id=tile_id,
                )
                treasures.append(treasure)
                # Replace treasure tile with empty in tilemap
                tilemap[i] = EMPTY_TILE_ID
                tile_id = EMPTY_TILE_ID

            # Check for tool tile
            elif tile_id in TOOL_TILES:
                tool_type_str = TOOL_TILES[tile_id]
                tool = Tool(
                    x=x, y=y, tool_type=ToolType(tool_type_str), visual_id=tile_id
                )
                tools.append(tool)
                # Replace tool tile with empty in tilemap
                tilemap[i] = EMPTY_TILE_ID
                tile_id = EMPTY_TILE_ID

            # Create tile object
            # Handle rock1 and rock2 as damaged bedrock tiles
            if tile_id == ROCK1_TILE_ID:
                tile = Tile(
                    visual_id=tile_id,
                    tile_type=TileType.BEDROCK,
                    solid=True,
                    interactable=False,
                    diggable=True,
                    health=25,
                )
            elif tile_id == ROCK2_TILE_ID:
                tile = Tile(
                    visual_id=tile_id,
                    tile_type=TileType.BEDROCK,
                    solid=True,
                    interactable=False,
                    diggable=True,
                    health=50,
                )
            elif tile_id in BEDROCK_CORNER_TILES:
                tile = Tile(
                    visual_id=tile_id,
                    tile_type=TileType.BEDROCK,
                    solid=True,
                    interactable=False,
                    diggable=True,
                    health=60,
                )
            else:
                tile = Tile(
                    visual_id=tile_id,
                    tile_type=_get_tile_type(tile_id),
                    solid=_is_solid(tile_id),
                    interactable=_is_interactable(tile_id),
                    diggable=_is_diggable(tile_id),
                )
            row.append(tile)
        tiles.append(row)

    return MapData(
        width=width,
        height=height,
        tiles=tiles,
        tilemap=tilemap,
        monsters=monsters,
        treasures=treasures,
        tools=tools,
    )


def _get_tile_type(tile_id: int) -> TileType:
    """Determine tile type from tile ID."""
    if tile_id in BEDROCK_TILES:
        return TileType.BEDROCK
    if tile_id in DIRT_TILES:
        return TileType.DIRT
    if tile_id in CONCRETE_TILES:
        return TileType.CONCRETE
    if tile_id in URETHANE_TILES:
        return TileType.URETHANE
    if tile_id in BIOSLIME_TILES:
        return TileType.BIOSLIME
    if tile_id in BOULDER_TILES:
        return TileType.BOULDER
    if tile_id in BRICKS_TILES:
        return TileType.BRICKS
    if tile_id in SWITCH_TILES:
        return TileType.SWITCH
    if tile_id in SECURITY_DOOR_TILES:
        return TileType.SECURITY_DOOR
    if tile_id in TUNNEL_TILES:
        return TileType.TUNNEL
    return TileType.EMPTY


def _is_solid(tile_id: int) -> bool:
    """Determine if a tile blocks movement."""
    solid_tiles = (
        BEDROCK_TILES
        | CONCRETE_TILES
        | BOULDER_TILES
        | BRICKS_TILES
        | SECURITY_DOOR_TILES
        | DIRT_TILES
    )
    return tile_id in solid_tiles


def _is_diggable(tile_id: int) -> bool:
    """Determine if a tile can be digged"""
    solid_tiles = BEDROCK_TILES | BRICKS_TILES | DIRT_TILES | URETHANE_TILES | C4_TILES
    return tile_id in solid_tiles


def _is_interactable(tile_id: int) -> bool:
    """Determine if a tile can be interacted with."""
    interactable_tiles = BOULDER_TILES | SWITCH_TILES | TUNNEL_TILES
    return tile_id in interactable_tiles
